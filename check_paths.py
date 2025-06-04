import json
import os
import sys

def check_photo_paths():
    """Check if photo paths in the JSON file exist and suggest fixes for path issues"""
    json_file = "photo_heatmap_data.json"
    
    if not os.path.exists(json_file):
        print(f"ERROR: JSON file not found: {json_file}")
        return False
    
    print(f"Checking photo paths in {json_file}...")
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list) or len(data) == 0:
            print(f"ERROR: No valid data in {json_file}")
            return False
            
        print(f"Found {len(data)} photos in the JSON file")
        
        # Check paths
        accessible_count = 0
        inaccessible_paths = []
        
        for item in data:
            if 'path' not in item:
                continue
                
            original_path = item['path']
            
            # Try to access the file directly
            if os.path.exists(original_path):
                accessible_count += 1
                continue
                
            # Try different drive letters if on Windows
            if sys.platform == 'win32' and len(original_path) > 1 and original_path[1] == ':':
                drive_free_path = original_path[2:]
                found = False
                
                # Try common drive letters
                for drive in ['C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 
                              'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:']:
                    test_path = f"{drive}{drive_free_path}"
                    if os.path.exists(test_path):
                        print(f"FOUND: {original_path} -> {test_path}")
                        accessible_count += 1
                        found = True
                        break
                        
                if found:
                    continue
            
            # If we get here, the path is inaccessible
            inaccessible_paths.append(original_path)
        
        # Report results
        if accessible_count == len(data):
            print(f"SUCCESS: All {accessible_count} photo paths are accessible")
        else:
            print(f"WARNING: Only {accessible_count} of {len(data)} photo paths are accessible")
            print(f"The following {len(inaccessible_paths)} paths could not be found:")
            for path in inaccessible_paths:
                print(f"  - {path}")
                
            # Suggest fix
            if inaccessible_paths and sys.platform == 'win32':
                print("\nSUGGESTION: The photo paths may be using a different drive letter.")
                print("Try modifying server.py to enable drive letter normalization.")
                
        return accessible_count > 0
            
    except Exception as e:
        print(f"ERROR: Failed to check paths: {e}")
        return False

if __name__ == "__main__":
    check_photo_paths()
