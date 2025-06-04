import os
import json
import urllib.request
import urllib.error
import sqlite3
import time
import sys

def test_photo_server():
    """Test the server's ability to serve photos correctly"""
    print("Testing photo server thumbnail capabilities...")
    
    # Check if server is running
    try:
        with urllib.request.urlopen("http://localhost:8000/") as response:
            if response.status != 200:
                print(f"WARNING: Server responded with status {response.status}")
    except urllib.error.URLError:
        print("ERROR: Server doesn't appear to be running. Please start it first with 'python server.py'")
        return False
    
    # Check if JSON file exists
    json_file = "photo_heatmap_data.json"
    if not os.path.exists(json_file):
        print(f"ERROR: JSON file {json_file} not found")
        return False
        
    # Parse JSON data
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list) or len(data) == 0:
            print(f"ERROR: No valid data in {json_file}")
            return False
            
        print(f"Found {len(data)} photos in JSON file")
        
        # Test thumbnails for each photo
        success_count = 0
        
        for i, photo in enumerate(data):
            if i >= 5:  # Only test the first 5 photos to avoid long wait times
                print(f"Skipping remaining photos...")
                break
                
            if 'filename' not in photo:
                print(f"WARNING: Photo at index {i} has no filename")
                continue
                
            filename = photo['filename']
            print(f"Testing photo {i+1}/{min(len(data), 5)}: {filename}")
            
            # Construct URL for thumbnail
            url = f"http://localhost:8000/photos/{urllib.parse.quote(filename)}"
            
            try:
                start_time = time.time()
                with urllib.request.urlopen(url) as response:
                    if response.status == 200:
                        # Read a bit of data to ensure it's working
                        data = response.read(1024)
                        end_time = time.time()
                        success_count += 1
                        print(f"  SUCCESS: Thumbnail received in {(end_time-start_time):.2f} seconds")
                    else:
                        print(f"  ERROR: Server returned status {response.status}")
            except urllib.error.URLError as e:
                print(f"  ERROR: Failed to fetch thumbnail: {e}")
                
        if success_count > 0:
            print(f"\nSUCCESS: {success_count}/{min(len(data), 5)} thumbnails were successfully retrieved")
            return True
        else:
            print("\nERROR: No thumbnails could be retrieved")
            
            # Check database for path issues
            db_path = "photo_library.db"
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT filename, path FROM photos LIMIT 5")
                    rows = cursor.fetchall()
                    conn.close()
                    
                    print("\nSample paths in database:")
                    for row in rows:
                        print(f"  {row[0]} -> {row[1]}")
                        
                    print("\nCheck if these paths exist on your system.")
                    
                except Exception as e:
                    print(f"Error accessing database: {e}")
            else:
                print(f"\nCould not find database file {db_path}")
                
            return False
            
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_photo_server()
    if not success:
        print("\nTroubleshooting tips:")
        print("1. Ensure server.py is running")
        print("2. Check if photo paths in the database match your file system")
        print("3. If using Windows, ensure drive letter normalization is working in server.py")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)
