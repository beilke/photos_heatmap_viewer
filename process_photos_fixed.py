# Fixed version of the main section with correct indentation
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process images and create a photo heatmap database')
    parser.add_argument('--init', action='store_true', help='Initialize the database')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--export', action='store_true', help='Export database to JSON')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--output', default='photo_heatmap_data.json', help='Output JSON file path')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--export-all', action='store_true', help='Export all photos to JSON, not just those with GPS data')
    parser.add_argument('--clean', action='store_true', help='Clean database before processing')
    parser.add_argument('--force', action='store_true', help='Force import even if photo already exists in database')
    parser.add_argument('--incremental', action='store_true', help='Fast incremental processing - only process new files by path comparison')
    parser.add_argument('--no-cache', action='store_true', help='Disable directory content cache for incremental processing')
    parser.add_argument('--no-resume', action='store_true', help='Disable resume capability for interrupted operations')
    parser.add_argument('--no-optimize-sqlite', action='store_true', help='Disable SQLite optimizations (WAL mode, etc.)')
    parser.add_argument('--serial-scan', action='store_true', help='Disable parallel directory scanning, use serial scanning instead')
    parser.add_argument('--library', default='Default', help='Specify the library name for imported photos')
    parser.add_argument('--description', help='Description for the library (when creating a new library)')
    
    args = parser.parse_args()
    
    if args.init:
        from init_db import create_database
        create_database(args.db)
    
    if args.clean:
        clean_database(args.db)
    
    if args.process:
        if args.incremental:
            # Use optimized incremental processing with our added features
            process_directory_incremental(
                root_dir=args.process,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                library_name=args.library,
                use_cache=not args.no_cache,
                resume=not args.no_resume
            )
        else:
            # Use standard processing
            process_directory(
                root_dir=args.process,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                skip_existing=not args.force,
                library_name=args.library
            )
    
    if args.export:
        export_to_json(args.db, args.output, include_non_geotagged=args.export_all)
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
    with open(image_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

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
        filename = os.path.basename(image_path)
        # Skip unsupported files if HEIC support is not available
        if filename.lower().endswith('.heic') and not HEIC_SUPPORT:
            logger.info(f"Skipping HEIC file {filename} - install pillow-heif for HEIC support")
            # Return basic information without GPS or datetime
            return {
                'filename': filename,
                'path': image_path,
                'latitude': None,
                'longitude': None,
                'datetime': None,
                'hash': None
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

def process_directory(root_dir, db_path='photo_library.db', max_workers=4, include_all=False, 
                     skip_existing=True, library_name="Default"):
    """Process all images in a directory and its subdirectories"""
    conn = sqlite3.connect(db_path)
    
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
              created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    batch_size = 100  # Process in batches of 100 for better commits
    
    # Process in smaller batches to avoid memory issues with large libraries
    for i in range(0, len(to_process), batch_size):
        batch = to_process[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(to_process) + batch_size - 1)//batch_size} ({len(batch)} images)...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    
                    # Log progress
                    if processed_count % 10 == 0:
                        print(f"Processed {processed_count}/{len(to_process)} images...")
                    
                    if result:
                        # If include_all is True, keep all photos regardless of GPS data
                        # Otherwise, only keep photos with GPS coordinates
                        if include_all or (result['latitude'] and result['longitude']):
                            # Create marker data
                            result['marker_data'] = create_marker_data(result)
                            result['library_id'] = library_id
                            batch_results.append(result)
                except Exception as e:
                    print(f"Error with {path}: {e}")
        
        # Batch insert the results
        if batch_results:
            inserted_count += batch_insert_photos(cursor, batch_results)
            conn.commit()
            print(f"Inserted {inserted_count} photos so far")
            
    print(f"Processing complete. {processed_count} images processed, {inserted_count} images inserted into database.")
    
    # Final commit
    conn.commit()
    conn.close()
    print(f"Processing complete. {processed_count} images processed.")

def export_to_json(db_path='photo_library.db', output_path='photo_heatmap_data.json', include_non_geotagged=False):
    """Export the database to JSON format for the heatmap visualization"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    
    # First check if the database has records
    cursor.execute("SELECT COUNT(*) FROM photos")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("Warning: No photos found in the database. The JSON file will be empty.")
        # Still create an empty JSON file
        with open(output_path, 'w') as f:
            f.write('{"photos": [], "libraries": []}')
        conn.close()
        return
    
    # Get libraries information
    try:
        cursor.execute("SELECT id, name, description, source_dirs FROM libraries")
        library_rows = cursor.fetchall()
        libraries = []
        
        for row in library_rows:
            lib = dict(row)
            # Parse source_dirs from JSON string
            try:
                lib['source_dirs'] = json.loads(lib['source_dirs']) if lib['source_dirs'] else []
            except Exception:
                lib['source_dirs'] = []
            libraries.append(lib)
    except sqlite3.Error as e:
        print(f"Warning: Could not fetch libraries: {e}")
        libraries = []
    
    # Get photos with library information
    if include_non_geotagged:
        # Export all photos, even those without GPS data
        cursor.execute('''
        SELECT p.id, p.filename, p.latitude, p.longitude, p.datetime, p.path, 
               p.marker_data, p.library_id, l.name as library_name
        FROM photos p
        LEFT JOIN libraries l ON p.library_id = l.id
        ''')
    else:
        # Export only photos with GPS data
        cursor.execute('''
        SELECT p.id, p.filename, p.latitude, p.longitude, p.datetime, p.path, 
               p.marker_data, p.library_id, l.name as library_name
        FROM photos p
        LEFT JOIN libraries l ON p.library_id = l.id
        WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        ''')
    
    rows = cursor.fetchall()
    photos = []
    
    for row in rows:
        photo = dict(row)
        # Parse marker_data from JSON string if available
        if photo['marker_data']:
            try:
                photo['marker_data'] = json.loads(photo['marker_data'])
            except Exception:
                photo['marker_data'] = {}
        else:
            photo['marker_data'] = {}
        
        photos.append(photo)
    
    # Create final data structure with libraries and photos
    result = {
        "photos": photos,
        "libraries": libraries
    }
    
    # Get record counts for logging
    total_count = len(photos)
    geotagged_count = len([photo for photo in photos if photo['latitude'] and photo['longitude']])
    
    # Ensure the directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)    
    # Create a temporary file first, then move it to the final destination
    # This helps prevent truncated files if the process is interrupted
    temp_output_path = f"{output_path}.tmp"
    
    try:
        with open(temp_output_path, 'w', encoding='utf-8') as f:
            # Use a more compact format to avoid formatting issues
            json.dump(result, f, ensure_ascii=False)
        
        # Check if the JSON file was written successfully
        if os.path.exists(temp_output_path):
            # Get the file size to verify it's not empty
            file_size = os.path.getsize(temp_output_path)
            
            if file_size > 0:
                # Move the temporary file to the final destination
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_output_path, output_path)
                print(f"Exported {total_count} records to {output_path} ({geotagged_count} with GPS data, {total_count - geotagged_count} without)")
                print(f"Included {len(libraries)} libraries")
                print(f"JSON file size: {file_size / 1024:.2f} KB")
            else:
                print(f"Error: Generated JSON file is empty. Please check database contents.")
        else:
            print(f"Error: Failed to create JSON file.")
    except Exception as e:
        print(f"Error exporting to JSON: {e}")
        # If there was an error, try to clean up the temporary file
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
    
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
        # Enable WAL (Write-Ahead Logging) mode - greatly improves concurrent write performance
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Set cache size to 2000 pages (about 8MB with default page size)
        conn.execute("PRAGMA cache_size=2000")
        
        # Configure other performance settings
        conn.execute("PRAGMA synchronous=NORMAL")  # Less safe but faster than FULL
        conn.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory
        conn.execute("PRAGMA mmap_size=268435456") # Use memory mapping (256MB)
        
        logger.info("SQLite optimizations applied")
        
        # Return current settings for debugging
        settings = {}
        for pragma in ["journal_mode", "cache_size", "synchronous", "temp_store", "mmap_size"]:
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
        logger.info(f"Directory cache saved to {cache_path}")
    except Exception as e:
        logger.warning(f"Failed to save directory cache: {e}")

# Define this as a top-level function so it can be pickled for multiprocessing
def _scan_single_directory(args):
    """Scan a single directory for image files
    
    Args:
        args: Tuple of (dir_path, image_extensions, existing_paths_list)
        
    Returns:
        Tuple of (files_found, total_files_in_directory)
    """
    dir_path, image_extensions, existing_paths_list = args
    # Convert the list back to a set for faster lookups
    existing_paths = set(existing_paths_list)
    files_found = []
    total = 0
    try:
        for filename in os.listdir(dir_path):
            full_path = os.path.join(dir_path, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(image_extensions):
                total += 1
                if full_path not in existing_paths:
                    files_found.append(full_path)
    except (PermissionError, FileNotFoundError) as e:
        # Handle permission errors or directories that disappeared
        logger.warning(f"Error scanning directory {dir_path}: {e}")
    
    return files_found, total

def scan_directory_parallel(root_dir, image_extensions, existing_paths=None):
    """Scan a directory for image files in parallel using multiprocessing"""
    if existing_paths is None:
        existing_paths = set()
      # Get all directories under the root
    all_dirs = []
    # Convert set to list for pickling
    existing_paths_list = list(existing_paths)
    for dirpath, _, _ in os.walk(root_dir):
        all_dirs.append((dirpath, image_extensions, existing_paths_list))
    
    new_files = []
    total_files = 0
    
    # Use multiprocessing to scan directories in parallel
    max_processes = min(multiprocessing.cpu_count(), 8)  # Limit to 8 processes max
    logger.info(f"Scanning {len(all_dirs)} directories with {max_processes} processes")
    
    try:
        # Use multiprocessing with a reasonable chunk size for better performance
        chunk_size = max(1, len(all_dirs) // (max_processes * 4))
        
        with multiprocessing.Pool(processes=max_processes) as pool:
            results = pool.map(_scan_single_directory, all_dirs, chunksize=chunk_size)
            
        # Collect results
        for files, total in results:
            new_files.extend(files)
            total_files += total
            
    except Exception as e:
        # Fall back to serial processing if multiprocessing fails
        logger.error(f"Parallel scanning failed: {e}. Falling back to serial processing.")
        new_files = []
        total_files = 0
        
        for dir_path, extensions, paths in all_dirs:
            files, total = _scan_single_directory((dir_path, extensions, paths))
            new_files.extend(files)
            total_files += total
    
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

def process_directory_incremental(root_dir, db_path='photo_library.db', max_workers=4, include_all=False, 
                          library_name="Default", use_cache=True, resume=True, use_parallel_scan=True):
    """Fast incremental processing with optimizations:
    - Uses multiprocessing for parallel directory scanning
    - Optional directory cache for avoiding redundant scans
    - SQLite optimizations (WAL mode, memory settings)
    - Resume capability for interrupted operations
    - Directory change detection to skip unchanged directories
    """
    start_time = time.time()
    
    # Validate the directory
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    logger.info(f"Starting optimized incremental scan of {root_dir}")
    
    # Prepare cache and checkpoint files
    workspace_dir = os.path.join(os.path.dirname(db_path), '.workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    cache_path = os.path.join(workspace_dir, 'directory_cache.pkl')
    checkpoint_path = os.path.join(workspace_dir, 'process_checkpoint.pkl')
    
    # Connect to database with optimizations
    conn = sqlite3.connect(db_path)
    
    # Apply SQLite optimizations
    optimization_settings = optimize_sqlite_connection(conn)
    logger.info(f"SQLite optimization settings: {optimization_settings}")
    
    cursor = conn.cursor()
    
    # Create tables if they don't exist and make sure we have a library
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS libraries (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          description TEXT,
          source_dirs TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    cursor.execute("SELECT path FROM photos")
    existing_paths = {row[0] for row in cursor.fetchall()}
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
                            new_files.append(full_path)    else:
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
    
    # Process new files in parallel
    batch_size = 100  # Process in batches for better performance
    processed_count = 0
    inserted_count = 0
    
    logger.info(f"Processing {len(new_files)} new files with {max_workers} workers...")
    
    for i in range(0, len(new_files), batch_size):
        batch = new_files[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(new_files) + batch_size - 1)//batch_size} ({len(batch)} images)...")
        
        # Create a checkpoint for this batch
        if resume:
            create_checkpoint(checkpoint_path, list(processed_files), batch)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, path): path for path in batch}
            batch_results = []
            
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    result = future.result()
                    processed_count += 1
                    processed_files.add(path)  # Mark as processed for checkpoint
                    
                    # Log progress
                    if processed_count % 10 == 0:
                        logger.info(f"Processed {processed_count}/{len(new_files)} images...")
                    
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
        
        # Insert batch results
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
                logger.info(f"Inserted {inserted_this_batch} photos in this batch ({inserted_count} total)")
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
    
    # Processing complete, remove checkpoint file if it exists
    if resume and os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
            logger.info("Removed checkpoint file after successful processing")
        except:
            pass
    
    conn.close()
    end_time = time.time()
    logger.info(f"Incremental scan completed in {end_time - start_time:.2f} seconds")
    logger.info(f"Processed {processed_count} images, inserted {inserted_count} into database")

