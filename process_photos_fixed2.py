"""
Fixed version of the photo processing script with improved database handling
"""
import sqlite3
import os
import json
import argparse
import time
import logging
import multiprocessing
import concurrent.futures
from PIL import Image
from datetime import datetime
from PIL.ExifTags import TAGS, GPSTAGS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fast_hash(image_path, sample_size=65536):
    """Create a fast hash of the image by sampling only parts of the file"""
    import hashlib
    
    try:
        file_size = os.path.getsize(image_path)
        
        if file_size < sample_size * 2:
            # For small files, just hash the entire file
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        
        # For larger files, only hash the beginning and end portions
        hash_obj = hashlib.md5()
        with open(image_path, 'rb') as f:
            # Read first chunk
            hash_obj.update(f.read(sample_size))
            
            # Seek to the end and read last chunk
            f.seek(-sample_size, os.SEEK_END)
            hash_obj.update(f.read(sample_size))
            
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {image_path}: {e}")
        return None

def optimize_sqlite_connection(conn):
    """Apply optimizations to SQLite connection for better performance"""
    try:
        # Enable WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Set cache size (in pages)
        conn.execute("PRAGMA cache_size=20000")
        
        # Set synchronous mode (2=FULL, 1=NORMAL, 0=OFF)
        conn.execute("PRAGMA synchronous=NORMAL")
        
        # Store temp tables in memory
        conn.execute("PRAGMA temp_store=MEMORY")
        
        # Use memory mapping
        conn.execute("PRAGMA mmap_size=536870912")  # 512MB
        
        # Exclusive locking for better performance
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        
        # Collect settings for logging
        settings = {}
        for pragma in ['journal_mode', 'cache_size', 'synchronous', 'temp_store', 
                      'mmap_size', 'locking_mode']:
            settings[pragma] = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
        
        logger.info(f"Applied advanced SQLite optimizations: {settings}")
        return settings
    except Exception as e:
        logger.error(f"Error optimizing SQLite connection: {e}")
        return {}

def extract_datetime(img, image_path):
    """Extract datetime from image EXIF data"""
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
    except Exception as e:
        logger.debug(f"Error extracting datetime from {image_path}: {e}")
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()
        
def extract_gps(img, image_path):
    """Extract GPS coordinates from image EXIF data"""
    try:
        exif = img.getexif()
        if not exif:
            return None, None
            
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == 'GPSInfo':
                for gps_tag, val in value.items():
                    gps_info[GPSTAGS.get(gps_tag, gps_tag)] = val
                
                if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                    lat = _convert_to_decimal(gps_info['GPSLatitude'])
                    lon = _convert_to_decimal(gps_info['GPSLongitude'])
                    
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
        
def _convert_to_decimal(value):
    """Convert GPS coordinates to decimal degrees"""
    d = float(value[0][0]) / float(value[0][1]) if value[0][1] != 0 else 0
    m = float(value[1][0]) / float(value[1][1]) / 60.0 if value[1][1] != 0 else 0
    s = float(value[2][0]) / float(value[2][1]) / 3600.0 if value[2][1] != 0 else 0
    return d + m + s

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
                datetime_str = extract_datetime(img, image_path)
                
                # Try to get GPS coordinates
                latitude, longitude = extract_gps(img, image_path)
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

def create_marker_data(photo):
    """Create marker data JSON for a photo"""
    marker_data = {
        'title': photo['filename'],
        'datetime': photo['datetime']
    }
    return json.dumps(marker_data)

def get_or_create_library(cursor, name, source_dirs=None):
    """Get or create library ID"""
    try:
        cursor.execute("SELECT id FROM libraries WHERE name = ?", (name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            source_dirs_json = json.dumps(source_dirs) if source_dirs else None
            cursor.execute(
                "INSERT INTO libraries (name, source_dirs) VALUES (?, ?)", 
                (name, source_dirs_json)
            )
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error getting/creating library: {e}")
        return 1  # Default to ID 1

def process_photos(root_dir, db_path='photo_library.db', max_workers=None, include_all=False, library_name="Default"):
    """Process photos with robust error handling and performance optimizations"""
    start_time = time.time()
    
    # Validate directory
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    # Determine optimal number of workers
    if max_workers is None:
        max_workers = min(8, multiprocessing.cpu_count())
    
    logger.info(f"Starting photo processing in {root_dir}")
    logger.info(f"Using {max_workers} worker threads")
    
    # Connect to database with robust error handling
    try:
        conn = sqlite3.connect(db_path, isolation_level="DEFERRED", timeout=30.0)
        cursor = conn.cursor()
        
        # Optimize the connection
        optimize_sqlite_connection(conn)
        
        # Make sure tables exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS libraries (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          description TEXT,
          source_dirs TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
          id INTEGER PRIMARY KEY,
          filename TEXT,
          path TEXT UNIQUE,
          latitude REAL,
          longitude REAL,
          datetime TEXT,
          tags TEXT,
          hash TEXT,
          library_id INTEGER,
          marker_data TEXT,
          FOREIGN KEY (library_id) REFERENCES libraries(id)
        )
        ''')
        
        # Create indexes if they don't exist
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_coords ON photos(latitude, longitude)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datetime ON photos(datetime)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_path ON photos(path)')
        conn.commit()
        
        # Get or create library
        library_id = get_or_create_library(cursor, library_name, [root_dir])
        conn.commit()
        
        logger.info(f"Using library: {library_name} (ID: {library_id})")
        
        # Scan directory for image files
        image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
        
        logger.info(f"Scanning directory: {root_dir}")
        logger.info(f"Looking for files with these extensions: {', '.join(image_extensions)}")
        
        # List subdirectories for user feedback
        subdirs = [d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))]
        if subdirs:
            logger.info("Subdirectories found:")
            for d in subdirs:
                logger.info(f"  - {d}")
        
        # Find image files
        all_files = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Log progress for large directories
            rel_path = os.path.relpath(dirpath, root_dir)
            if rel_path != '.':
                logger.info(f"Scanning: {rel_path}")
            
            for filename in filenames:
                if filename.lower().endswith(image_extensions):
                    all_files.append(os.path.join(dirpath, filename))
        
        # Filter out files already in database
        cursor.execute("SELECT path FROM photos")
        existing_paths = {row[0] for row in cursor.fetchall()}
        to_process = [f for f in all_files if f not in existing_paths]
        
        logger.info(f"Found {len(all_files)} image files")
        logger.info(f"Found {len(to_process)} new files to process")
        
        if not to_process:
            logger.info("No new files to process")
            conn.close()
            return
        
        # Process images in batches
        batch_size = 500  # Larger batch size for better performance
        processed_count = 0
        inserted_count = 0
        
        for i in range(0, len(to_process), batch_size):
            batch = to_process[i:i+batch_size]
            batch_start_time = time.time()
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(to_process) + batch_size - 1)//batch_size}")
            
            # Process images in parallel
            batch_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_image, path): path for path in batch}
                
                for future in concurrent.futures.as_completed(futures):
                    path = futures[future]
                    try:
                        result = future.result()
                        processed_count += 1
                        
                        # Log progress
                        if processed_count % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed_count / elapsed if elapsed > 0 else 0
                            logger.info(f"Processed {processed_count}/{len(to_process)} images... ({rate:.1f} images/sec)")
                        
                        # Keep image if it has GPS data or if include_all is True
                        if result and (include_all or (result['latitude'] and result['longitude'])):
                            # Add marker data and library ID
                            result['marker_data'] = create_marker_data(result)
                            result['library_id'] = library_id
                            batch_results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing {path}: {e}")
            
            # Insert batch results
            if batch_results:
                # Use transaction for better performance
                try:
                    # Prepare batch insert data
                    insert_data = [(
                        photo['filename'], 
                        photo['path'],
                        photo['latitude'],
                        photo['longitude'],
                        photo['datetime'],
                        photo['hash'],
                        photo['library_id'],
                        photo['marker_data']
                    ) for photo in batch_results]
                    
                    # Execute batch insert
                    cursor.executemany(
                        "INSERT OR IGNORE INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        insert_data
                    )
                    
                    # Commit transaction
                    conn.commit()
                    inserted_this_batch = len(batch_results)
                    inserted_count += inserted_this_batch
                    
                    # Log insertion rate
                    batch_time = time.time() - batch_start_time
                    rate = inserted_this_batch / batch_time if batch_time > 0 else 0
                    logger.info(f"Inserted {inserted_this_batch} photos ({rate:.1f} photos/sec)")
                    
                except (sqlite3.OperationalError, sqlite3.ProgrammingError) as e:
                    logger.error(f"Database error: {e}")
                    logger.info("Falling back to individual inserts...")
                    
                    # Try individual inserts as fallback
                    success_count = 0
                    for photo in batch_results:
                        try:
                            cursor.execute(
                                "INSERT OR IGNORE INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (photo['filename'], photo['path'], photo['latitude'], photo['longitude'],
                                 photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
                            )
                            success_count += 1
                            
                            # Commit periodically
                            if success_count % 10 == 0:
                                conn.commit()
                        except Exception as insert_error:
                            logger.error(f"Error inserting {photo['path']}: {insert_error}")
                    
                    # Final commit for individual inserts
                    conn.commit()
                    logger.info(f"Inserted {success_count} photos individually")
                    inserted_count += success_count
                    
                except Exception as e:
                    logger.error(f"Unexpected error during batch insert: {e}")
        
        # Final commit and cleanup
        try:
            conn.commit()
        except:
            pass
            
        # Log performance statistics
        total_time = time.time() - start_time
        logger.info(f"Processing complete: {processed_count} images processed, {inserted_count} inserted")
        if total_time > 0:
            process_rate = processed_count / total_time
            logger.info(f"Overall processing rate: {process_rate:.1f} photos/sec")
        
    except Exception as e:
        logger.error(f"Error in photo processing: {e}")
    finally:
        # Ensure connection is properly closed
        try:
            if 'conn' in locals() and conn:
                conn.close()
        except:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process photos for heatmap visualization')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--workers', type=int, default=None, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--library', default='Default', help='Library name for imported photos')
    
    args = parser.parse_args()
    
    if args.process:
        process_photos(
            root_dir=args.process,
            db_path=args.db,
            max_workers=args.workers,
            include_all=args.include_all,
            library_name=args.library
        )
