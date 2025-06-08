"""
Fixed version of photo processing script with correct indentation and improved error handling.
"""
import sqlite3
import os
import json
import argparse
import hashlib
import time
import multiprocessing
import concurrent.futures
import logging
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import heif support if available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIF/HEIC support enabled")
    HEIC_SUPPORT = True
except ImportError:
    logger.warning("pillow-heif not installed. HEIC files will not be processed.")
    logger.warning("To enable HEIC support, install with: pip install pillow-heif")
    HEIC_SUPPORT = False

# Try to import scan_functions for parallel scanning
try:
    from scan_functions import scan_directory_parallel
    HAS_PARALLEL_SCAN = True
    logger.info("Using scan_functions module for parallel directory scanning")
except ImportError:
    HAS_PARALLEL_SCAN = False
    logger.warning("scan_functions.py module not found, parallel scan functionality disabled")

# Try to import performance helpers
try:
    from performance_helpers import fast_file_hash_cached, get_optimal_worker_count
    HAS_PERFORMANCE_HELPERS = True
    logger.info("Performance optimization helpers available")
except ImportError:
    HAS_PERFORMANCE_HELPERS = False
    logger.info("Performance helpers not available, using standard implementations")

def fast_hash(file_path, sample_size=65536):
    """Create a quick hash of a file by reading only the beginning and end."""
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
        # Fall back to standard method
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return None

def optimize_sqlite_connection(conn):
    """Apply performance optimizations to the SQLite connection."""
    settings = {}
    try:
        # Enable WAL mode for better concurrent write performance
        conn.execute("PRAGMA journal_mode=WAL")
        settings['journal_mode'] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        
        # Set a large cache size (in pages)
        conn.execute("PRAGMA cache_size=20000")
        settings['cache_size'] = conn.execute("PRAGMA cache_size").fetchone()[0]
        
        # Set synchronous mode (2=FULL, 1=NORMAL, 0=OFF)
        conn.execute("PRAGMA synchronous=NORMAL")
        settings['synchronous'] = conn.execute("PRAGMA synchronous").fetchone()[0]
        
        # Store temp tables in memory
        conn.execute("PRAGMA temp_store=MEMORY")
        settings['temp_store'] = conn.execute("PRAGMA temp_store").fetchone()[0]
        
        # Use memory mapping
        conn.execute("PRAGMA mmap_size=536870912")  # 512MB
        settings['mmap_size'] = conn.execute("PRAGMA mmap_size").fetchone()[0]
        
        # Additional optimizations
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        settings['locking_mode'] = conn.execute("PRAGMA locking_mode").fetchone()[0]
        
        logger.info(f"Applied advanced SQLite optimizations: {settings}")
        return settings
    except Exception as e:
        logger.error(f"Failed to apply some SQLite optimizations: {e}")
        return settings

def get_or_create_library(cursor, library_name, source_dirs=None):
    """Get or create a library entry."""
    cursor.execute("SELECT id FROM libraries WHERE name = ?", (library_name,))
    result = cursor.fetchone()
    if result:
        # Library exists
        library_id = result[0]
    else:
        # Create new library
        if source_dirs:
            source_dirs_json = json.dumps(source_dirs)
        else:
            source_dirs_json = None
            
        cursor.execute(
            "INSERT INTO libraries (name, source_dirs) VALUES (?, ?)",
            (library_name, source_dirs_json)
        )
        library_id = cursor.lastrowid
        
    return library_id

def extract_gps_from_image(img, image_path):
    """Extract GPS coordinates from image EXIF data."""
    try:
        exif = img._getexif() if hasattr(img, '_getexif') else img.getexif()
        
        if not exif:
            return None, None
            
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
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
    except Exception as e:
        logger.debug(f"Error extracting GPS from {image_path}: {e}")
        return None, None

def convert_to_degrees(value):
    """Convert GPS coordinates to decimal degrees."""
    if not value:
        return None
    
    try:
        d = float(value[0][0]) / float(value[0][1]) if value[0][1] != 0 else 0
        m = float(value[1][0]) / float(value[1][1]) / 60.0 if value[1][1] != 0 else 0
        s = float(value[2][0]) / float(value[2][1]) / 3600.0 if value[2][1] != 0 else 0
        return d + m + s
    except (IndexError, ZeroDivisionError, TypeError):
        return None

def extract_datetime_from_image(img, image_path):
    """Extract date/time from image EXIF data."""
    try:
        exif = img._getexif() if hasattr(img, '_getexif') else img.getexif()
        
        if exif:
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    try:
                        dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                        return dt.isoformat()
                    except (ValueError, TypeError):
                        pass
        
        # Fall back to file creation time
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()
    except Exception:
        # Final fallback
        try:
            file_time = os.path.getctime(image_path)
            return datetime.fromtimestamp(file_time).isoformat()
        except Exception:
            return datetime.now().isoformat()

def create_marker_data(photo_info):
    """Create JSON data for map markers."""
    try:
        result = {
            'title': os.path.basename(photo_info['path']),
            'date': photo_info['datetime']
        }
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error creating marker data: {e}")
        return None

def process_image(image_path):
    """Process a single image and extract its metadata."""
    try:
        # Skip if file doesn't exist
        if not os.path.exists(image_path):
            return None
            
        filename = os.path.basename(image_path)
        
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

def process_directory(root_dir, db_path='photo_library.db', max_workers=None, include_all=False,
                     skip_existing=True, library_name="Default"):
    """Process a directory of photos and add them to the database."""
    start_time = time.time()
    
    # Determine optimal number of workers
    if max_workers is None:
        if HAS_PERFORMANCE_HELPERS:
            max_workers = get_optimal_worker_count('cpu')
        else:
            max_workers = min(8, multiprocessing.cpu_count())
    
    # Validate the directory
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    logger.info(f"Processing directory: {root_dir}")
    logger.info(f"Using {max_workers} worker threads")
    
    # Connect to database with optimizations
    conn = sqlite3.connect(db_path)
    optimize_sqlite_connection(conn)
    cursor = conn.cursor()
    
    # Get or create library ID
    library_id = get_or_create_library(cursor, library_name, [root_dir])
    conn.commit()
    
    logger.info(f"Using library: {library_name} (ID: {library_id})")
    
    # Define image extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
    
    # Find image files
    logger.info("Scanning directory for images...")
    all_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.lower().endswith(image_extensions):
                all_files.append(os.path.join(dirpath, filename))
                
                # Report progress on large scans
                if len(all_files) % 5000 == 0:
                    logger.info(f"Found {len(all_files)} image files so far...")
    
    logger.info(f"Found {len(all_files)} image files")
    
    # Skip existing images if requested
    if skip_existing:
        logger.info("Checking for existing photos in database...")
        cursor.execute("SELECT path FROM photos")
        existing_paths = {row[0] for row in cursor.fetchall()}
        new_files = [f for f in all_files if f not in existing_paths]
        logger.info(f"Skipping {len(all_files) - len(new_files)} existing files")
        all_files = new_files
    
    if not all_files:
        logger.info("No new files to process")
        conn.close()
        return
    
    # Process images in batches
    batch_size = 500  # Large batch size for better performance
    processed_count = 0
    inserted_count = 0
    
    logger.info(f"Processing {len(all_files)} files in batches of {batch_size}...")
    
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i+batch_size]
        batch_start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    
                    # Report progress
                    if processed_count % 50 == 0:
                        elapsed = time.time() - start_time
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        logger.info(f"Processed {processed_count}/{len(all_files)} images... ({rate:.1f} images/sec)")
                    
                    if result:
                        if include_all or (result['latitude'] and result['longitude']):
                            # Add marker data
                            result['marker_data'] = create_marker_data(result)
                            result['library_id'] = library_id
                            batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")
        
        # Insert batch results
        if batch_results:
            try:
                # Use executemany for better performance
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
                success_count = 0
                for photo in batch_results:
                    try:
                        cursor.execute(
                            "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                             photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
                        )
                        success_count += 1
                        
                        # Commit every 10 records
                        if success_count % 10 == 0:
                            conn.commit()
                    except sqlite3.IntegrityError:
                        # Skip duplicates
                        pass
                    except Exception as inner_e:
                        logger.error(f"Error inserting photo {photo['path']}: {inner_e}")
                
                # Final commit for this batch
                conn.commit()
                inserted_count += success_count
                logger.info(f"Inserted {success_count}/{len(batch_results)} photos individually")
    
    # Final commit and cleanup
    conn.commit()
    conn.close()
    
    # Report final results
    total_time = time.time() - start_time
    logger.info(f"Processing complete. {processed_count} images processed, {inserted_count} inserted in {total_time:.1f} seconds")
    if processed_count > 0 and total_time > 0:
        process_rate = processed_count / total_time
        logger.info(f"Performance: {process_rate:.1f} photos/sec")

# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process images and create a photo heatmap database')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--export', action='store_true', help='Export database to JSON')
    parser.add_argument('--output', default='photo_heatmap_data.json', help='Output JSON file path')
    parser.add_argument('--workers', type=int, default=None, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--incremental', action='store_true', help='Use incremental processing (only process new files)')
    parser.add_argument('--library', default='Default', help='Specify the library name for imported photos')
    
    args = parser.parse_args()
    
    if args.process:
        process_directory(
            root_dir=args.process,
            db_path=args.db,
            max_workers=args.workers,
            include_all=args.include_all,
            library_name=args.library
        )
    
    if args.export:
        # Import the export_to_json function if needed
        try:
            from process_photos import export_to_json
            export_to_json(args.db, args.output, include_non_geotagged=args.include_all)
        except ImportError:
            print("Export functionality not available in this script")
