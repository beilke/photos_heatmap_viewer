#!/usr/bin/env python3
"""
Photo heatmap processor - fixed version with optimized performance
"""
import sqlite3
import os
import json
import argparse
import hashlib
from datetime import datetime
import time
import multiprocessing
import concurrent.futures
import logging
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import performance helpers
try:
    from performance_helpers import fast_file_hash_cached
    HAS_PERFORMANCE_HELPERS = True
except ImportError:
    HAS_PERFORMANCE_HELPERS = False

# Try to import HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIF/HEIC support enabled")
    HEIC_SUPPORT = True
except ImportError:
    logger.warning("pillow-heif not installed. HEIC files will not be processed.")
    HEIC_SUPPORT = False

def fast_hash(image_path, sample_size=65536):
    """Create a fast hash of the file by sampling beginning and end for speed"""
    try:
        if HAS_PERFORMANCE_HELPERS:
            return fast_file_hash_cached(image_path)
        
        file_size = os.path.getsize(image_path)
        
        if file_size < sample_size * 2:
            # For small files, just hash the entire file
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        
        hash_obj = hashlib.md5()
        with open(image_path, 'rb') as f:
            # Read first chunk
            hash_obj.update(f.read(sample_size))
            
            # Seek to the end and read last chunk
            f.seek(-sample_size, os.SEEK_END)
            hash_obj.update(f.read(sample_size))
            
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"Error creating fast hash for {image_path}: {e}")
        try:
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {image_path}: {e}")
            return None

def get_exif_data(img):
    """Get EXIF data from an image"""
    if hasattr(img, 'getexif'):
        return img.getexif()
    elif hasattr(img, '_getexif'):
        return img._getexif()
    else:
        return None

def extract_datetime(image_path):
    """Extract datetime from image EXIF"""
    try:
        with Image.open(image_path) as img:
            exif_data = get_exif_data(img)
            
            if not exif_data:
                file_time = os.path.getctime(image_path)
                return datetime.fromtimestamp(file_time).isoformat()
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    return dt.isoformat()
            
            file_time = os.path.getctime(image_path)
            return datetime.fromtimestamp(file_time).isoformat()
    except Exception as e:
        logger.debug(f"Error extracting datetime: {e}")
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()

def get_decimal_from_dms(dms, ref):
    """Convert GPS DMS to decimal format"""
    try:
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        decimal = degrees + minutes + seconds
        
        if ref and ref in ('S', 'W'):
            decimal = -decimal
        
        return decimal
    except Exception as e:
        logger.debug(f"Error converting GPS: {e}")
        return None

def extract_gps(image_path):
    """Extract GPS coordinates from image"""
    try:
        with Image.open(image_path) as img:
            exif_data = get_exif_data(img)
            
            if not exif_data:
                return None, None
                
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'GPSInfo':
                    gps_info = {}
                    
                    for gps_tag, val in value.items():
                        gps_info[GPSTAGS.get(gps_tag, gps_tag)] = val
                    
                    lat = lon = None
                    
                    if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
                        lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
                    
                    if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                        lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
                    
                    return lat, lon
            
            return None, None
    except Exception as e:
        logger.debug(f"Error extracting GPS: {e}")
        return None, None

def process_image(image_path):
    """Process a single image"""
    try:
        filename = os.path.basename(image_path)
        
        # Skip if file doesn't exist
        if not os.path.exists(image_path):
            return None
        
        # Get hash
        img_hash = fast_hash(image_path)
        
        # Extract metadata
        latitude, longitude = extract_gps(image_path)
        datetime_str = extract_datetime(image_path)
        
        return {
            'filename': filename,
            'path': image_path,
            'latitude': latitude,
            'longitude': longitude,
            'datetime': datetime_str,
            'hash': img_hash
        }
    except Exception as e:
        logger.error(f"Error processing {image_path}: {e}")
        return None

def optimize_sqlite_connection(conn):
    """Apply SQLite optimizations"""
    settings = {}
    try:
        # WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        settings['journal_mode'] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        
        # Large cache
        conn.execute("PRAGMA cache_size=20000")
        settings['cache_size'] = conn.execute("PRAGMA cache_size").fetchone()[0]
        
        # Other optimizations
        conn.execute("PRAGMA synchronous=NORMAL")
        settings['synchronous'] = conn.execute("PRAGMA synchronous").fetchone()[0]
        conn.execute("PRAGMA temp_store=MEMORY")
        settings['temp_store'] = conn.execute("PRAGMA temp_store").fetchone()[0]
        conn.execute("PRAGMA mmap_size=536870912")  # 512MB
        settings['mmap_size'] = conn.execute("PRAGMA mmap_size").fetchone()[0]
        
        logger.info(f"Applied SQLite optimizations: {settings}")
        return settings
    except Exception as e:
        logger.error(f"Failed to apply SQLite optimizations: {e}")
        return settings

def get_or_create_library(cursor, library_name, source_dirs=None):
    """Get or create a library in the database"""
    try:
        cursor.execute("SELECT id FROM libraries WHERE name = ?", (library_name,))
        result = cursor.fetchone()
        
        if result:
            library_id = result[0]
            logger.info(f"Using library: {library_name} (ID: {library_id})")
            return library_id
        else:
            source_dirs_json = json.dumps(source_dirs) if source_dirs else '[]'
            cursor.execute(
                "INSERT INTO libraries (name, source_dirs) VALUES (?, ?)",
                (library_name, source_dirs_json)
            )
            library_id = cursor.lastrowid
            logger.info(f"Created library: {library_name} (ID: {library_id})")
            return library_id
    except Exception as e:
        logger.error(f"Error with library: {e}")
        return 1  # Default to ID 1

def create_marker_data(photo_data):
    """Create JSON marker data for a photo"""
    try:
        marker = {
            'title': os.path.basename(photo_data['path']),
            'date': photo_data['datetime']
        }
        return json.dumps(marker)
    except:
        return '{}'

def process_directory_incremental(root_dir, db_path='photo_library.db', max_workers=None, include_all=False, 
                                 library_name="Default", use_cache=True, resume=True, use_parallel_scan=True):
    """Process a directory incrementally"""
    start_time = time.time()
    
    # Set optimal worker count
    if max_workers is None:
        cpu_count = multiprocessing.cpu_count()
        max_workers = max(2, cpu_count - 1)
    
    logger.info(f"Starting incremental processing with {max_workers} workers")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        optimize_sqlite_connection(conn)
        cursor = conn.cursor()
        
        # Get or create library
        library_id = get_or_create_library(cursor, library_name, [root_dir])
        conn.commit()
        
        # Get existing paths
        cursor.execute("SELECT path FROM photos")
        existing_paths = {row[0] for row in cursor.fetchall()}
        logger.info(f"Found {len(existing_paths)} existing photos in database")
        
        # Scan for new images
        image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
        new_files = []
        total_files = 0
        
        # Walk the directory
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith(image_extensions):
                    total_files += 1
                    full_path = os.path.join(dirpath, filename)
                    if full_path not in existing_paths:
                        new_files.append(full_path)
            
            # Progress report
            if total_files % 1000 == 0:
                logger.info(f"Scanned {total_files} files, found {len(new_files)} new...")
        
        logger.info(f"Scan complete: {len(new_files)} new files of {total_files} total")
        
        if not new_files:
            logger.info("No new files to process")
            conn.close()
            return
        
        # Process in batches
        batch_size = 500
        processed_count = 0
        inserted_count = 0
        
        for i in range(0, len(new_files), batch_size):
            batch = new_files[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(new_files) + batch_size - 1)//batch_size}...")
            
            batch_results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_path = {executor.submit(process_image, path): path for path in batch}
                
                for future in concurrent.futures.as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        result = future.result()
                        processed_count += 1
                        
                        if processed_count % 50 == 0:
                            elapsed = time.time() - start_time
                            rate = processed_count / elapsed if elapsed > 0 else 0
                            logger.info(f"Processed {processed_count}/{len(new_files)} images ({rate:.1f}/sec)")
                        
                        if result:
                            if include_all or (result['latitude'] and result['longitude']):
                                result['marker_data'] = create_marker_data(result)
                                result['library_id'] = library_id
                                batch_results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing {path}: {e}")
            
            # Insert batch
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
                    logger.info(f"Inserted {inserted_this_batch} photos")
                except Exception as e:
                    logger.error(f"Batch insert error: {e}")
                    # Try one by one
                    for photo in batch_results:
                        try:
                            cursor.execute(
                                "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                                 photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
                            )
                            inserted_count += 1
                        except Exception as inner_e:
                            logger.error(f"Individual insert error: {inner_e}")
                    conn.commit()
        
        # Final stats
        conn.close()
        total_time = time.time() - start_time
        logger.info(f"Processing complete: {processed_count} processed, {inserted_count} inserted")
        if total_time > 0:
            rate = processed_count / total_time
            logger.info(f"Rate: {rate:.1f} images/sec")
        
    except Exception as e:
        logger.error(f"Error during processing: {e}")

def export_to_json(db_path='photo_library.db', output_path='photo_heatmap_data.json', include_non_geotagged=False):
    """Export database to JSON"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get libraries
        cursor.execute("SELECT * FROM libraries")
        libraries = [dict(row) for row in cursor.fetchall()]
        
        # Get photos
        if include_non_geotagged:
            cursor.execute('''
            SELECT p.id, p.filename, p.latitude, p.longitude, p.datetime, p.path, 
                   p.marker_data, p.library_id, l.name as library_name
            FROM photos p
            LEFT JOIN libraries l ON p.library_id = l.id
            ''')
        else:
            cursor.execute('''
            SELECT p.id, p.filename, p.latitude, p.longitude, p.datetime, p.path, 
                   p.marker_data, p.library_id, l.name as library_name
            FROM photos p
            LEFT JOIN libraries l ON p.library_id = l.id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
            ''')
        
        photos = []
        for row in cursor.fetchall():
            photo = dict(row)
            if photo['marker_data']:
                try:
                    photo['marker_data'] = json.loads(photo['marker_data'])
                except:
                    photo['marker_data'] = {}
            else:
                photo['marker_data'] = {}
            photos.append(photo)
        
        result = {
            "photos": photos,
            "libraries": libraries
        }
        
        # Create output directory if needed
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
        
        logger.info(f"Exported {len(photos)} photos to {output_path}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error exporting to JSON: {e}")

def clean_database(db_path='photo_library.db'):
    """Clear the photos table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM photos")
        conn.commit()
        conn.close()
        logger.info("Database cleaned")
    except Exception as e:
        logger.error(f"Error cleaning database: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process photos for heatmap')
    parser.add_argument('--init', action='store_true', help='Initialize the database')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--export', action='store_true', help='Export database to JSON')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--output', default='photo_heatmap_data.json', help='Output JSON file path')
    parser.add_argument('--workers', type=int, default=None, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--export-all', action='store_true', help='Export all photos to JSON')
    parser.add_argument('--clean', action='store_true', help='Clean database before processing')
    parser.add_argument('--library', default='Default', help='Library name for imported photos')
    
    args = parser.parse_args()
    
    if args.init:
        try:
            from init_db import create_database
            create_database(args.db)
        except ImportError:
            logger.error("init_db.py not found")
    
    if args.clean:
        clean_database(args.db)
    
    if args.process:
        process_directory_incremental(
            root_dir=args.process,
            db_path=args.db,
            max_workers=args.workers,
            include_all=args.include_all,
            library_name=args.library
        )
    
    if args.export:
        export_to_json(args.db, args.output, include_non_geotagged=args.export_all)
