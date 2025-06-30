import sqlite3
import os

def check_sql_deduplication():
    """Check if our SQL deduplication query is working correctly"""
    
    # Connect to database
    db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(os.getcwd(), 'photo_library.db')
        if not os.path.exists(db_path):
            print(f"Database not found: {db_path}")
            return
            
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get total photos with GPS
    cursor.execute("""
        SELECT COUNT(*) as total 
        FROM photos 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    result = cursor.fetchone()
    total_with_gps = result["total"]
    print(f"Total photos with GPS data before deduplication: {total_with_gps}")
    
    # Get count of unique photos using our deduplication query
    cursor.execute("""
        WITH RankedPhotos AS (
            SELECT 
                p.id, p.filename, p.path, p.latitude, p.longitude, 
                ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
            FROM photos p
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        )
        SELECT COUNT(*) as total_photos 
        FROM RankedPhotos 
        WHERE rn = 1
    """)
    result = cursor.fetchone()
    unique_photos = result["total_photos"]
    print(f"Total unique photos with GPS data after deduplication: {unique_photos}")
    print(f"Duplicates removed: {total_with_gps - unique_photos}")
    
    # Show examples of duplicate groups
    print("\nExamples of duplicate photos (same filename, same coordinates):")
    cursor.execute("""
        WITH DupeGroups AS (
            SELECT filename, latitude, longitude, COUNT(*) as count
            FROM photos
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY filename, latitude, longitude
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        )
        SELECT 
            d.filename, d.latitude, d.longitude, d.count,
            GROUP_CONCAT(p.path, '\n') as paths,
            GROUP_CONCAT(p.library_id, ',') as library_ids
        FROM DupeGroups d
        JOIN photos p ON p.filename = d.filename 
                    AND p.latitude = d.latitude 
                    AND p.longitude = d.longitude
        GROUP BY d.filename, d.latitude, d.longitude
    """)
    dupes = cursor.fetchall()
    
    for d in dupes:
        print(f"\n{d['filename']} at {d['latitude']},{d['longitude']} ({d['count']} instances):")
        print(f"Library IDs: {d['library_ids']}")
        print(f"Paths:\n{d['paths']}")
    
    # Check if our query in server.py is working as expected
    print("\nTesting the exact query from server.py:")
    cursor.execute("""
        WITH RankedPhotos AS (
            SELECT 
                p.id, p.filename, p.path, p.latitude, p.longitude, p.datetime, 
                p.marker_data, p.library_id, l.name as library_name,
                ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
            FROM photos p
            LEFT JOIN libraries l ON p.library_id = l.id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        )
        SELECT 
            id, filename, path, latitude, longitude, datetime, 
            marker_data, library_id, library_name
        FROM RankedPhotos
        WHERE rn = 1
        LIMIT 5
    """)
    sample_results = cursor.fetchall()
    
    print(f"Sample results from deduplication query (first 5 rows):")
    for row in sample_results:
        print(f"ID: {row['id']}, Filename: {row['filename']}, Library: {row['library_id']}")
    
    # Check for any potential duplicates in results (shouldn't be any)
    print("\nVerifying no duplicates in final result set:")
    cursor.execute("""
        WITH DedupResults AS (
            WITH RankedPhotos AS (
                SELECT 
                    p.id, p.filename, p.path, p.latitude, p.longitude, p.datetime, 
                    p.marker_data, p.library_id, l.name as library_name,
                    ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
                FROM photos p
                LEFT JOIN libraries l ON p.library_id = l.id
                WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
            )
            SELECT 
                id, filename, path, latitude, longitude, datetime, 
                marker_data, library_id, library_name
            FROM RankedPhotos
            WHERE rn = 1
        )
        SELECT filename, latitude, longitude, COUNT(*) as count
        FROM DedupResults
        GROUP BY filename, latitude, longitude
        HAVING COUNT(*) > 1
        LIMIT 5
    """)
    
    potential_dupes = cursor.fetchall()
    if potential_dupes:
        print(f"WARNING: Found {len(potential_dupes)} potential duplicates in final result set!")
        for d in potential_dupes:
            print(f"  {d['filename']} at {d['latitude']},{d['longitude']} ({d['count']} instances)")
    else:
        print("No duplicates found in final result set - SQL query is working correctly.")
    
    conn.close()

if __name__ == "__main__":
    check_sql_deduplication()
