import sqlite3
import os

def check_near_duplicates():
    """
    Check for photos with identical filenames but slightly different coordinates.
    These would appear as separate markers but look like duplicates in clusters.
    """
    print("Checking for photos with same filenames but different coordinates...")
    
    # Connect to database
    try:
        db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
        if not os.path.exists(db_path):
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            
        print(f"Using database at {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find photos with same filename but different coordinates
        cursor.execute("""
        SELECT p1.id as id1, p1.filename, p1.library_id as lib1, p1.latitude as lat1, p1.longitude as lon1,
               p2.id as id2, p2.library_id as lib2, p2.latitude as lat2, p2.longitude as lon2,
               ABS(p1.latitude - p2.latitude) as lat_diff,
               ABS(p1.longitude - p2.longitude) as lon_diff
        FROM photos p1
        JOIN photos p2 ON p1.filename = p2.filename AND p1.id != p2.id
        WHERE p1.latitude IS NOT NULL AND p1.longitude IS NOT NULL
          AND p2.latitude IS NOT NULL AND p2.longitude IS NOT NULL
          AND (ABS(p1.latitude - p2.latitude) <= 0.001 OR ABS(p1.longitude - p2.longitude) <= 0.001)
        LIMIT 100
        """)
        
        near_duplicates = cursor.fetchall()
        
        if not near_duplicates:
            print("No near-duplicates found with similar coordinates")
        else:
            print(f"Found {len(near_duplicates)} pairs of photos with same filename but slightly different coordinates:")
            for row in near_duplicates:
                print(f"Filename: {row['filename']}")
                print(f"  Photo 1: ID={row['id1']}, Library={row['lib1']}, Coordinates={row['lat1']}, {row['lon1']}")
                print(f"  Photo 2: ID={row['id2']}, Library={row['lib2']}, Coordinates={row['lat2']}, {row['lon2']}")
                print(f"  Difference: Lat={row['lat_diff']:.6f}, Lon={row['lon_diff']:.6f}")
                print()
        
        # Also check for photos with same filename but very different coordinates
        print("\nChecking for photos with same filename but significantly different coordinates...")
        cursor.execute("""
        SELECT p1.id as id1, p1.filename, p1.library_id as lib1, p1.path as path1, p1.latitude as lat1, p1.longitude as lon1,
               p2.id as id2, p2.library_id as lib2, p2.path as path2, p2.latitude as lat2, p2.longitude as lon2,
               ABS(p1.latitude - p2.latitude) as lat_diff,
               ABS(p1.longitude - p2.longitude) as lon_diff
        FROM photos p1
        JOIN photos p2 ON p1.filename = p2.filename AND p1.id != p2.id
        WHERE p1.latitude IS NOT NULL AND p1.longitude IS NOT NULL
          AND p2.latitude IS NOT NULL AND p2.longitude IS NOT NULL
          AND (ABS(p1.latitude - p2.latitude) > 0.001 OR ABS(p1.longitude - p2.longitude) > 0.001)
        ORDER BY p1.filename
        LIMIT 100
        """)
        
        diff_coords = cursor.fetchall()
        
        if not diff_coords:
            print("No photos found with same filename but significantly different coordinates")
        else:
            print(f"Found {len(diff_coords)} pairs of photos with same filename but different coordinates:")
            for row in diff_coords:
                print(f"Filename: {row['filename']}")
                print(f"  Photo 1: ID={row['id1']}, Library={row['lib1']}")
                print(f"    Path: {row['path1']}")
                print(f"    Coordinates: {row['lat1']}, {row['lon1']}")
                print(f"  Photo 2: ID={row['id2']}, Library={row['lib2']}")
                print(f"    Path: {row['path2']}")
                print(f"    Coordinates: {row['lat2']}, {row['lon2']}")
                print(f"  Difference: Lat={row['lat_diff']:.6f}, Lon={row['lon_diff']:.6f}")
                print()
        
        # Count how many are in a cluster
        print("\nChecking how many of these photos might appear in the same cluster...")
        cursor.execute("""
        SELECT p1.filename, COUNT(*) as instances,
               COUNT(DISTINCT p1.library_id) as num_libraries,
               GROUP_CONCAT(DISTINCT p1.library_id) as libraries
        FROM photos p1
        JOIN photos p2 ON p1.filename = p2.filename AND p1.id != p2.id
        WHERE p1.latitude IS NOT NULL AND p1.longitude IS NOT NULL
          AND p2.latitude IS NOT NULL AND p2.longitude IS NOT NULL
        GROUP BY p1.filename
        ORDER BY instances DESC
        LIMIT 20
        """)
        
        filename_counts = cursor.fetchall()
        
        if filename_counts:
            print(f"Top filenames appearing multiple times:")
            for row in filename_counts:
                print(f"  {row['filename']}: {row['instances']} instances across {row['num_libraries']} libraries ({row['libraries']})")
        
        conn.close()
    except Exception as e:
        print(f"Error checking duplicates: {e}")

if __name__ == "__main__":
    check_near_duplicates()
