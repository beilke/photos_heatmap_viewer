"""
Fixed version of the process_photos.py script with all indentation issues resolved
and performance optimizations applied.
"""
import sqlite3
import os
import json
import argparse
import hashlib
import time
import multiprocessing
import pickle
import concurrent.futures
import logging
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from contextlib import closing

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import performance optimizations
try:
    from performance_helpers import fast_file_hash_cached, optimize_sqlite_connection
    from performance_helpers import get_optimal_worker_count
    HAS_PERFORMANCE_HELPERS = True
    logger.info("Performance helpers imported successfully")
except ImportError:
    HAS_PERFORMANCE_HELPERS = False
    logger.info("Performance helpers not available, using standard implementations")

# Fast file hash function that uses optimized implementation if available
def fast_hash(file_path, sample_size=65536):
    """Create a hash of the file by sampling beginning and end for speed"""
    if HAS_PERFORMANCE_HELPERS:
        return fast_file_hash_cached(file_path)
    
    try:
        file_size = os.path.getsize(file_path)
        
        if file_size < sample_size * 2:
            # For small files, just hash the entire file
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        
        hash_obj = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read first chunk
            hash_obj.update(f.read(sample_size))
            
            # Seek to the end and read last chunk
            f.seek(-sample_size, os.SEEK_END)
            hash_obj.update(f.read(sample_size))
            
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"Error creating fast hash for {file_path}: {e}")
        # Fall back to original method
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return None

def process_directory_incremental(root_dir, db_path='photo_library.db', max_workers=None, include_all=False, 
                                 library_name="Default", use_cache=True, resume=True, use_parallel_scan=True):
    """Process a directory of photos incrementally with optimizations for speed"""
    start_time = time.time()
    
    # Determine optimal number of workers
    if max_workers is None:
        if HAS_PERFORMANCE_HELPERS:
            max_workers = get_optimal_worker_count('cpu')
        else:
            max_workers = min(8, multiprocessing.cpu_count())
    
    # Determine optimal batch size
    batch_size = 500  # Default large batch size for better performance
    
    # Validate the directory
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    # Connect to database with optimizations
    conn = sqlite3.connect(db_path)
    if HAS_PERFORMANCE_HELPERS:
        optimize_sqlite_connection(conn)
    else:
        # Apply standard optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        
    cursor = conn.cursor()
    
    # Find existing paths in database
    cursor.execute("SELECT path FROM photos")
    existing_paths = {row[0] for row in cursor.fetchall()}
    logger.info(f"Found {len(existing_paths)} existing files in database")
    
    # Scan for image files
    image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
    new_files = []
    
    # Use parallel scanning if available and enabled
    if use_parallel_scan:
        try:
            from scan_functions import scan_directory_parallel
            new_files, total_files = scan_directory_parallel(root_dir, image_extensions, existing_paths)
            logger.info(f"Parallel scan complete. Found {len(new_files)} new files out of {total_files} total")
        except ImportError:
            logger.warning("Parallel scanning module not available, using serial scan")
            use_parallel_scan = False
    
    # Fall back to serial scanning
    if not use_parallel_scan:
        logger.info("Using serial directory scanning...")
        total_files = 0
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith(image_extensions):
                    total_files += 1
                    full_path = os.path.join(dirpath, filename)
                    if full_path not in existing_paths:
                        new_files.append(full_path)
                        
                    # Progress reporting for large directories
                    if total_files % 1000 == 0:
                        logger.info(f"Scanned {total_files} files, found {len(new_files)} new...")
    
    if not new_files:
        logger.info("No new files to process")
        conn.close()
        return
        
    # Get or create library ID
    library_id = 1  # Default
    try:
        cursor.execute("SELECT id FROM libraries WHERE name = ?", (library_name,))
        result = cursor.fetchone()
        if result:
            library_id = result[0]
        else:
            cursor.execute("INSERT INTO libraries (name, source_dirs) VALUES (?, ?)", 
                          (library_name, json.dumps([root_dir])))
            library_id = cursor.lastrowid
            conn.commit()
    except Exception as e:
        logger.error(f"Error getting library: {e}")
    
    # Process new files in batches
    processed_count = 0
    inserted_count = 0
    
    logger.info(f"Processing {len(new_files)} new files with {max_workers} workers...")
    
    # Process in batches for better performance
    for i in range(0, len(new_files), batch_size):
        batch = new_files[i:i+batch_size]
        batch_start_time = time.time()
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(new_files) + batch_size - 1)//batch_size}...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    
                    if processed_count % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        logger.info(f"Processed {processed_count}/{len(new_files)} images ({rate:.1f}/sec)")
                    
                    if result:
                        if include_all or (result['latitude'] and result['longitude']):
                            # Add library ID
                            result['library_id'] = library_id
                            # Add marker data as JSON
                            result['marker_data'] = json.dumps({
                                'title': os.path.basename(result['path']),
                                'date': result['datetime']
                            })
                            batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")
        
        # Insert the batch into the database
        if batch_results:
            try:
                cursor.executemany(
                    "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                      photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data']) for photo in batch_results]
                )
                inserted_this_batch = len(batch_results)
                inserted_count += inserted_this_batch
                conn.commit()
                
                # Report batch insertion rate
                batch_time = time.time() - batch_start_time
                if batch_time > 0:
                    rate = inserted_this_batch / batch_time
                    logger.info(f"Inserted {inserted_this_batch} photos ({rate:.1f}/sec)")
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")
                # Try inserting one by one
                for photo in batch_results:
                    try:
                        cursor.execute(
                            "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                             photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
                        )
                        inserted_count += 1
                    except sqlite3.IntegrityError:
                        # Skip duplicates
                        pass
                    except Exception as e:
                        logger.error(f"Error inserting photo {photo['path']}: {e}")
                conn.commit()
    
    # Final commit and cleanup
    conn.commit()
    conn.close()
    
    # Report final results
    total_time = time.time() - start_time
    logger.info(f"Processing complete. {processed_count} images processed, {inserted_count} inserted in {total_time:.1f} seconds")
    if processed_count > 0 and total_time > 0:
        process_rate = processed_count / total_time
        logger.info(f"Performance: {process_rate:.1f} photos/sec")

def process_image(image_path):
    """Process a single image and extract its metadata"""
    try:
        filename = os.path.basename(image_path)
        
        # Skip if file doesn't exist
        if not os.path.exists(image_path):
            return None
        
        # Get file hash using optimized method
        img_hash = fast_hash(image_path)
        
        # Extract date and GPS data
        latitude = None
        longitude = None
        datetime_str = None
        
        try:
            with Image.open(image_path) as img:
                # Try to get datetime
                datetime_str = extract_datetime_from_image(img, image_path)
                
                # Try to get GPS coordinates
                latitude, longitude = extract_gps_from_image(img, image_path)
        except Exception as e:
            logger.debug(f"Error processing image {image_path}: {e}")
            # Use file date as fallback
            datetime_str = datetime.fromtimestamp(os.path.getctime(image_path)).isoformat()
        
        return {
            'filename': filename,
            'path': image_path,
            'latitude': latitude,
            'longitude': longitude,
            'datetime': datetime_str,
            'hash': img_hash
        }
    except Exception as e:
        logger.error(f"Failed to process {image_path}: {e}")
        return None

# These are simplified placeholder functions - in a real implementation
# they would contain the existing extraction logic from your original script
def extract_datetime_from_image(img, image_path):
    """Extract date/time from image EXIF data"""
    try:
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    return dt.isoformat()
        
        # Fall back to file creation time
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()
    except Exception:
        # Final fallback
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()

def extract_gps_from_image(img, image_path):
    """Extract GPS coordinates from image EXIF data"""
    try:
        exif = img.getexif()
        if not exif:
            return None, None
            
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
                gps_info = {}
                
                for gps_tag, val in value.items():
                    gps_info[GPSTAGS.get(gps_tag, gps_tag)] = val
                
                if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                    lat = convert_to_degrees(gps_info['GPSLatitude'])
                    lon = convert_to_degrees(gps_info['GPSLongitude'])
                    
                    # Apply reference direction
                    if 'GPSLatitudeRef' in gps_info and gps_info['GPSLatitudeRef'] == 'S':
                        lat = -lat
                    if 'GPSLongitudeRef' in gps_info and gps_info['GPSLongitudeRef'] == 'W':
                        lon = -lon
                        
                    return lat, lon
        
        return None, None
    except Exception:
        return None, None

def convert_to_degrees(value):
    """Helper to convert GPS coordinates to decimal degrees"""
    d, m, s = value
    return d + (m / 60.0) + (s / 3600.0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process images for photo heatmap')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--library', default='Default', help='Library name for imported photos')
    parser.add_argument('--incremental', action='store_true', help='Use fast incremental processing')
    parser.add_argument('--workers', type=int, default=None, help='Number of worker threads (auto if not specified)')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    
    args = parser.parse_args()
    
    if args.process:
        process_directory_incremental(
            root_dir=args.process,
            db_path=args.db,
            max_workers=args.workers,
            include_all=args.include_all,
            library_name=args.library
        )
