import sqlite3
import os

def verify_deduplication():
    """
    Verify the effectiveness of the new deduplication strategy based on filename alone.
    This will check how many photos would be returned after deduplication.
    """
    print("Verifying deduplication strategy...")
    
    # Connect to database
    try:
        db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
        if not os.path.exists(db_path):
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            
        print(f"Using database at {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Count total photos with GPS data
        cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        total_photos = cursor.fetchone()[0]
        print(f"Total photos with GPS data: {total_photos}")
        
        # Count unique filenames
        cursor.execute("SELECT COUNT(DISTINCT filename) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        unique_filenames = cursor.fetchone()[0]
        print(f"Unique filenames with GPS data: {unique_filenames}")
        
        # Count photos that would be returned with the old deduplication strategy
        cursor.execute("""
        WITH RankedPhotos AS (
            SELECT 
                p.id, p.filename, p.latitude, p.longitude,
                ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
            FROM photos p
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        )
        SELECT COUNT(*) FROM RankedPhotos WHERE rn = 1
        """)
        old_dedup_count = cursor.fetchone()[0]
        print(f"Photos after old deduplication (by filename+coordinates): {old_dedup_count}")
        print(f"Old deduplication removed {total_photos - old_dedup_count} duplicates ({(total_photos - old_dedup_count) / total_photos * 100:.1f}%)")
        
        # Count photos that would be returned with the new deduplication strategy
        cursor.execute("""
        WITH RankedPhotos AS (
            SELECT 
                p.id, p.filename,
                ROW_NUMBER() OVER(PARTITION BY p.filename ORDER BY p.id) as rn
            FROM photos p
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        )
        SELECT COUNT(*) FROM RankedPhotos WHERE rn = 1
        """)
        new_dedup_count = cursor.fetchone()[0]
        print(f"Photos after new deduplication (by filename only): {new_dedup_count}")
        print(f"New deduplication removed {total_photos - new_dedup_count} duplicates ({(total_photos - new_dedup_count) / total_photos * 100:.1f}%)")
        
        # Check specific photos that were causing issues before
        cursor.execute("""
        WITH PhotoCounts AS (
            SELECT 
                filename, 
                COUNT(*) as instances,
                COUNT(DISTINCT CAST(latitude AS TEXT) || ',' || CAST(longitude AS TEXT)) as unique_locations
            FROM photos 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY filename
            HAVING COUNT(*) > 1
            ORDER BY instances DESC
        )
        SELECT * FROM PhotoCounts LIMIT 20
        """)
        
        print("\nExamples of filenames that appear multiple times:")
        print("{:<30} {:<10} {:<15}".format("Filename", "Instances", "Unique Locations"))
        print("-" * 55)
        
        for row in cursor.fetchall():
            print("{:<30} {:<10} {:<15}".format(
                row['filename'], row['instances'], row['unique_locations']
            ))
        
        conn.close()
    except Exception as e:
        print(f"Error verifying deduplication: {e}")

if __name__ == "__main__":
    verify_deduplication()
