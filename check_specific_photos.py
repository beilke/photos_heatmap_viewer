import sqlite3
import os

def check_specific_photos():
    """Check specific photos that may have duplicates across libraries but at different coordinates"""
    
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
    
    # Filenames to check - these appear in both libraries
    filenames_to_check = [
        'IMG_9343.jpg', 'IMG_9345.jpg', 'IMG_9810.jpg', 'IMG_9812.jpg'
    ]
    
    # Check each filename
    print("Checking specific photos that exist in multiple libraries:")
    for filename in filenames_to_check:
        print(f"\nChecking {filename}:")
        cursor.execute("""
            SELECT id, filename, path, library_id, latitude, longitude
            FROM photos
            WHERE filename = ?
            ORDER BY library_id, id
        """, (filename,))
        
        results = cursor.fetchall()
        if not results:
            print(f"  No entries found for {filename}")
            continue
            
        print(f"  Found {len(results)} entries:")
        for row in results:
            print(f"  ID: {row['id']}, Library: {row['library_id']}, Coordinates: {row['latitude']}, {row['longitude']}")
            print(f"  Path: {row['path']}")
    
    # Now check what would be returned after our deduplication query
    print("\nNow checking what would be returned after deduplication:")
    
    placeholders = ", ".join(["?" for _ in filenames_to_check])
    query = f"""
    WITH RankedPhotos AS (
        SELECT 
            p.id, p.filename, p.path, p.latitude, p.longitude, p.library_id,
            ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
        FROM photos p
        WHERE p.filename IN ({placeholders})
    )
    SELECT id, filename, path, library_id, latitude, longitude
    FROM RankedPhotos
    WHERE rn = 1
    """
    
    cursor.execute(query, filenames_to_check)
    deduplicated = cursor.fetchall()
    
    print(f"After deduplication, {len(deduplicated)} entries would remain:")
    for row in deduplicated:
        print(f"  ID: {row['id']}, Filename: {row['filename']}, Library: {row['library_id']}")
        print(f"  Coordinates: {row['latitude']}, {row['longitude']}")
    
    conn.close()

if __name__ == "__main__":
    check_specific_photos()
