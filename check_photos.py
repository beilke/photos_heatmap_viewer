import sqlite3
import json
import os
from pathlib import Path

DB_PATH = 'photo_library.db'

def check_photo_data():
    if not os.path.exists(DB_PATH):
        print("Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n----- DETAILED PHOTO INFORMATION -----")
    
    # Get all photos
    cursor.execute("SELECT id, filename, path, latitude, longitude, library_id FROM photos")
    photos = cursor.fetchall()
    
    if not photos:
        print("No photos found in database!")
        return
    
    print(f"Found {len(photos)} total photos")
    
    # Print detailed info about each photo
    for i, photo in enumerate(photos):
        photo_id, filename, path, lat, lon, library_id = photo
        print(f"\nPhoto {i+1}/{len(photos)}:")
        print(f"  ID: {photo_id}")
        print(f"  Filename: {filename}")
        print(f"  Path: {path}")
        print(f"  GPS: {'Yes' if lat is not None and lon is not None else 'No'} (Lat: {lat}, Lon: {lon})")
        print(f"  Library ID: {library_id}")
        
        # Check if file exists
        full_path = os.path.join(path, filename) if path else filename
        if os.path.exists(full_path):
            print(f"  File exists: Yes")
            print(f"  File size: {os.path.getsize(full_path)} bytes")
        else:
            print(f"  File exists: No")

    print("\n----- PROCESS_PHOTOS.PY ANALYSIS -----")
    try:
        # Check if process_photos.py exists
        if os.path.exists('process_photos.py'):
            with open('process_photos.py', 'r') as f:
                content = f.read()
                # Check for GPS extraction code
                if 'latitude' in content and 'longitude' in content:
                    print("GPS extraction code found in process_photos.py")
                    # Look for specific GPS extraction methods
                    if '_get_gps' in content:
                        print("_get_gps function found")
                    else:
                        print("WARNING: No _get_gps function found")
                else:
                    print("WARNING: No GPS extraction code found in process_photos.py")
        else:
            print("process_photos.py not found!")
    except Exception as e:
        print(f"Error analyzing process_photos.py: {e}")
    
    print("\n----- SAMPLE EXIF DATA -----")
    try:
        from PIL import Image
        import PIL.ExifTags
        
        # Try to extract EXIF data from a sample photo
        for photo in photos:
            _, filename, path, _, _, _ = photo
            full_path = os.path.join(path, filename) if path else filename
            if os.path.exists(full_path):
                try:
                    print(f"Analyzing EXIF for: {filename}")
                    img = Image.open(full_path)
                    exif_data = img._getexif()
                    
                    if exif_data:
                        print("  EXIF data found")
                        # Print some key EXIF fields
                        exif = {PIL.ExifTags.TAGS.get(k, k): v for k, v in exif_data.items() if k in PIL.ExifTags.TAGS}
                        
                        # Check for GPS info
                        if 'GPSInfo' in exif:
                            gps_info = exif['GPSInfo']
                            print("  GPS data found in EXIF")
                            print("  GPS tags:", list(gps_info.keys()))
                        else:
                            print("  No GPS data in EXIF")
                            
                        # Check for some common tags
                        for tag in ['DateTime', 'Make', 'Model']:
                            if tag in exif:
                                print(f"  {tag}: {exif[tag]}")
                    else:
                        print("  No EXIF data found")
                        
                    break  # Just analyze one photo
                except Exception as e:
                    print(f"  Error reading EXIF: {e}")
        else:
            print("No accessible photos found for EXIF analysis")
    except ImportError:
        print("PIL library not available for EXIF analysis")
    
    conn.close()

if __name__ == "__main__":
    check_photo_data()
