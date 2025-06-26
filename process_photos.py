import sqlite3
import os
import json
import argparse
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import hashlib
import concurrent.futures
import sys
import logging
import time
import multiprocessing
import pickle
import shelve
import pathlib
from functools import partial
from contextlib import closing

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Additional GPS data extraction libraries
# Install with: pip install piexif exifread
try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    logger.debug("piexif not installed, advanced GPS extraction will be limited")
    HAS_PIEXIF = False
    
try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    logger.debug("exifread not installed, fallback GPS extraction will be limited")
    HAS_EXIFREAD = False

# Try to import the HEIC support library
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIF/HEIC support enabled")
    HEIC_SUPPORT = True
except ImportError:
    logger.warning("pillow-heif not installed. HEIC files will not be processed.")
    logger.warning("To enable HEIC support, install with: pip install pillow-heif")
    HEIC_SUPPORT = False

def get_image_hash(image_path):
    """Create a simple hash of the image file to identify duplicates"""
    try:
        # Import our optimized performance functions if available
        try:
            from optimize_performance import fast_file_hash_cached
            return fast_file_hash_cached(image_path)
        except ImportError:
            # Fall back to the original method
            with open(image_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing file {image_path}: {e}")
        return None

def fast_hash(image_path):
    """Fast file hash implementation that tries to use the optimized version if available"""
    try:
        # Try to use the optimized version from performance_helpers
        from performance_helpers import fast_file_hash_cached
        return fast_file_hash_cached(image_path)
    except ImportError:
        # Fall back to standard implementation if module not available
        return get_image_hash(image_path)

def get_exif_data(img):
    """Get EXIF data from an image, handling different image types"""
    if hasattr(img, 'getexif'):  # Newer versions of PIL or regular image formats
        return img.getexif()
    elif hasattr(img, '_getexif'):  # Older versions of PIL
        return img._getexif()
    else:
        # HEIC and other formats might not have these methods
        return None

def extract_datetime(image_path):
    """Extract the datetime from image EXIF data"""
    # Check if the file is a HEIC file and we don't have HEIC support
    if image_path.lower().endswith('.heic') and not HEIC_SUPPORT:
        logger.warning(f"Skipping datetime extraction for {image_path}: HEIC support not enabled")
        # Fall back to file creation time for HEIC files
        file_time = os.path.getctime(image_path)
        return datetime.fromtimestamp(file_time).isoformat()
        
    try:
        with Image.open(image_path) as img:
            # Get EXIF data using our helper function
            exif_data = get_exif_data(img)
            
            if not exif_data:
                # For HEIC files, try to get creation date from file metadata
                if image_path.lower().endswith('.heic'):
                    logger.debug(f"No EXIF data found for HEIC file {image_path}, checking file metadata")
                
                # No EXIF data found, fall back to file creation time
                file_time = os.path.getctime(image_path)
                logger.debug(f"Using file creation time for {image_path}")
                return datetime.fromtimestamp(file_time).isoformat()
            
            # Search for date info in EXIF    
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    # Convert EXIF datetime format to ISO format
                    dt = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    return dt.isoformat()
            
            # If DateTimeOriginal not found, use file creation time
            file_time = os.path.getctime(image_path)
            return datetime.fromtimestamp(file_time).isoformat()
    except Exception as e:
        logger.error(f"Error extracting datetime from {image_path}: {e}")
        # Fall back to file creation time as a last resort
        try:
            file_time = os.path.getctime(image_path)
            return datetime.fromtimestamp(file_time).isoformat()
        except:
            return None

def get_decimal_from_dms(dms, ref):
    """Convert GPS DMS (Degrees, Minutes, Seconds) to decimal format"""
    try:
        # Handle different formats of DMS data
        if isinstance(dms, tuple) or isinstance(dms, list):
            # Check if we have a tuple of tuples (rational numbers)
            if len(dms) >= 3 and all(isinstance(x, tuple) for x in dms[:3]):
                # Handle rational numbers: (numerator, denominator)
                degrees = float(dms[0][0]) / float(dms[0][1]) if dms[0][1] != 0 else 0
                minutes = float(dms[1][0]) / float(dms[1][1]) / 60.0 if dms[1][1] != 0 else 0
                seconds = float(dms[2][0]) / float(dms[2][1]) / 3600.0 if dms[2][1] != 0 else 0
                decimal = degrees + minutes + seconds
            # Standard format: [degrees, minutes, seconds]
            elif len(dms) >= 3:
                degrees = float(dms[0])
                minutes = float(dms[1]) / 60.0
                seconds = float(dms[2]) / 3600.0
                decimal = degrees + minutes + seconds
            elif len(dms) == 2:
                # Some formats only provide degrees and minutes
                degrees = float(dms[0])
                minutes = float(dms[1]) / 60.0
                decimal = degrees + minutes
            else:
                # If we only have degrees
                decimal = float(dms[0])
        elif isinstance(dms, (int, float)):
            # Some formats might already provide decimal degrees
            decimal = float(dms)
        else:
            # Unsupported format
            logger.error(f"Unsupported GPS data format: {type(dms)} - {dms}")
            return None
        
        # Apply the reference direction (N/S/E/W)
        if ref and (ref == 'S' or ref == 'W' or ref == b'S' or ref == b'W'):
            decimal = -decimal
        
        return decimal
    except Exception as e:
        logger.error(f"Error converting GPS coordinates: {e}, data: {dms}, ref: {ref}")
        return None

def extract_gps(image_path):
    """Extract GPS coordinates from an image's EXIF data"""
    # Check if the file is a HEIC file and we don't have HEIC support
    if image_path.lower().endswith('.heic') and not HEIC_SUPPORT:
        logger.warning(f"Skipping GPS extraction for {image_path}: HEIC support not enabled")
        return None, None
        
    try:
        with Image.open(image_path) as img:
            # Get EXIF data using our helper function
            exif_data = get_exif_data(img)
            
            if not exif_data:
                logger.debug(f"No EXIF data found in {image_path}")
                return None, None
                
            gps_info = {}
            
            # Special handling for HEIC files
            is_heic = image_path.lower().endswith('.heic')
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'GPSInfo':
                    logger.debug(f"Found GPSInfo tag: {tag_id}")
                    logger.debug(f"GPS value type: {type(value)}")
                    
                    # Handle different GPS data formats
                    try:
                        if isinstance(value, dict):
                            # Some implementations might return a dictionary directly
                            logger.debug("Dictionary format")
                            gps_info = value
                        elif isinstance(value, int):
                            # Sometimes GPSInfo is stored as an integer reference
                            # This is a known issue with some Samsung phones like Galaxy S24+
                            logger.debug(f"Integer format: {value} - using direct GPS extraction method")
                            # We need to try a different approach for these files                            # Try to get GPS data directly from EXIF
                            if HAS_PIEXIF:
                                try:
                                    with open(image_path, 'rb') as f:
                                        exif_dict = piexif.load(f.read())
                                        if 'GPS' in exif_dict and exif_dict['GPS']:
                                            # Map the GPS data
                                            for gps_tag, val in exif_dict['GPS'].items():
                                                gps_info[GPSTAGS.get(gps_tag, gps_tag)] = val
                                            logger.debug(f"Direct GPS extraction found: {len(gps_info)} items")
                                except Exception as e:
                                    logger.debug(f"Direct GPS extraction failed: {e}")
                        else:
                            # Standard format where value is a dictionary-like object
                            logger.debug("Standard format")
                            for gps_tag in value:
                                gps_info[GPSTAGS.get(gps_tag, gps_tag)] = value[gps_tag]
                    except TypeError as e:
                        # If we get a TypeError (like 'int' object is not iterable)
                        logger.debug(f"Error inspecting GPS data: {e}")
                        if is_heic:
                            # For HEIC files, try alternative extraction method
                            logger.debug("Using alternative method for HEIC GPS extraction")
            
            logger.debug(f"Extracted GPS info: {gps_info}")
            
            if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                try:
                    lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
                    lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
                    logger.debug(f"Converted GPS coordinates: {lat}, {lon}")
                    return lat, lon
                except Exception as e:
                    logger.error(f"Error converting GPS coordinates: {e}")
                    return None, None
            else:                # Try one more fallback method for Samsung phones specifically
                if HAS_EXIFREAD:
                    try:
                        with open(image_path, 'rb') as f:
                            tags = exifread.process_file(f)
                            if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                                lat_ref = str(tags.get('GPS GPSLatitudeRef', 'N'))
                                lon_ref = str(tags.get('GPS GPSLongitudeRef', 'E'))
                                
                                lat = tags['GPS GPSLatitude'].values
                                lon = tags['GPS GPSLongitude'].values
                                
                                # Convert to decimal degrees
                                lat_val = float(lat[0].num) / float(lat[0].den) + \
                                      float(lat[1].num) / float(lat[1].den) / 60 + \
                                      float(lat[2].num) / float(lat[2].den) / 3600
                                      
                                lon_val = float(lon[0].num) / float(lon[0].den) + \
                                      float(lon[1].num) / float(lon[1].den) / 60 + \
                                      float(lon[2].num) / float(lon[2].den) / 3600
                                      
                                if lat_ref == 'S':
                                    lat_val = -lat_val
                                if lon_ref == 'W':
                                    lon_val = -lon_val
                                    
                                logger.debug(f"Extracted GPS via exifread: {lat_val}, {lon_val}")
                                return lat_val, lon_val
                    except Exception as e:
                        logger.debug(f"Fallback GPS extraction failed: {e}")
                    pass
    except Exception as e:
        logger.error(f"Error extracting GPS data from {image_path}: {e}")
    
    return None, None

def process_image(image_path):
    """Process a single image and return its metadata"""
    try:
        # Use faster path operations
        filename = os.path.basename(image_path)
        
        # Fast-fail for non-existent files (prevents unnecessary work)
        if not os.path.exists(image_path):
            logger.debug(f"Skipping non-existent file: {image_path}")
            return None
            
        # Set a file size limit to prevent memory issues with huge files (>100MB)
        try:
            file_size = os.path.getsize(image_path)
            file_size_mb = file_size / (1024 * 1024)
            if file_size_mb > 100:
                logger.warning(f"Skipping oversized file: {filename} ({file_size_mb:.1f} MB)")
                # Return basic information without GPS or datetime for oversized files
                return {
                    'filename': filename,
                    'path': image_path,
                    'latitude': None,
                    'longitude': None,
                    'datetime': None,
                    'hash': get_image_hash(image_path)  # Use optimized hash function
                }
        except OSError:
            pass  # Continue if we can't check file size
            
        # Skip unsupported files if HEIC support is not available
        if filename.lower().endswith('.heic') and not HEIC_SUPPORT:
            logger.debug(f"Skipping HEIC file {filename} - install pillow-heif for HEIC support")
            # Return basic information without GPS or datetime
            return {
                'filename': filename,
                'path': image_path,
                'latitude': None,
                'longitude': None,
                'datetime': None,
                'hash': get_image_hash(image_path)  # Use optimized hash function
            }
        
        # Handle DNG files which Pillow may not be able to open directly
        if filename.lower().endswith('.dng'):
            # Try to get basic info without opening with Pillow
            hash_value = get_image_hash(image_path)
            try:
                file_time = os.path.getctime(image_path)
                dt = datetime.fromtimestamp(file_time).isoformat()
            except:
                dt = None
            
            # For DNG files, try using exifread for GPS data
            lat, lon = None, None
            if HAS_EXIFREAD:
                try:
                    with open(image_path, 'rb') as f:
                        tags = exifread.process_file(f)
                        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                            lat_ref = str(tags.get('GPS GPSLatitudeRef', 'N'))
                            lon_ref = str(tags.get('GPS GPSLongitudeRef', 'E'))
                            
                            lat = tags['GPS GPSLatitude'].values
                            lon = tags['GPS GPSLongitude'].values
                            
                            # Convert to decimal degrees
                            lat_val = float(lat[0].num) / float(lat[0].den) + \
                                  float(lat[1].num) / float(lat[1].den) / 60 + \
                                  float(lat[2].num) / float(lat[2].den) / 3600
                                  
                            lon_val = float(lon[0].num) / float(lon[0].den) + \
                                  float(lon[1].num) / float(lon[1].den) / 60 + \
                                  float(lon[2].num) / float(lon[2].den) / 3600
                                  
                            if lat_ref == 'S':
                                lat_val = -lat_val
                            if lon_ref == 'W':
                                lon_val = -lon_val
                                
                            logger.debug(f"Extracted DNG GPS via exifread: {lat_val}, {lon_val}")
                            lat, lon = lat_val, lon_val
                except Exception as e:
                    logger.debug(f"DNG GPS extraction failed: {e}")
            
            return {
                'filename': filename,
                'path': image_path,
                'latitude': lat,
                'longitude': lon,
                'datetime': dt,
                'hash': hash_value
            }
            
        # Continue processing for supported files
        lat, lon = extract_gps(image_path)
        dt = extract_datetime(image_path)
        img_hash = get_image_hash(image_path)
        
        return {
            'filename': filename,
            'path': image_path,
            'latitude': lat,
            'longitude': lon,
            'datetime': dt,
            'hash': img_hash
        }
    except Exception as e:
        logger.error(f"Error processing {image_path}: {e}")
        return None

def get_or_create_library(cursor, library_name, source_dirs=None, description=None):
    """Get an existing library or create a new one"""
    # Check if library exists
    cursor.execute("SELECT id FROM libraries WHERE name = ?", (library_name,))
    result = cursor.fetchone()
    
    if result:
        library_id = result[0]
        # Update source_dirs if provided
        if source_dirs:
            source_dirs_json = json.dumps(source_dirs)
            cursor.execute("UPDATE libraries SET source_dirs = ? WHERE id = ?", 
                          (source_dirs_json, library_id))
        return library_id
    else:
        # Create new library
        source_dirs_json = json.dumps(source_dirs or [])
        cursor.execute(
            "INSERT INTO libraries (name, description, source_dirs) VALUES (?, ?, ?)",
            (library_name, description or "", source_dirs_json)
        )
        return cursor.lastrowid

def create_marker_data(photo):
    """Create marker-specific data for a photo"""
    # Extract year and month for clustering
    date_obj = None
    if photo.get('datetime'):
        try:
            date_obj = datetime.fromisoformat(photo['datetime'])
        except (ValueError, TypeError):
            pass
    
    marker_data = {
        "popup_text": photo.get('filename', 'Unknown'),
        "cluster_group": f"{date_obj.year}-{date_obj.month:02d}" if date_obj else "unknown",
        "has_thumbnail": False  # Will be set to True when thumbnails are generated
    }
    
    return json.dumps(marker_data)

def process_directory(root_dir, db_path='photo_library.db', max_workers=None, include_all=False, 
                     skip_existing=True, library_name="Default"):
    """Process all images in a directory and its subdirectories"""
    # Determine optimal number of workers if not specified
    if max_workers is None:
        try:
            from performance_helpers import get_optimal_worker_count
            max_workers = get_optimal_worker_count('cpu')
            logger.info(f"Using auto-configured optimal worker count: {max_workers}")
        except ImportError:
            max_workers = min(8, multiprocessing.cpu_count())
            logger.info(f"Using default worker count: {max_workers}")
    
    # Use our improved database connection manager
    try:
        # Import the database connection manager
        from db_connection import DatabaseConnectionManager
        db_manager = DatabaseConnectionManager(db_path)
        db_manager.set_optimizer(optimize_sqlite_connection)
        conn = db_manager.connect()
        logger.info("Using robust database connection manager with auto-reconnection")
    except ImportError:
        # Fall back to standard connection if the module is not available
        logger.info("Database connection manager not available, using standard connection")
        conn = sqlite3.connect(db_path, isolation_level="DEFERRED", check_same_thread=False)
        # Apply SQLite optimizations for better performance
        optimize_sqlite_connection(conn)
    
    cursor = conn.cursor()
    
    # Make sure the libraries table exists
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libraries'")
        if not cursor.fetchone():
            print("Libraries table not found. Creating...")
            cursor.execute('''
            CREATE TABLE libraries (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT,
              source_dirs TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              last_updated TEXT
            )
            ''')
    except sqlite3.Error as e:
        print(f"Error checking libraries table: {e}")
    
    # Make sure the marker_data column exists in photos table
    try:
        cursor.execute("PRAGMA table_info(photos)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "marker_data" not in columns:
            print("Adding marker_data column to photos table...")
            cursor.execute("ALTER TABLE photos ADD COLUMN marker_data TEXT")
        
        if "library_id" not in columns:
            print("Adding library_id column to photos table...")
            cursor.execute("ALTER TABLE photos ADD COLUMN library_id INTEGER REFERENCES libraries(id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_library_id ON photos(library_id)")
    except sqlite3.Error as e:
        print(f"Error updating photos table: {e}")
    
    # Get or create the library
    library_id = get_or_create_library(cursor, library_name, [root_dir])
    conn.commit()
    
    print(f"Using library: {library_name} (ID: {library_id})")
      
    # Get list of all image files
    image_files = []
    image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
    
    print(f"Scanning directory: {root_dir}")
    print("Looking for files with these extensions:", ", ".join(image_extensions))
    
    if not os.path.exists(root_dir):
        print(f"ERROR: Directory does not exist: {root_dir}")
        return
    
    # List subdirectories to help with debugging
    print("Subdirectories found:")
    for item in os.listdir(root_dir):
        full_path = os.path.join(root_dir, item)
        if os.path.isdir(full_path):
            print(f"  - {item}")
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Print current directory being processed
        rel_path = os.path.relpath(dirpath, root_dir)
        if rel_path != '.':
            print(f"Scanning: {rel_path}")
        
        for filename in filenames:
            if filename.lower().endswith(image_extensions):
                full_path = os.path.join(dirpath, filename)
                image_files.append(full_path)
    
    total_files = len(image_files)
    print(f"Found {total_files} image files. Starting processing...")
      # Create a file index if we're using incremental updates
    if skip_existing:
        print("Creating file index for incremental update...")
        file_index = get_file_index(cursor)
        print(f"Found {len(file_index)} existing photos in database")
    else:
        file_index = {}
    
    # Filter image files to only include new or modified files
    to_process = []
    skipped_count = 0
    for img_path in image_files:
        filename = os.path.basename(img_path)
        if skip_existing and filename in file_index:
            # Check file modification time to see if it's changed
            mtime = os.path.getmtime(img_path)
            file_date = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            db_path = file_index.get(filename)
            
            # Skip if path matches and file hasn't changed
            if db_path == img_path:
                skipped_count += 1
                continue
        
        to_process.append(img_path)
    
    print(f"Skipping {skipped_count} existing files. Processing {len(to_process)} new or modified images...")
      # Process images in parallel using batches for better performance
    processed_count = 0
    inserted_count = 0
    
    # Calculate optimal batch size for processing
    try:
        from performance_helpers import optimize_batch_processing
        batch_size = optimize_batch_processing(500)  # Start with 500 as default
        logger.info(f"Using optimized batch size: {batch_size}")
    except ImportError:
        # Use a reasonable default if helper not available
        batch_size = 500  # Increased batch size for faster processing
        logger.info(f"Using default batch size: {batch_size}")
    
    # Start timing for performance metrics
    batch_start_time = time.time()
    for i in range(0, len(to_process), batch_size):
        batch = to_process[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(to_process) + batch_size - 1)//batch_size} ({len(batch)} images)...")
        
        # Use thread pool for image processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    
                    # Log progress less frequently to reduce overhead
                    if processed_count % 50 == 0 or processed_count == len(to_process):
                        elapsed = time.time() - batch_start_time
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        print(f"Processed {processed_count}/{len(to_process)} images... ({rate:.1f} images/sec)")
                    
                    if result:
                        # If include_all is True, keep all photos regardless of GPS data
                        # Otherwise, only keep photos with GPS coordinates
                        if include_all or (result['latitude'] and result['longitude']):
                            # Create marker data
                            result['marker_data'] = create_marker_data(result)
                            result['library_id'] = library_id
                            batch_results.append(result)
                except Exception as e:
                    print(f"Error with {path}: {e}")        # Batch insert the results with robust database handling
        if batch_results:
            # Use more efficient batch insert with executemany
            max_attempts = 3
            attempt = 0
            success = False
            
            while attempt < max_attempts and not success:
                try:
                    attempt += 1
                    # Check if we're using the database manager
                    if 'db_manager' in locals():
                        # Use robust connection manager
                        logger.debug(f"Using database manager for batch insert (attempt {attempt}/{max_attempts})")
                        cursor = conn.cursor()
                        cursor.executemany(
                            "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            [(photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                              photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data']) for photo in batch_results]
                        )
                        inserted_this_batch = len(batch_results)
                        inserted_count += inserted_this_batch
                        db_manager.commit_with_retry()
                    else:
                        # Make sure connection is still valid
                        if conn is None or not hasattr(conn, 'execute'):
                            logger.warning("Database connection lost, reconnecting...")
                            conn = sqlite3.connect(db_path, isolation_level="DEFERRED", check_same_thread=False)
                            cursor = conn.cursor()
                            optimize_sqlite_connection(conn)
                        else:
                            cursor = conn.cursor()
                        
                        # Insert data safely
                        cursor.executemany(
                            "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            [(photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                              photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data']) for photo in batch_results]
                        )
                        inserted_this_batch = len(batch_results)
                        inserted_count += inserted_this_batch
                        conn.commit()
                      # Success! Break the retry loop
                    success = True
                      # Calculate and display insertion rate
                    elapsed = time.time() - batch_start_time
                    rate = inserted_count / elapsed if elapsed > 0 else 0
                    print(f"Inserted {inserted_count} photos so far ({rate:.1f} inserts/sec)")
                except (sqlite3.OperationalError, sqlite3.ProgrammingError, sqlite3.DatabaseError) as e:
                    error_str = str(e).lower()
                    if "closed database" in error_str or "not a database" in error_str or "database is locked" in error_str:
                        if attempt < max_attempts:
                            logger.warning(f"Database error: {e}, retrying (attempt {attempt}/{max_attempts})...")
                            time.sleep(1)  # Wait before retrying
                            
                            # Try to reconnect if we're not using the connection manager
                            if 'db_manager' not in locals():
                                try:
                                    if conn:
                                        try:
                                            conn.close()
                                        except:
                                            pass
                                    conn = sqlite3.connect(db_path, isolation_level="DEFERRED", check_same_thread=False, timeout=30.0)
                                    optimize_sqlite_connection(conn)
                                except Exception as conn_err:
                                    logger.error(f"Error reconnecting to database: {conn_err}")
                        else:
                            # If we've reached max attempts, fall back to individual inserts
                            logger.error(f"Failed to insert batch after {max_attempts} attempts: {e}")
                            
                            # Try to ensure we have a valid connection
                            try:
                                if 'db_manager' in locals():
                                    conn = db_manager.connect()
                                else:
                                    if conn:
                                        try:
                                            conn.close()
                                        except:
                                            pass
                                    conn = sqlite3.connect(db_path, isolation_level="DEFERRED", check_same_thread=False, timeout=30.0)
                                    optimize_sqlite_connection(conn)
                                    
                                cursor = conn.cursor()
                                
                                # Try one by one to avoid losing too much data
                                logger.info("Falling back to individual inserts...")
                                success_count = 0
                                for photo in batch_results:
                                    try:
                                        cursor.execute(
                                            "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                            (photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                                             photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
                                        )
                                        success_count += 1
                                        
                                        # Commit every 10 records to avoid large transactions
                                        if success_count % 10 == 0:
                                            conn.commit()
                                    except sqlite3.IntegrityError:
                                        # Skip duplicates
                                        pass
                                    except Exception as insert_err:
                                        logger.error(f"Error inserting photo {photo['path']}: {insert_err}")
                                
                                # Final commit
                                conn.commit()
                                logger.info(f"Individual inserts completed: {success_count}/{len(batch_results)} successful")
                                inserted_count += success_count
                                print(f"Reconnected and inserted {success_count} photos individually.")
                                
                                # Skip the remaining attempts in the batch loop
                                success = True
                                
                            except Exception as recovery_err:
                                logger.error(f"Failed to recover database connection: {recovery_err}")
                                # Skip the remaining attempts in the batch loop
                                success = True
                    else:
                        logger.error(f"SQLite error: {e}")
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
                            inserted_count += 1
                            if success_count % 10 == 0:
                                conn.commit()  # Commit in smaller batches                        except sqlite3.IntegrityError:
                            # Skip duplicates
                            pass
                        except Exception as e:
                            logger.error(f"Error inserting photo {photo['path']}: {e}")
                    
                    # Final batch commit
                    try:
                        conn.commit()
                    except Exception as commit_e:
                        logger.error(f"Error during commit: {commit_e}")
                  # Final commit - wrapped in try/except to avoid issues        
            try:
                if conn is not None and hasattr(conn, 'commit'):
                    conn.commit()
                    conn.close()
                print(f"Processing complete. {processed_count} images processed, {inserted_count} images inserted into database.")
                
                # Record the processing timestamp for this library
                data_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else './data'
                record_processing_time(library_name, data_dir)
            except Exception as e:
                logger.error(f"Error during final database operations: {e}")
                print(f"Processing completed with some errors. {processed_count} images processed, approximately {inserted_count} inserted.")
                # Try to ensure the connection is closed
                try:
                    if conn is not None and hasattr(conn, 'close'):
                        conn.close()
                except:
                    pass

def export_to_json(db_path='photo_library.db', output_path='photo_heatmap_data.json', include_non_geotagged=False):
    """
    [LEGACY FUNCTION] Export the database to JSON format for the heatmap visualization
    
    This function is maintained for backward compatibility only.
    The application now uses the SQLite database directly instead of JSON files.
    """
    print("WARNING: JSON export is no longer needed as the application uses SQLite database directly")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get database stats for informational purposes
    cursor.execute("SELECT COUNT(*) FROM photos")
    total_photos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    geotagged_photos = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM libraries")
    total_libraries = cursor.fetchone()[0]
    
    print(f"Database at {db_path} contains:")
    print(f"- {total_photos} total photos")
    print(f"- {geotagged_photos} photos with GPS data")
    print(f"- {total_libraries} libraries")
    print(f"JSON export skipped - SQLite database is used directly")
    
    # Create a minimal JSON file for compatibility
    if output_path:
        try:
            # Ensure the directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Create a minimal JSON structure with deprecation notice
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('{"photos":[],"libraries":[],"note":"This file is deprecated. Use SQLite database directly."}')
                
            print(f"Created placeholder JSON file at {output_path} for compatibility")
        except Exception as e:
            print(f"Error creating placeholder JSON: {e}")
    
    conn.close()
def photo_exists_in_db(cursor, filename=None, img_hash=None, path=None):
    """Check if a photo already exists in the database based on hash, filename, or path"""
    if img_hash:
        cursor.execute("SELECT COUNT(*) FROM photos WHERE hash = ?", (img_hash,))
        if cursor.fetchone()[0] > 0:
            return True
    
    if path:
        cursor.execute("SELECT COUNT(*) FROM photos WHERE path = ?", (path,))
        if cursor.fetchone()[0] > 0:
            return True
    
    if filename:
        cursor.execute("SELECT COUNT(*) FROM photos WHERE filename = ?", (filename,))
        if cursor.fetchone()[0] > 0:
            return True
    
    return False

def clean_database(db_path='photo_library.db'):
    """Remove all entries from the photos table"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if photos table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'")
    if not cursor.fetchone():
        print("No photos table found. Nothing to clean.")
        conn.close()
        return
    
    # Get current count
    cursor.execute("SELECT COUNT(*) FROM photos")
    count = cursor.fetchone()[0]
    
    # Delete all records
    cursor.execute("DELETE FROM photos")
    conn.commit()
    
    # Reset auto-increment if the sqlite_sequence table exists
    # This table is only created once you've inserted a row with an autoincrement field
    try:
        # Check if sqlite_sequence table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
        if cursor.fetchone():
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='photos'")
            conn.commit()
    except sqlite3.Error as e:
        print(f"Note: Could not reset sequence: {e}")
    
    conn.close()
    print(f"Removed {count} photos from database")

def optimize_sqlite_connection(conn):
    """Apply performance optimizations to the SQLite connection"""
    try:
        # Try to use the optimized version from the performance module
        try:
            from optimize_performance import optimize_sqlite_connection as optimized_sqlite
            
            # Get database file size if available
            db_size_mb = None
            if hasattr(conn, 'execute'):
                try:
                    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
                    if db_path and os.path.exists(db_path):
                        db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
                except:
                    pass
                    
            settings = optimized_sqlite(conn, file_size_mb=db_size_mb)
            logger.info(f"Applied advanced SQLite optimizations: {settings}")
            return settings
            
        except ImportError:
            # Fall back to the original optimization code
            # Enable WAL (Write-Ahead Logging) mode - greatly improves concurrent write performance
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Set cache size to 20000 pages (about 80MB with default page size) - increased for better performance
            conn.execute("PRAGMA cache_size=20000")
            
            # Configure other performance settings
            conn.execute("PRAGMA synchronous=NORMAL")  # Less safe but faster than FULL
            conn.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory
            conn.execute("PRAGMA mmap_size=536870912") # Use memory mapping (512MB) - increased
            
            # Additional optimizations
            conn.execute("PRAGMA page_size=4096")      # Larger page size for better performance
            conn.execute("PRAGMA count_changes=OFF")   # Disable count_changes for better performance
            conn.execute("PRAGMA case_sensitive_like=OFF")
            
            # For heavy inserts
            conn.isolation_level = 'DEFERRED'          # Better transaction handling
            
            logger.info("Enhanced SQLite optimizations applied")
        
        # Return current settings for debugging
        settings = {}
        for pragma in ["journal_mode", "cache_size", "synchronous", "temp_store", "mmap_size", "page_size"]:
            settings[pragma] = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
        return settings
    except Exception as e:
        logger.warning(f"Failed to apply some SQLite optimizations: {e}")
        return {}

def create_directory_hash(dir_path):
    """Create a hash representing the directory contents and modification times"""
    dir_hash = hashlib.md5()
    for root, dirs, files in os.walk(dir_path):
        # Add folder path
        dir_hash.update(root.encode())
        
        # Add file names and modification times
        for file in sorted(files):  # Sort for consistent results
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')):
                full_path = os.path.join(root, file)
                try:
                    mtime = str(os.path.getmtime(full_path))
                    dir_hash.update(f"{file}{mtime}".encode())
                except OSError:
                    pass  # Skip files with access issues
    
    return dir_hash.hexdigest()

def get_directory_cache(cache_path):
    """Load cached directory information if available"""
    if not os.path.exists(cache_path):
        return {}
    
    try:
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"Failed to load directory cache: {e}")
        return {}

def save_directory_cache(cache_path, cache_data):
    """Save directory information to cache file"""
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'wb') as f:
            pickle.dump(cache_data, f)
        logger.info(f"Directory cache saved to {os.path.dirname(cache_path)}")
    except Exception as e:
        logger.warning(f"Failed to save directory cache: {e}")

# We'll use the scan_functions.py module to handle parallel scanning
try:
    from scan_functions import scan_directory_parallel as external_scan
    from scan_functions import _scan_single_directory
    HAS_PARALLEL_SCAN = True
    logger.info("Using external scan_functions module for parallel scanning")
except ImportError:
    HAS_PARALLEL_SCAN = False
    logger.warning("scan_functions.py module not found, parallel scan functionality disabled")

def scan_directory_parallel(root_dir, image_extensions, existing_paths=None):
    """Scan a directory for image files in parallel using multiprocessing"""
    # Try to import scan_functions.py which has properly defined multiprocessing-safe functions
    try:
        from scan_functions import scan_directory_parallel as external_scan
        logger.info("Using external scan_functions module for parallel scanning")
        return external_scan(root_dir, image_extensions, existing_paths)
    except ImportError:
        logger.warning("scan_functions.py module not found, falling back to serial scanning")
        
        # Fall back to serial scanning if module not found
        if existing_paths is None:
            existing_paths = set()
            
        new_files = []
        total_files = 0
        
        # Traditional serial scanning method
        for dirpath, _, filenames in os.walk(root_dir):
            rel_path = os.path.relpath(dirpath, root_dir)
            if rel_path != '.' and total_files % 1000 == 0:
                logger.info(f"Scanning: {rel_path}")
                
            for filename in filenames:
                if filename.lower().endswith(image_extensions):
                    total_files += 1
                    full_path = os.path.join(dirpath, filename)
                    
                    # Skip if file already exists in database (by path)
                    if full_path not in existing_paths:
                        new_files.append(full_path)
        
        return new_files, total_files

def create_checkpoint(checkpoint_file, processed_files, current_batch=None):
    """Save checkpoint information to resume processing if interrupted"""
    try:
        with open(checkpoint_file, 'wb') as f:
            pickle.dump({
                'processed_files': processed_files,
                'current_batch': current_batch,
                'timestamp': datetime.now().isoformat()
            }, f)
        logger.debug(f"Checkpoint saved: {len(processed_files)} files processed")
    except Exception as e:
        logger.warning(f"Failed to create checkpoint: {e}")

def load_checkpoint(checkpoint_file):
    """Load checkpoint information to resume processing"""
    if not os.path.exists(checkpoint_file):
        logger.info("No checkpoint file found")
        return None
    
    try:
        with open(checkpoint_file, 'rb') as f:
            checkpoint = pickle.load(f)
        logger.info(f"Resuming from checkpoint: {len(checkpoint['processed_files'])} files already processed")
        return checkpoint
    except Exception as e:
        logger.warning(f"Failed to load checkpoint: {e}")
        return None
def batch_insert_photos(cursor, batch):
    """Insert a batch of photos into the database"""
    inserted = 0
    for photo in batch:
        try:
            cursor.execute(
                "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data'])
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Skip duplicates
            pass
        except Exception as e:
            logger.error(f"Error inserting photo {photo['path']}: {e}")
    
    return inserted

def process_directory_incremental(root_dir, db_path='photo_library.db', max_workers=None, include_all=False, 
                          library_name="Default", use_cache=True, resume=True, use_parallel_scan=True):
    """Fast incremental processing with optimizations:
    - Uses multiprocessing for parallel directory scanning
    - Uses thread pool for parallel image processing
    - Optional directory cache for avoiding redundant scans
    - SQLite optimizations (WAL mode, memory settings)
    - Resume capability for interrupted operations
    - Directory change detection to skip unchanged directories
    - Optimized batch sizes for better performance    - Fast file hashing without loading entire files into memory
    """
    
    start_time = time.time()
      # Normalize and validate the directory
    root_dir = normalize_path(root_dir)
    
    # Try to handle Docker volume mount paths
    if not os.path.isdir(root_dir) and '/photos/' in root_dir:
        # Check available directories to help debugging
        parent_dir = os.path.dirname(root_dir)
        if os.path.exists(parent_dir):
            logger.info(f"Parent directory exists. Contents of {parent_dir}:")
            try:
                for item in os.listdir(parent_dir):
                    logger.info(f"  - {item}")
            except Exception as e:
                logger.error(f"Could not list parent directory: {e}")
    
    # Final check after normalization
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    logger.info(f"Starting optimized incremental scan of {root_dir}")
    
    # Ensure the database is initialized
    ensure_database_initialized(db_path)
      # Try to use optimized performance settings
    try:
        # First try the simple performance helpers module
        try:
            from performance_helpers import get_optimal_worker_count, optimize_batch_processing, PerformanceMonitor
            logger.info("Using performance_helpers module")
        except ImportError:
            # Then try the full optimization module
            from optimize_performance import get_optimal_worker_count, optimize_batch_processing, PerformanceMonitor
            logger.info("Using optimize_performance module")
            
        # Auto-determine optimal number of worker threads if not specified
        if max_workers is None:
            max_workers = get_optimal_worker_count(task_type='io')
            logger.info(f"Auto-configured worker count: {max_workers}")
        
        # Get optimal batch sizes based on available memory
        try:
            processing_batch_size, db_batch_size = optimize_batch_processing(batch_size=100)
        except TypeError:
            # Simple version might return just one value
            processing_batch_size = optimize_batch_processing(batch_size=100)
            db_batch_size = processing_batch_size
            
        logger.info(f"Auto-configured batch sizes: processing={processing_batch_size}, db={db_batch_size}")
        
        # Create performance monitor
        performance_monitor = PerformanceMonitor("Image processing")
        
    except ImportError:
        # Fall back to default values
        logger.info("Performance optimization modules not available, using default settings")
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 8)
        processing_batch_size = 250
        db_batch_size = 250
        processing_batch_size = 100
        db_batch_size = 100
        performance_monitor = None
        
    logger.info(f"Using worker count: {max_workers}, processing batch size: {processing_batch_size}, "
               f"DB batch size: {db_batch_size}")
        
    # Prepare cache and checkpoint files
    workspace_dir = os.path.join(os.path.dirname(db_path), '.workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    cache_path = os.path.join(workspace_dir, 'directory_cache.pkl')
    checkpoint_path = os.path.join(workspace_dir, 'process_checkpoint.pkl')
    
    # Connect to database with optimizations
    conn = sqlite3.connect(db_path)
    
    # Apply SQLite optimizations
    optimization_settings = optimize_sqlite_connection(conn)
    logger.info(f"SQLite optimization settings applied")
    
    cursor = conn.cursor()
    
    # Create tables if they don't exist and make sure we have a library
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS libraries (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          description TEXT,
          source_dirs TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          last_updated TEXT
        )
        ''')
    except sqlite3.Error as e:
        logger.error(f"Error checking libraries table: {e}")
    
    # Make sure the marker_data column exists in photos table
    try:
        cursor.execute("PRAGMA table_info(photos)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "marker_data" not in columns:
            logger.info("Adding marker_data column to photos table...")
            cursor.execute("ALTER TABLE photos ADD COLUMN marker_data TEXT")
        
        if "library_id" not in columns:
            logger.info("Adding library_id column to photos table...")
            cursor.execute("ALTER TABLE photos ADD COLUMN library_id INTEGER REFERENCES libraries(id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_library_id ON photos(library_id)")
    except sqlite3.Error as e:
        logger.error(f"Error updating photos table: {e}")
    
    # Get or create the library
    library_id = get_or_create_library(cursor, library_name, [root_dir])
    conn.commit()
    
    logger.info(f"Using library: {library_name} (ID: {library_id})")
    
    # Define image extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
    
    # Load checkpoint if resume is enabled
    checkpoint = None
    processed_files = set()
    if resume:
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint:
            processed_files = set(checkpoint['processed_files'])
            logger.info(f"Resuming from checkpoint with {len(processed_files)} already processed files")
    
    # Create index of paths that already exist in the database
    logger.info("Building database path index for incremental comparison...")
    
    # Use a more efficient approach with a generator to avoid loading all paths into memory at once
    cursor.execute("SELECT path FROM photos")
    existing_paths = set()
    
    # Read in chunks to avoid memory pressure with very large databases
    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            break
        existing_paths.update(row[0] for row in rows)
    
    logger.info(f"Found {len(existing_paths)} files already in database")
    
    # Check if we have a directory cache from previous runs
    dir_cache = {}
    if use_cache:
        dir_cache = get_directory_cache(cache_path)
        logger.info(f"Loaded cache with {len(dir_cache)} directory entries")
    
    # Process directories with directory-level change detection
    new_files = []
    total_files = 0
    unchanged_dirs = 0
    
    # If we have a cache, we can use directory-level change detection
    if use_cache and dir_cache:
        logger.info("Using directory-level change detection...")
        all_dirs = []
        for dirpath, _, _ in os.walk(root_dir):
            all_dirs.append(dirpath)
        
        changed_dirs = []
        for dir_path in all_dirs:
            # Create a hash of the directory contents
            dir_hash = create_directory_hash(dir_path)
            
            # If the directory hasn't changed since last time, skip it
            if dir_path in dir_cache and dir_cache[dir_path] == dir_hash:
                unchanged_dirs += 1
                continue
                
            # Directory has changed or is new, mark for processing
            changed_dirs.append(dir_path)
            dir_cache[dir_path] = dir_hash
        
        logger.info(f"Skipping {unchanged_dirs} unchanged directories. Processing {len(changed_dirs)} changed directories.")
        
        # Only scan the changed directories
        for dir_path in changed_dirs:
            for filename in os.listdir(dir_path):
                if filename.lower().endswith(image_extensions):
                    full_path = os.path.join(dir_path, filename)
                    if os.path.isfile(full_path):
                        total_files += 1
                        if full_path not in existing_paths and full_path not in processed_files:
                            new_files.append(full_path)
    else:
        # Without cache or directory change detection, decide on scanning method
        if use_parallel_scan:
            logger.info("Using parallel directory scanning...")
            new_files, total_files = scan_directory_parallel(
                root_dir, image_extensions, existing_paths.union(processed_files)
            )
        else:
            logger.info("Using serial directory scanning...")
            # Traditional serial scanning method
            total_files = 0
            new_files = []
            for dirpath, _, filenames in os.walk(root_dir):
                rel_path = os.path.relpath(dirpath, root_dir)
                if rel_path != '.' and total_files % 1000 == 0:
                    logger.info(f"Scanning: {rel_path}")
                
                for filename in filenames:
                    if filename.lower().endswith(image_extensions):
                        total_files += 1
                        full_path = os.path.join(dirpath, filename)
                        
                        # Skip if file already exists in database (by path)
                        if full_path not in existing_paths and full_path not in processed_files:
                            new_files.append(full_path)
    
    # Save the updated directory cache
    if use_cache:
        save_directory_cache(cache_path, dir_cache)
    
    logger.info(f"Found {total_files} total files")
    logger.info(f"Found {len(new_files)} new files to process")
    
    if not new_files:
        logger.info("No new files to process. Exiting.")
        conn.close()
        end_time = time.time()
        logger.info(f"Incremental scan completed in {end_time - start_time:.2f} seconds")
        return
    
    # Start performance monitoring if available
    if performance_monitor:
        performance_monitor.start()
    
    # Process new files in parallel with optimized batch size
    processed_count = 0
    inserted_count = 0
    
    logger.info(f"Processing {len(new_files)} new files with {max_workers} workers...")
    
    # Reduce logging frequency during batch processing
    logging.getLogger().setLevel(logging.WARNING)  # Temporarily reduce logging
    
    # Use context manager for thread pooling
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        # Process in optimized batches
        for i in range(0, len(new_files), processing_batch_size):
            batch = new_files[i:i+processing_batch_size]
            
            # Only log every few batches to reduce overhead
            if i % (processing_batch_size * 5) == 0 or i == 0:
                logger.warning(f"Processing batch {i//processing_batch_size + 1}/{(len(new_files) + processing_batch_size - 1)//processing_batch_size} ({len(batch)} images)...")
            
            # Create a checkpoint for this batch if resume is enabled
            if resume:
                create_checkpoint(checkpoint_path, list(processed_files), batch)
            
            # Submit all files in this batch for parallel processing
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    processed_files.add(path)  # Mark as processed for checkpoint
                    
                    # Update performance monitor if available
                    if performance_monitor:
                        performance_monitor.update()
                    
                    # Otherwise log progress periodically
                    elif processed_count % (processing_batch_size // 2) == 0:
                        percent_done = (processed_count / len(new_files)) * 100
                        logger.warning(f"Processed {processed_count}/{len(new_files)} images ({percent_done:.1f}%)...")
                    
                    if result:
                        # If include_all is True, keep all photos regardless of GPS data
                        # Otherwise, only keep photos with GPS coordinates
                        if include_all or (result['latitude'] and result['longitude']):
                            # Add marker data and library ID
                            result['marker_data'] = create_marker_data(result)
                            result['library_id'] = library_id
                            batch_results.append(result)
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")
            
            # Insert batch results to database efficiently
            if batch_results:
                try:
                    # Use more efficient batched insert with executemany
                    cursor.executemany(
                        "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        [(photo['filename'], photo['path'], photo['latitude'], photo['longitude'], 
                          photo['datetime'], photo['hash'], photo['library_id'], photo['marker_data']) for photo in batch_results]
                    )
                    inserted_this_batch = len(batch_results)
                    inserted_count += inserted_this_batch
                    conn.commit()
                except Exception as e:
                    logger.error(f"Error inserting batch: {e}")
                    # Try inserting one by one as fallback
                    inserted_this_batch = batch_insert_photos(cursor, batch_results)
                    inserted_count += inserted_this_batch
                    conn.commit()
    
    # Processing complete, remove checkpoint file if it exists
    if resume and os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
            logger.info("Removed checkpoint file after successful processing")
        except Exception as e:
            logger.warning(f"Could not remove checkpoint file: {e}")
    
    # Restore normal logging
    logging.getLogger().setLevel(logging.INFO)
    
    # Stop performance monitoring and get final stats
    if performance_monitor:
        items_processed, elapsed = performance_monitor.stop()
    
    # Close database connection
    conn.close()
      # Final statistics
    end_time = time.time()
    total_time = end_time - start_time
    logger.info(f"Incremental scan completed in {total_time:.2f} seconds")
    
    if inserted_count > 0 and total_time > 0:
        processing_rate = inserted_count / total_time
        logger.info(f"Overall processing rate: {processing_rate:.2f} photos/second")
    
    logger.info(f"Processed {processed_count} images, inserted {inserted_count} into database")
    
    # Record the processing timestamp for this library
    data_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else './data'
    record_processing_time(library_name, data_dir)

def ensure_database_initialized(db_path):
    """Check if the database exists and has required tables, initialize if needed"""
    db_exists = os.path.exists(db_path)
    
    if not db_exists:
        logger.info(f"Database at {db_path} doesn't exist, creating...")
    else:
        logger.info(f"Database at {db_path} exists, checking tables...")
      # Always ensure tables exist
    ensure_database_tables(db_path)
    return True
    
    conn.close()
    return False

def ensure_database_tables(db_path):
    """Ensure that all necessary tables exist in the database, creating them if needed."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Check if the libraries table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libraries'")
        if not cursor.fetchone():
            logger.info(f"Creating libraries table in {db_path}")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS libraries (
              id INTEGER PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT,
              source_dirs TEXT,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              last_updated TEXT
            )
            ''')
        else:
            # Check if last_updated column exists in libraries table
            cursor.execute("PRAGMA table_info(libraries)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'last_updated' not in columns:
                logger.info("Adding last_updated column to libraries table")
                cursor.execute("ALTER TABLE libraries ADD COLUMN last_updated TEXT")
                conn.commit()
        
        # Check if the photos table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'")
        if not cursor.fetchone():
            logger.info(f"Creating photos table in {db_path}")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
              id INTEGER PRIMARY KEY,
              filename TEXT,
              path TEXT,
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
            
            # Create indexes for better query performance
            logger.info("Creating indexes...")
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_coords ON photos(latitude, longitude)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_datetime ON photos(datetime)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON photos(filename)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_hash ON photos(hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_path ON photos(path)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_library_id ON photos(library_id)')
        
        conn.commit()
        conn.close()
        logger.info("Database tables created or verified successfully")
        return True
    except Exception as e:
        logger.error(f"Error ensuring database tables: {e}")
        return False
def get_file_index(cursor):
    """Create an index of existing files in the database for faster lookup"""
    file_index = {}
    cursor.execute("SELECT filename, path FROM photos")
    for row in cursor.fetchall():
        file_index[row[0]] = row[1]
    return file_index

def record_processing_time(library_name, data_dir='./data', db_path='data/photo_library.db'):
    """
    Record the timestamp of the last library processing.
    This will be used by the web UI to display when the library was last updated.
    
    Args:
        library_name (str): Name of the library being processed
        data_dir (str): Directory where the database is located (legacy parameter for backward compatibility)
        db_path (str): Path to database file
    """
    try:
        # Get current timestamp in a readable format
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ensure 'data' directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Create legacy text file for backward compatibility
        try:
            update_file = os.path.join(data_dir, f"last_update_{library_name}.txt")
            with open(update_file, "w") as f:
                f.write(f"{timestamp}")
        except Exception as e:
            logger.warning(f"Failed to write legacy timestamp file: {e}")
        
        # Connect to the database
        if not os.path.isabs(db_path):
            # If relative path, resolve it correctly
            if os.path.exists(os.path.join(data_dir, db_path)):
                db_path = os.path.join(data_dir, db_path)
        
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if last_updated column exists
        cursor.execute("PRAGMA table_info(libraries)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'last_updated' in columns:
            # Update the last_updated field for this library
            cursor.execute(
                "UPDATE libraries SET last_updated = ? WHERE name = ?",
                (timestamp, library_name)
            )
            conn.commit()
            logger.info(f"Updated database timestamp for library '{library_name}' at {timestamp}")
        else:
            logger.warning("last_updated column not found in libraries table")
            
            # Try to add the column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE libraries ADD COLUMN last_updated TEXT")
                conn.commit()
                logger.info("Added last_updated column to libraries table")
                
                # Now update the value
                cursor.execute(
                    "UPDATE libraries SET last_updated = ? WHERE name = ?",
                    (timestamp, library_name)
                )
                conn.commit()
                logger.info(f"Updated database timestamp for library '{library_name}' at {timestamp}")
            except Exception as e:
                logger.error(f"Failed to add last_updated column: {e}")
                
        conn.close()
    except Exception as e:
        logger.error(f"Failed to record processing time: {e}")

def normalize_path(path):
    """
    Normalize path for cross-platform compatibility.
    This helps handle both Windows and Linux paths correctly.
    """
    # Convert to absolute path
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    
    # On Windows, check if this is a valid path format for another OS
    if os.name == 'nt' and path.startswith('/'):
        logger.info(f"Detected Linux-style path on Windows: {path}")
        # Try to translate a Linux-style path to current OS
        # This handles paths like /photos/Fernando when running on Windows
        parts = path.split('/')
        path = os.path.join(*[p for p in parts if p])
        logger.info(f"Normalized to: {path}")
    
    # Handle cases where Docker volume mounts might use different paths than host
    if not os.path.exists(path) and path.startswith('/photos/'):
        alt_path = path.replace('/photos/', './')
        if os.path.exists(alt_path):
            logger.info(f"Using alternative path: {alt_path} instead of {path}")
            path = alt_path
    
    return path

def cross_platform_scan_dir(directory, extensions=None):
    """
    Scan a directory for files with specific extensions in a cross-platform compatible way.
    
    Args:
        directory (str): Directory path to scan
        extensions (tuple): File extensions to filter by (case-insensitive)
        
    Returns:
        list: List of file paths matching the extensions
    """
    # Normalize path for cross-platform compatibility
    norm_dir = normalize_path(directory)
    
    if not os.path.isdir(norm_dir):
        logger.error(f"Cannot scan non-existent directory: {norm_dir} (original: {directory})")
        # Try to output what's available
        try:
            parent_dir = os.path.dirname(norm_dir)
            if os.path.exists(parent_dir):
                logger.info(f"Contents of parent directory {parent_dir}:")
                for item in os.listdir(parent_dir):
                    logger.info(f"  - {item}")
        except Exception:
            pass
        return []
    
    matching_files = []
    logger.info(f"Scanning directory: {norm_dir}")
    
    try:
        for root, _, files in os.walk(norm_dir):
            for filename in files:
                if extensions and not filename.lower().endswith(extensions):
                    continue
                full_path = os.path.join(root, filename)
                matching_files.append(full_path)
    except Exception as e:
        logger.error(f"Error scanning directory {norm_dir}: {e}")
    
    logger.info(f"Found {len(matching_files)} matching files in {norm_dir}")
    return matching_files
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process images and create a photo heatmap database')
    parser.add_argument('--init', action='store_true', help='Initialize the database')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--db', default='data/photo_library.db', help='Database file path')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--clean', action='store_true', help='Clean database before processing')
    parser.add_argument('--force', action='store_true', help='Force import even if photo already exists in database')
    parser.add_argument('--legacy', action='store_true', help='Use legacy processing mode (slower, not recommended)')
    parser.add_argument('--no-cache', action='store_true', help='Disable directory content cache for incremental processing')
    parser.add_argument('--no-resume', action='store_true', help='Disable resume capability for interrupted operations')
    parser.add_argument('--no-optimize-sqlite', action='store_true', help='Disable SQLite optimizations (WAL mode, etc.)')
    parser.add_argument('--serial-scan', action='store_true', help='Disable parallel directory scanning, use serial scanning instead')
    parser.add_argument('--library', default='Default', help='Specify the library name for imported photos')
    parser.add_argument('--description', help='Description for the library (when creating a new library)')
    args = parser.parse_args()
    
    # Ensure 'data' directory exists
    data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(data_dir, exist_ok=True)
      # Ensure DB path exists
    db_dir = os.path.dirname(args.db)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # We'll automatically initialize the database if needed
    # The --init flag is kept for backward compatibility but is no longer required
    if args.init:
        ensure_database_initialized(args.db)
    
    if args.clean:
        clean_database(args.db)
    
    if args.process:
        # Normalize the process directory path
        process_dir = normalize_path(args.process)
        logger.info(f"Normalized process directory: {process_dir}")
        
        # Always use the incremental processing by default as it's much faster
        # Only use the legacy processing if explicitly requested with --legacy flag
        if getattr(args, 'legacy', False):            # Use legacy standard processing
            logger.info("Using legacy processing mode (slower)")
            process_directory(
                root_dir=process_dir,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                skip_existing=not args.force,
                library_name=args.library
            )
        else:            # Use optimized incremental processing by default
            logger.info("Using optimized incremental processing mode")
            process_directory_incremental(
                root_dir=process_dir,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                library_name=args.library,
                use_cache=not args.no_cache,
                resume=not args.no_resume,
                use_parallel_scan=not args.serial_scan
            )
