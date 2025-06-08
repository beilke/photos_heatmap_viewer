"""
Fixed version of the process_directory function with proper indentation and error handling
"""
import sqlite3
import os
import time
import json
import hashlib
import concurrent.futures
import logging
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)

def process_directory_fixed(root_dir, db_path='photo_library.db', max_workers=8, include_all=False, 
                        skip_existing=True, library_name="Default"):
    """Process a directory of images and add them to the database.
    This is a fixed version with proper indentation and error handling.
    """
    start_time = time.time()
    print(f"Processing directory: {root_dir}")
    print(f"Using database: {db_path}")
    
    # Validate the directory
    if not os.path.isdir(root_dir):
        print(f"Error: {root_dir} is not a directory")
        return
    
    # Connect to database with optimizations
    try:
        conn = sqlite3.connect(db_path)
        # Apply optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        
        cursor = conn.cursor()
        
        # Make sure we have a library
        library_id = None
        try:
            cursor.execute("SELECT id FROM libraries WHERE name = ?", (library_name,))
            result = cursor.fetchone()
            if result:
                library_id = result[0]
                print(f"Using existing library: {library_name} (ID: {library_id})")
            else:
                cursor.execute("INSERT INTO libraries (name, source_dirs) VALUES (?, ?)", 
                              (library_name, json.dumps([root_dir])))
                library_id = cursor.lastrowid
                print(f"Created new library: {library_name} (ID: {library_id})")
            conn.commit()
        except Exception as e:
            print(f"Error setting up library: {e}")
            library_id = 1  # Use default library ID as fallback
        
        # Get index of existing files if needed
        existing_files = set()
        if skip_existing:
            try:
                cursor.execute("SELECT path FROM photos")
                existing_files = {row[0] for row in cursor.fetchall()}
                print(f"Found {len(existing_files)} existing files in database")
            except Exception as e:
                print(f"Error getting existing files: {e}")
                
        # Define image extensions
        image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
        
        # Find all image files
        print(f"Looking for files with these extensions: {', '.join(image_extensions)}")
        all_files = []
        
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith(image_extensions):
                    full_path = os.path.join(dirpath, filename)
                    if not skip_existing or full_path not in existing_files:
                        all_files.append(full_path)
            
            # Print progress for large directories
            if len(all_files) % 1000 == 0 and len(all_files) > 0:
                print(f"Found {len(all_files)} files so far...")
        
        if not all_files:
            print("No new files found to process")
            conn.close()
            return
            
        print(f"Found {len(all_files)} files to process")
        
        # Process files in batches
        batch_size = 200  # Increased batch size for better performance
        processed_count = 0
        inserted_count = 0
        
        for i in range(0, len(all_files), batch_size):
            batch = all_files[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(all_files) + batch_size - 1)//batch_size}...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_path = {executor.submit(process_image, path): path for path in batch}
                batch_results = []
                
                for future in concurrent.futures.as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        result = future.result()
                        processed_count += 1
                        
                        if processed_count % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed_count / elapsed if elapsed > 0 else 0
                            print(f"Processed {processed_count}/{len(all_files)} images... ({rate:.1f} images/sec)")
                        
                        if result:
                            if include_all or (result['latitude'] and result['longitude']):
                                # Add marker data
                                result['marker_data'] = json.dumps({
                                    'title': os.path.basename(result['path']),
                                    'date': result['datetime']
                                })
                                result['library_id'] = library_id
                                batch_results.append(result)
                    except Exception as e:
                        print(f"Error processing {path}: {e}")
            
            # Insert batch results into database
            if batch_results:
                try:
                    # Try bulk insert first
                    cursor.executemany(
                        "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [(photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                          photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data']) for photo in batch_results]
                    )
                    inserted_count += len(batch_results)
                    conn.commit()
                except Exception as e:
                    # If bulk insert fails, try one by one
                    print(f"Batch insert failed: {e}")
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
                            print(f"Error inserting {photo['path']}: {inner_e}")
                    
                    # Final commit for this batch
                    try:
                        conn.commit()
                        inserted_count += success_count
                        print(f"Inserted {success_count} photos individually")
                    except Exception as commit_e:
                        print(f"Error during commit: {commit_e}")
        
        # Processing complete
        try:
            conn.commit()
            conn.close()
            
            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            
            print(f"Processing complete in {elapsed:.1f} seconds")
            print(f"Processed {processed_count} images ({rate:.1f} images/sec)")
            print(f"Inserted {inserted_count} images into database")
            
        except Exception as final_e:
            print(f"Error finalizing processing: {final_e}")
            
    except Exception as e:
        print(f"Fatal error during processing: {e}")

def get_image_hash(image_path):
    """Create a hash of the file to identify duplicates"""
    try:
        file_size = os.path.getsize(image_path)
        
        # For large files, only read part of the file for faster hashing
        if file_size > 1024 * 1024:  # If larger than 1MB
            with open(image_path, 'rb') as f:
                # Read first 64KB and last 64KB
                first_chunk = f.read(65536)
                f.seek(-65536, os.SEEK_END)
                last_chunk = f.read(65536)
                return hashlib.md5(first_chunk + last_chunk).hexdigest()
        else:
            # For smaller files, hash the entire content
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {image_path}: {e}")
        return None

def extract_datetime(image_path):
    """Extract datetime from image EXIF data"""
    try:
        with Image.open(image_path) as img:
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
        try:
            file_time = os.path.getctime(image_path)
            return datetime.fromtimestamp(file_time).isoformat()
        except:
            return None

def get_decimal_from_dms(dms, ref):
    """Convert GPS DMS to decimal format"""
    try:
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        decimal = degrees + minutes + seconds
        
        # Apply reference direction
        if ref in ('S', 'W'):
            decimal = -decimal
            
        return decimal
    except:
        return None

def extract_gps(image_path):
    """Extract GPS coordinates from image EXIF data"""
    try:
        with Image.open(image_path) as img:
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
                        lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info.get('GPSLatitudeRef', 'N'))
                        lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info.get('GPSLongitudeRef', 'E'))
                        return lat, lon
        
        return None, None
    except Exception:
        return None, None

def process_image(image_path):
    """Process a single image and extract its metadata"""
    try:
        # Skip non-existent files
        if not os.path.exists(image_path):
            return None
            
        # Extract basic file info
        filename = os.path.basename(image_path)
        
        # Get hash
        img_hash = get_image_hash(image_path)
        
        # Extract date and GPS coordinates
        datetime_str = extract_datetime(image_path)
        latitude, longitude = extract_gps(image_path)
        
        return {
            'filename': filename,
            'path': image_path,
            'latitude': latitude,
            'longitude': longitude,
            'datetime': datetime_str,
            'hash': img_hash
        }
    except Exception as e:
        logger.error(f"Error processing image {image_path}: {e}")
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Process photos for heatmap visualization')
    parser.add_argument('--process', required=True, help='Directory with photos to process')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--library', default='Default', help='Library name')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--workers', type=int, default=8, help='Number of worker threads')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Run the process function
    process_directory_fixed(
        root_dir=args.process,
        db_path=args.db,
        max_workers=args.workers,
        include_all=args.include_all,
        library_name=args.library
    )
