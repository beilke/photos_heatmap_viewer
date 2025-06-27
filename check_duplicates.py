import sqlite3
import os
import sys

def check_database_duplicates(db_path):
    """Check for duplicate entries in the photos table based on full path."""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for exact duplicate file paths
        print("Checking for duplicate file paths...")
        cursor.execute("""
            SELECT path, COUNT(*) as count 
            FROM photos 
            GROUP BY path 
            HAVING count > 1
        """)
        duplicate_paths = cursor.fetchall()
        
        # Show exact duplicate paths
        if duplicate_paths:
            print(f"\nFound {len(duplicate_paths)} exact duplicate file paths:")
            for path, count in duplicate_paths:
                print(f"  {path} (appears {count} times)")
                # Show the actual duplicate records
                cursor.execute("SELECT id, filename, path FROM photos WHERE path = ?", (path,))
                for record in cursor.fetchall():
                    print(f"    ID: {record[0]}, Filename: {record[1]}, Path: {record[2]}")
        else:
            print("No duplicate file paths found.")
        
        # Get statistics about paths
        cursor.execute("SELECT COUNT(*) FROM photos WHERE path IS NOT NULL")
        total_photos_with_paths = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT path) FROM photos WHERE path IS NOT NULL")
        unique_paths = cursor.fetchone()[0]
        
        print("\nPath statistics:")
        print(f"  Total photos with paths: {total_photos_with_paths}")
        print(f"  Unique file paths: {unique_paths}")
        
        if total_photos_with_paths > unique_paths:
            print(f"  Duplicate paths: {total_photos_with_paths - unique_paths}")
        else:
            print("  All paths are unique.")
            
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
