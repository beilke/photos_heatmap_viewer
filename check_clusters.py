#!/usr/bin/env python3
import sqlite3
import os
import sys
import json

def check_cluster_issues(db_path):
    """Check for potential issues with clusters in the database."""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print(f"\nConnected to database: {db_path}")
        
        # Check for locations with exactly 2 photos
        print("\nLocations with exactly 2 photos (possible issue cluster):")
        cursor.execute("""
            SELECT latitude, longitude 
            FROM photos 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY latitude, longitude 
            HAVING COUNT(*) = 2
        """)
        locations_with_2 = cursor.fetchall()
        
        if not locations_with_2:
            print("  No locations found with exactly 2 photos.")
        else:
            print(f"  Found {len(locations_with_2)} locations with exactly 2 photos.")
            
            # Examine each location with 2 photos
            for i, loc in enumerate(locations_with_2):
                if i >= 5:  # Limit detailed output to first 5 locations
                    print(f"  ... and {len(locations_with_2) - 5} more locations")
                    break
                    
                lat, lng = loc['latitude'], loc['longitude']
                print(f"\n  Location {i+1}: Lat={lat}, Lng={lng}")
                
                # Get the photos at this location
                cursor.execute("""
                    SELECT id, filename, library_id, hash, marker_data
                    FROM photos 
                    WHERE latitude = ? AND longitude = ?
                """, (lat, lng))
                photos = cursor.fetchall()
                
                print("  Photos at this location:")
                for j, photo in enumerate(photos):
                    photo_id = photo['id']
                    filename = photo['filename']
                    library = photo['library_id']
                    hash_val = photo['hash']
                    
                    print(f"    Photo {j+1}: ID={photo_id}, Filename={filename}, Library={library}, Hash={hash_val}")
                    
                    # Check if these are actually the same photo (same hash)
                    if j > 0 and hash_val and hash_val == photos[0]['hash']:
                        print(f"    ⚠️ WARNING: This photo has the same hash as Photo 1 - likely duplicate!")
                    
                    # Analyze marker_data if available
                    marker_data = photo['marker_data']
                    if marker_data:
                        try:
                            # Try to parse as JSON
                            marker_json = json.loads(marker_data)
                            print(f"    Marker data: {json.dumps(marker_json, indent=2)[:100]}...")
                        except:
                            # If not valid JSON, just show as text
                            print(f"    Marker data: {marker_data[:50]}...")
        
        # Get stats for libraries
        print("\nLibrary Statistics:")
        cursor.execute("""
            SELECT l.id, l.name, COUNT(p.id) as photo_count,
                   SUM(CASE WHEN p.latitude IS NOT NULL AND p.longitude IS NOT NULL THEN 1 ELSE 0 END) as geotagged_count
            FROM libraries l
            LEFT JOIN photos p ON l.id = p.library_id
            GROUP BY l.id, l.name
        """)
        libraries = cursor.fetchall()
        
        for lib in libraries:
            lib_id = lib['id']
            name = lib['name']
            photo_count = lib['photo_count']
            geotagged = lib['geotagged_count']
            
            print(f"  Library: {name} (ID: {lib_id})")
            print(f"    Total photos: {photo_count}")
            percent = (geotagged/photo_count*100) if photo_count > 0 else 0
            print(f"    Photos with coordinates: {geotagged} ({percent:.1f}%)")
            
            # Check for duplicate filenames in this library
            cursor.execute("""
                SELECT filename, COUNT(*) as count 
                FROM photos 
                WHERE library_id = ?
                GROUP BY filename 
                HAVING count > 1
            """, (lib_id,))
            duplicate_files = cursor.fetchall()
            
            if duplicate_files:
                print(f"    ⚠️ Found {len(duplicate_files)} duplicate filenames in this library!")
                for df in duplicate_files[:3]:  # Show first 3 examples
                    print(f"      {df['filename']} appears {df['count']} times")
                if len(duplicate_files) > 3:
                    print(f"      ... and {len(duplicate_files) - 3} more duplicate filenames")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    db_paths = [
        os.path.join(os.getcwd(), 'data', 'photo_library.db'),
        os.path.join(os.getcwd(), 'photo_library.db')
    ]
    
    # If a command line argument is provided, use it as the database path
    if len(sys.argv) > 1:
        db_paths.insert(0, sys.argv[1])
    
    db_found = False
    for path in db_paths:
        if os.path.exists(path):
            check_cluster_issues(path)
            db_found = True
            break
    
    if not db_found:
        print("No database file found.")
        print("\nAvailable files in current directory:")
        try:
            for file in os.listdir(os.getcwd()):
                if file.endswith('.db'):
                    print(f"  {file} ({os.path.getsize(file) / 1024:.1f} KB)")
        except:
            print("  Error listing directory contents")
