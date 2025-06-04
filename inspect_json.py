import json
import os
import sys
import datetime

def inspect_json_file(filepath):
    """
    Inspect a JSON file to validate its structure and content
    """
    print(f"Inspecting JSON file: {filepath}")
    
    # Check if file exists
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return False
    
    # Check file size
    file_size = os.path.getsize(filepath)
    print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    
    if file_size == 0:
        print("ERROR: File is empty (0 bytes)")
        return False
    
    # Try to parse the JSON
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read first few characters for inspection
            start_chars = f.read(100)
            print(f"File starts with: {start_chars[:50]}...")
            
            # Reset file pointer
            f.seek(0)
            
            # Parse the JSON
            data = json.load(f)
            
            # Check if it's an array
            if not isinstance(data, list):
                print(f"ERROR: JSON data is not an array. Type: {type(data)}")
                return False
            
            # Check the array length
            print(f"JSON array contains {len(data):,} items")
            
            # If empty array
            if len(data) == 0:
                print("WARNING: JSON array is empty")
                return True
            
            # Inspect the first item
            first_item = data[0]
            if not isinstance(first_item, dict):
                print(f"WARNING: First item is not a dictionary. Type: {type(first_item)}")
            else:
                print("First item properties:")
                for key, value in first_item.items():
                    print(f"  - {key}: {type(value).__name__} = {value}")
            
            # Count items with GPS data
            items_with_gps = sum(1 for item in data if 
                               isinstance(item, dict) and
                               'latitude' in item and 'longitude' in item and
                               item['latitude'] is not None and item['longitude'] is not None)
            
            print(f"Items with GPS data: {items_with_gps:,} ({items_with_gps/len(data)*100:.1f}% of total)")
            
            # Format check for GPS coordinates
            if items_with_gps > 0:
                # Find the first item with GPS
                sample_gps = next((item for item in data if 
                                 isinstance(item, dict) and
                                 'latitude' in item and 'longitude' in item and
                                 item['latitude'] is not None and item['longitude'] is not None), None)
                
                if sample_gps:
                    print(f"Sample GPS coordinates: {sample_gps['latitude']}, {sample_gps['longitude']}")
                    
                    # Check if they are numeric
                    try:
                        lat = float(sample_gps['latitude'])
                        lon = float(sample_gps['longitude'])
                        print(f"  - Values are numeric: lat={lat}, lon={lon}")
                        
                        # Check if values are in reasonable range
                        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                            print(f"  - WARNING: GPS coordinates out of valid range")
                    except (ValueError, TypeError):
                        print(f"  - ERROR: GPS coordinates are not valid numbers")
            
            return True
            
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        
        # Read part of the file to see where it breaks
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                problem_area = f.read(max(0, e.pos - 50)), f.read(100)
                print(f"Problem near: ...{problem_area[0]}{problem_area[1]}...")
        except:
            pass
            
        return False
    except UnicodeDecodeError as e:
        print(f"ERROR: Unicode decode error: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Other error: {e}")
        return False

def fix_json_file(filepath):
    """
    Attempt to fix common JSON file issues
    """
    print(f"Attempting to fix JSON file: {filepath}")
    
    # Backup the original file
    backup_path = f"{filepath}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        with open(filepath, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        print(f"Created backup: {backup_path}")
    except Exception as e:
        print(f"WARNING: Could not create backup: {e}")
    
    try:
        # Try to read the file and fix basic issues
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # If file appears empty or just contains whitespace
        content = content.strip()
        if not content:
            print("Creating minimal valid JSON array...")
            content = "[]"
        
        # If it doesn't start with [ but has JSON-like content
        elif not content.startswith('[') and (content.startswith('{') or
                                             '"' in content or
                                             "'" in content):
            print("Wrapping content in array brackets...")
            content = f"[{content}]"
        
        # Fix common trailing comma issue
        if ",]" in content:
            print("Fixing trailing commas...")
            content = content.replace(",]", "]")
            
        # Try to parse it to validate
        try:
            json.loads(content)
            print("Fixed content is valid JSON")
        except json.JSONDecodeError as e:
            print(f"Still invalid JSON after fixes: {e}")
            return False
            
        # Write the fixed content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"Fixed JSON file written to: {filepath}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to fix JSON file: {e}")
        return False

def create_minimal_json(filepath):
    """
    Create a minimal valid empty JSON array file
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("[]")
        print(f"Created minimal empty JSON array at: {filepath}")
        return True
    except Exception as e:
        print(f"ERROR: Could not create minimal JSON file: {e}")
        return False

if __name__ == "__main__":
    # Default JSON file path
    json_file = "photo_heatmap_data.json"
    
    # Parse arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("Usage: python inspect_json.py [filepath] [--fix]")
            print("  filepath: Path to JSON file (default: photo_heatmap_data.json)")
            print("  --fix: Attempt to fix the JSON file if issues are found")
            print("  --create-empty: Create a minimal valid empty JSON array")
            sys.exit(0)
        if sys.argv[1] != "--fix" and sys.argv[1] != "--create-empty":
            json_file = sys.argv[1]
    
    # Check for --fix flag
    fix_mode = "--fix" in sys.argv
    create_empty = "--create-empty" in sys.argv
    
    if create_empty:
        create_minimal_json(json_file)
        sys.exit(0)
        
    # Inspect the file
    success = inspect_json_file(json_file)
    
    # If inspection failed and fix mode is enabled
    if not success and fix_mode:
        print("\nAttempting to fix issues...")
        fix_json_file(json_file)
        
        # Re-inspect after fixing
        print("\nRe-inspecting after fixes:")
        inspect_json_file(json_file)
