import sqlite3
import os
import sys

def check_database_duplicates(db_path):
    """Check for duplicate entries in the photos table."""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for duplicate file paths
        print("Checking for duplicate file paths...")
        cursor.execute("""
            SELECT path, COUNT(*) as count 
            FROM photos 
            GROUP BY path 
            HAVING count > 1
        """)
        duplicate_paths = cursor.fetchall()
        
        # Check for duplicate coordinates (same lat/lng)
        print("Checking for duplicate coordinates...")
        cursor.execute("""
            SELECT latitude, longitude, COUNT(*) as count 
            FROM photos 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY latitude, longitude 
            HAVING count > 1
        """)
        duplicate_coords = cursor.fetchall()
        
        # Show duplicate paths
        if duplicate_paths:
            print(f"\nFound {len(duplicate_paths)} duplicate file paths:")
            for path, count in duplicate_paths:
                print(f"  {path} (appears {count} times)")
                # Show the actual duplicate records
                cursor.execute("SELECT id, path, latitude, longitude FROM photos WHERE path = ?", (path,))
                for record in cursor.fetchall():
                    print(f"    ID: {record[0]}, Path: {record[1]}, Lat: {record[2]}, Lng: {record[3]}")
        else:
            print("No duplicate file paths found.")
            
        # Show locations with multiple photos
        if duplicate_coords:
            print(f"\nFound {len(duplicate_coords)} locations with multiple photos:")
            for lat, lng, count in duplicate_coords:
                print(f"  Lat: {lat}, Lng: {lng} (has {count} photos)")
                # Show the actual photos at this location
                cursor.execute("SELECT id, filename, path FROM photos WHERE latitude = ? AND longitude = ? LIMIT 5", (lat, lng))
                photos = cursor.fetchall()
                for photo in photos:
                    print(f"    ID: {photo[0]}, Filename: {photo[1]}, Path: {photo[2]}")
                if count > 5:
                    print(f"    ... and {count - 5} more")
        else:
            print("No locations with multiple photos found.")

        # Display cluster statistics
        print("\nCluster statistics:")
        cursor.execute("""
            SELECT COUNT(DISTINCT latitude || '_' || longitude) AS unique_locations,
                   COUNT(*) AS total_photos
            FROM photos
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        stats = cursor.fetchone()
        print(f"  Unique locations: {stats[0]}")
        print(f"  Total photos with coordinates: {stats[1]}")
        print(f"  Average photos per location: {stats[1]/stats[0] if stats[0] > 0 else 0:.2f}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    db_paths = [
        os.path.join(os.getcwd(), 'data', 'photo_library.db'),
        os.path.join(os.getcwd(), 'photo_library.db')
    ]
    
    for path in db_paths:
        if os.path.exists(path):
            print(f"Checking database: {path}")
            check_database_duplicates(path)
            break
    else:
        print("No database file found.")
