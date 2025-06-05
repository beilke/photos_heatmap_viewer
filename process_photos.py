import sqlite3
import os
import json
import argparse
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import hashlib
import concurrent.futures

def get_image_hash(image_path):
    """Create a simple hash of the image file to identify duplicates"""
    with open(image_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def extract_datetime(image_path):
    """Extract the datetime from image EXIF data"""
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None
                
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
        print(f"Error extracting datetime from {image_path}: {e}")
        return None

def get_decimal_from_dms(dms, ref):
    """Convert GPS DMS (Degrees, Minutes, Seconds) to decimal format"""
    degrees = dms[0]
    minutes = dms[1] / 60.0
    seconds = dms[2] / 3600.0
    
    decimal = degrees + minutes + seconds
    
    if ref in ['S', 'W']:
        decimal = -decimal
    
    return decimal

def extract_gps(image_path):
    """Extract GPS coordinates from image EXIF data"""
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None, None
                
            gps_info = {}
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'GPSInfo':
                    for gps_tag in value:
                        gps_info[GPSTAGS.get(gps_tag, gps_tag)] = value[gps_tag]
            
            if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
                lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
                return lat, lon
    except Exception as e:
        print(f"Error extracting GPS data from {image_path}: {e}")
    
    return None, None

def process_image(image_path):
    """Process a single image and return its metadata"""
    try:
        filename = os.path.basename(image_path)
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
        print(f"Error processing {image_path}: {e}")
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
        with open(temp_output_path, 'w') as f:
            # Use a higher indent value for better readability if needed
            json.dump(result, f, indent=None)
        
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
