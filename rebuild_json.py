#!/usr/bin/env python
"""
Script to regenerate a clean JSON file from the database
"""

import sqlite3
import json
import os

def rebuild_json():
    """Rebuild the JSON file with proper formatting"""
    # Define file paths
    db_path = 'photo_library.db'
    output_path = 'photo_heatmap_data.json'
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        return False
    
    # Create backup of existing JSON file if it exists
    if os.path.exists(output_path):
        backup_path = f"{output_path}.bak"
        try:
            with open(output_path, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            print(f"Created backup of existing JSON file: {backup_path}")
        except Exception as e:
            print(f"Warning: Failed to create backup: {e}")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        # Get libraries information
        cursor.execute("SELECT id, name, description, source_dirs FROM libraries")
        library_rows = cursor.fetchall()
        libraries = []
        
        for row in library_rows:
            lib = dict(row)
            try:
                lib['source_dirs'] = json.loads(lib['source_dirs']) if lib['source_dirs'] else []
            except Exception:
                lib['source_dirs'] = []
            libraries.append(lib)
        
        print(f"Found {len(libraries)} libraries")
        
        # Get photos information
        cursor.execute("""
        SELECT p.id, p.filename, p.latitude, p.longitude, p.datetime, p.path, 
               p.marker_data, p.library_id, l.name as library_name
        FROM photos p
        LEFT JOIN libraries l ON p.library_id = l.id
        """)
        
        rows = cursor.fetchall()
        photos = []
        
        for row in rows:
            photo = dict(row)
            
            # Parse marker_data JSON
            if photo['marker_data']:
                try:
                    photo['marker_data'] = json.loads(photo['marker_data'])
                except Exception:
                    photo['marker_data'] = {}
            else:
                photo['marker_data'] = {}
            
            photos.append(photo)
        
        print(f"Found {len(photos)} photos")
        
        # Create final data structure
        result = {
            "photos": photos,
            "libraries": libraries
        }
        
        # Write to a temporary file first
        temp_path = f"{output_path}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # Validate JSON - make sure it can be parsed back
        with open(temp_path, 'r', encoding='utf-8') as f:
            test = json.load(f)
            print(f"JSON validation successful: {len(test['photos'])} photos, {len(test['libraries'])} libraries")
        
        # Replace the original file
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(temp_path, output_path)
        
        print(f"Successfully created new JSON file: {output_path}")
        return True
    
    except Exception as e:
        print(f"Error rebuilding JSON: {e}")
        return False

if __name__ == "__main__":
    print("==== JSON Rebuild Utility ====")
    result = rebuild_json()
    print("Done!")
    exit(0 if result else 1)
