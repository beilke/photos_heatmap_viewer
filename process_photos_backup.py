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

def get_decimal_from_dms(dms, ref, image_path=None):
    """Convert GPS DMS (Degrees, Minutes, Seconds) to decimal format"""
    try:
        if ref is None:
            logger.error(f"Missing GPS reference (N/S/E/W) in file: {image_path or 'unknown'}")
            return None
            
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
            logger.error(f"Unsupported GPS data format: {type(dms)} - {dms} in file: {image_path or 'unknown'}")
            return None
        
        # Apply the reference direction (N/S/E/W)
        if ref and (ref == 'S' or ref == 'W' or ref == b'S' or ref == b'W'):
            decimal = -decimal
        
        return decimal
    except Exception as e:
        filename = os.path.basename(image_path) if image_path else "unknown"
        logger.error(f"Error converting GPS coordinates in '{filename}': {e}, data: {dms}, ref: {ref}")
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
                                gps_info[GPSTAGS.get(gps_tag, gps_tag)] = value[gps_tag]                    except TypeError as e:
                        # If we get a TypeError (like 'int' object is not iterable)
                        logger.debug(f"Error inspecting GPS data: {e}")
                        if is_heic:
                            # For HEIC files, try alternative extraction method
                            logger.debug("Using alternative method for HEIC GPS extraction")
            
            logger.debug(f"Extracted GPS info: {gps_info}")
            
            if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                try:
                    # Check if we have all necessary data for GPS coordinates
                    if 'GPSLatitudeRef' not in gps_info:
                        logger.error(f"Missing GPSLatitudeRef in {os.path.basename(image_path)}, available keys: {list(gps_info.keys())}")
                        return None, None
                    if 'GPSLongitudeRef' not in gps_info:
                        logger.error(f"Missing GPSLongitudeRef in {os.path.basename(image_path)}, available keys: {list(gps_info.keys())}")
                        return None, None
                        
                    lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'], image_path)
                    lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'], image_path)
                    
                    if lat is not None and lon is not None:
                        logger.debug(f"Converted GPS coordinates for {os.path.basename(image_path)}: {lat}, {lon}")
                        return lat, lon
                    else:
                        logger.warning(f"Failed to convert GPS coordinates for {os.path.basename(image_path)}")
                        return None, None
                except Exception as e:
                    logger.error(f"Error converting GPS coordinates for {os.path.basename(image_path)}: {e}")
                    return None, None
            else:
                # Try one more fallback method for Samsung phones specifically
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
    
    # Process images in parallel
    processed_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(process_image, path): path for path in image_files}
        
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                processed_count += 1
                  # Log progress every 100 files
                if processed_count % 100 == 0:
                    print(f"Processed {processed_count}/{total_files} images...")
                
                if result:
                    # Check if photo already exists in the database (if skip_existing is True)
                    exists = False
                    if skip_existing:
                        exists = photo_exists_in_db(cursor, 
                                                   filename=result['filename'], 
                                                   img_hash=result['hash'], 
                                                   path=result['path'])
                    
                    # If the photo doesn't exist or we're not skipping existing photos
                    if not exists:
                        # If include_all is True, insert all photos regardless of GPS data
                        # Otherwise, only insert photos with GPS coordinates
                        if include_all or (result['latitude'] and result['longitude']):
                            # Create marker data
                            marker_data = create_marker_data(result)
                            
                            cursor.execute(
                                "INSERT INTO photos (filename, path, latitude, longitude, datetime, hash, library_id, marker_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (result['filename'], result['path'], result['latitude'], result['longitude'], 
                                result['datetime'], result['hash'], library_id, marker_data)
                            )
                            # Commit every 100 inserts to avoid large transactions
                            if processed_count % 100 == 0:
                                conn.commit()
            except Exception as e:
                print(f"Error with {path}: {e}")
    
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
    parser.add_argument('--library', default='Default', help='Specify the library name for imported photos')
    parser.add_argument('--description', help='Description for the library (when creating a new library)')
    
    args = parser.parse_args()
    
    if args.init:
        from init_db import create_database
        create_database(args.db)
    
    if args.clean:
        clean_database(args.db)
    
    if args.process:
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
