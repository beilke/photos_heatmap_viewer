import sqlite3
import json
import os

def check_database():
    print("Checking photo database for GPS coordinates...")
    
    # Connect to SQLite database
    conn = sqlite3.connect('photo_library.db')
    cursor = conn.cursor()
    
    # Count all photos
    cursor.execute("SELECT COUNT(*) FROM photos")
    total_photos = cursor.fetchone()[0]
    print(f"Total photos in database: {total_photos}")
    
    # Count photos with GPS
    cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    gps_photos = cursor.fetchone()[0]
    print(f"Photos with GPS coordinates: {gps_photos}")
    
    # Check latest JSON export
    json_path = 'photo_heatmap_data.json'
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            if isinstance(data, dict):
                print(f"\nJSON data structure:")
                print(f"- Has 'photos' key: {'Yes' if 'photos' in data else 'No'}")
                print(f"- Has 'libraries' key: {'Yes' if 'libraries' in data else 'No'}")
                
                if 'photos' in data:
                    print(f"- Photos in JSON: {len(data['photos'])}")
                    
                    # Check how many photos have coordinates
                    photos_with_coords = sum(1 for p in data['photos'] if p.get('latitude') is not None and p.get('longitude') is not None)
                    print(f"- Photos with coordinates in JSON: {photos_with_coords}")
                
                if 'libraries' in data:
                    print(f"- Libraries in JSON: {len(data['libraries'])}")
                    for lib in data['libraries']:
                        print(f"  - {lib.get('name', 'Unnamed')} (ID: {lib.get('id', 'Unknown')})")
            else:
                print(f"\nJSON data is not a dictionary (it's a {type(data).__name__})")
        except Exception as e:
            print(f"\nError reading JSON file: {e}")
    else:
        print(f"\nNo JSON export file found at {json_path}")
    
    conn.close()

if __name__ == "__main__":
    check_database()
