import os
import sys
import json
import sqlite3

def check_paths():
    """Check if photo paths in JSON file are accessible"""
    print("Checking photo paths in photo_heatmap_data.json...")
    
    # Check if JSON file exists
    if not os.path.exists('photo_heatmap_data.json'):
        print("ERROR: photo_heatmap_data.json not found")
        return False
        
    try:
        # Read the JSON file
        with open('photo_heatmap_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data:
            print("ERROR: Empty JSON data")
            return False
            
        print(f"Found {len(data)} photos in the JSON file")
        
        # Check if each path exists
        accessible_paths = 0
        inaccessible_paths = []
        
        for photo in data:
            if 'path' not in photo:
                inaccessible_paths.append(f"Missing path field: {photo.get('filename', 'unknown')}")
                continue
                
            path = photo['path']
            
            # Check if file exists as is
            if os.path.exists(path):
                accessible_paths += 1
                continue
                
            # Try to normalize path on Windows
            if sys.platform == 'win32' and len(path) > 1 and path[1] == ':':
                # Get the path without the drive letter
                drive_free_path = path[2:]
                found = False
                
                # Check common drive letters
                for drive in ['C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 
                            'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:']:
                    test_path = f"{drive}{drive_free_path}"
                    if os.path.exists(test_path):
                        accessible_paths += 1
                        found = True
                        break
                        
                if found:
                    continue
                    
            inaccessible_paths.append(path)
        
        # Report results
        if accessible_paths == len(data):
            print(f"SUCCESS: All {accessible_paths} photo paths are accessible")
            return True
        else:
            print(f"WARNING: {accessible_paths} out of {len(data)} paths are accessible")
            print(f"Inaccessible paths: {len(inaccessible_paths)}")
            for path in inaccessible_paths[:5]:  # Show first 5
                print(f"  - {path}")
                
            if len(inaccessible_paths) > 5:
                print(f"  ... and {len(inaccessible_paths) - 5} more")
                
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def check_db_paths():
    """Check if photo paths in the database are accessible"""
    print("\nChecking photo paths in photo_library.db...")
    
    if not os.path.exists('photo_library.db'):
        print("ERROR: photo_library.db not found")
        return False
        
    try:
        # Connect to the database
        conn = sqlite3.connect('photo_library.db')
        cursor = conn.cursor()
        
        # Get paths from the database
        cursor.execute("SELECT path FROM photos")
        paths = cursor.fetchall()
        
        if not paths:
            print("ERROR: No paths found in database")
            return False
            
        print(f"Found {len(paths)} paths in database")
        
        # Check if each path exists
        accessible_paths = 0
        inaccessible_paths = []
        
        for (path,) in paths:
            # Check if file exists as is
            if os.path.exists(path):
                accessible_paths += 1
                continue
                
            # Try to normalize path on Windows
            if sys.platform == 'win32' and len(path) > 1 and path[1] == ':':
                # Get the path without the drive letter
                drive_free_path = path[2:]
                found = False
                
                # Check common drive letters
                for drive in ['C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 
                            'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:']:
                    test_path = f"{drive}{drive_free_path}"
                    if os.path.exists(test_path):
                        accessible_paths += 1
                        found = True
                        break
                        
                if found:
                    continue
                    
            inaccessible_paths.append(path)
            
        # Report results
        if accessible_paths == len(paths):
            print(f"SUCCESS: All {accessible_paths} database photo paths are accessible")
            return True
        else:
            print(f"WARNING: {accessible_paths} out of {len(paths)} database paths are accessible")
            print(f"Inaccessible paths: {len(inaccessible_paths)}")
            for path in inaccessible_paths[:5]:  # Show first 5
                print(f"  - {path}")
                
            if len(inaccessible_paths) > 5:
                print(f"  ... and {len(inaccessible_paths) - 5} more")
                
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        conn.close()

def update_db_paths():
    """Update paths in the database to match the current system"""
    print("\nAttempting to fix paths in the database...")
    
    if not os.path.exists('photo_library.db'):
        print("ERROR: photo_library.db not found")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect('photo_library.db')
        cursor = conn.cursor()
        
        # Get all records with paths
        cursor.execute("SELECT id, path FROM photos")
        records = cursor.fetchall()
        
        if not records:
            print("No records found in database")
            return False
        
        print(f"Found {len(records)} records to check")
        
        # Track updates
        updates = 0
        
        # Check each path and update if needed
        for record_id, path in records:
            if os.path.exists(path):
                # Path is already accessible
                continue
            
            if sys.platform == 'win32' and len(path) > 1 and path[1] == ':':
                # Get the path without the drive letter
                drive_letter = path[0].upper()
                drive_free_path = path[2:]
                
                # Try all possible drive letters
                for new_drive in ['C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 
                            'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']:
                    if new_drive == drive_letter:
                        continue  # Skip the original drive letter
                        
                    new_path = f"{new_drive}:{drive_free_path}"
                    
                    if os.path.exists(new_path):
                        # Found a valid path, update the database
                        cursor.execute("UPDATE photos SET path = ? WHERE id = ?", (new_path, record_id))
                        print(f"Updated: {path} -> {new_path}")
                        updates += 1
                        break
        
        # Commit changes and report
        if updates > 0:
            conn.commit()
            print(f"Successfully updated {updates} paths in the database")
            
            # Also update the JSON file
            update_json_paths()
            return True
        else:
            print("No paths were updated")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        conn.close()

def update_json_paths():
    """Update paths in the JSON file to match the database"""
    print("\nUpdating JSON file to match database...")
    
    if not os.path.exists('photo_library.db') or not os.path.exists('photo_heatmap_data.json'):
        print("ERROR: Database or JSON file not found")
        return False
        
    try:
        # Read the JSON file
        with open('photo_heatmap_data.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        if not json_data:
            print("No data in JSON file")
            return False
            
        # Connect to the database
        conn = sqlite3.connect('photo_library.db')
        cursor = conn.cursor()
        
        # Get all paths from database
        cursor.execute("SELECT filename, path FROM photos")
        db_paths = {filename: path for filename, path in cursor.fetchall()}
        
        # Update JSON paths
        updates = 0
        for photo in json_data:
            if 'filename' in photo and photo['filename'] in db_paths:
                old_path = photo.get('path', '')
                new_path = db_paths[photo['filename']]
                
                if old_path != new_path:
                    photo['path'] = new_path
                    updates += 1
        
        # Write updated JSON
        if updates > 0:
            with open('photo_heatmap_data.json', 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
                
            print(f"Successfully updated {updates} paths in the JSON file")
            return True
        else:
            print("No paths were updated in the JSON file")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        conn.close()

def check_missing_thumbnails():
    """Test thumbnail generation for a sample photo"""
    print("\nTesting thumbnail generation...")
    
    try:
        # Read the JSON file
        with open('photo_heatmap_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data or len(data) == 0:
            print("No photos found in JSON")
            return
            
        # Get the first photo
        sample_photo = data[0]
        filename = sample_photo.get('filename')
        
        if not filename:
            print("No filename found in sample photo")
            return
            
        print(f"Testing thumbnail for: {filename}")
        
        # Try to access the thumbnail URL
        import urllib.request
        import urllib.error
        
        url = f"http://localhost:8000/photos/{urllib.parse.quote(filename)}"
        print(f"Testing URL: {url}")
        
        try:
            response = urllib.request.urlopen(url)
            print(f"Thumbnail accessible! Status: {response.status}, Content-Type: {response.info().get_content_type()}")
        except urllib.error.HTTPError as e:
            print(f"Error accessing thumbnail: {e.code} {e.reason}")
        except Exception as e:
            print(f"Error: {e}")
            
    except Exception as e:
        print(f"Error testing thumbnails: {e}")

if __name__ == "__main__":
    json_paths_ok = check_paths()
    db_paths_ok = check_db_paths()
    
    if not json_paths_ok or not db_paths_ok:
        print("\nWould you like to attempt to fix path issues? (y/n)")
        response = input().lower()
        
        if response == 'y' or response == 'yes':
            update_db_paths()
            
    # Always check thumbnail generation
    check_missing_thumbnails()
