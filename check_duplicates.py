import sqlite3
import os
import sys
import argparse

def check_database_duplicates(db_path, limit=None, specific_file=None):
    """Check for duplicate entries in the photos table."""
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get database information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables in the database:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check for specific filename if provided
        if specific_file:
            print(f"\nChecking for '{specific_file}' in database...")
            cursor.execute("""
                SELECT id, filename, path, latitude, longitude 
                FROM photos 
                WHERE filename LIKE ? 
                ORDER BY filename
            """, (f'%{specific_file}%',))
            
            matches = cursor.fetchall()
            if matches:
                print(f"Found {len(matches)} occurrences of '{specific_file}':")
                for row in matches:
                    print(f"  * ID: {row[0]}, Filename: {row[1]}, Path: {row[2]}, GPS: {row[3]}, {row[4]}")
            else:
                print(f"No occurrences of '{specific_file}' found.")
            
            return
        
        # Check for exact duplicate file paths
        print("\nChecking for exact duplicate file paths...")
        cursor.execute("""
            SELECT path, COUNT(*) as count 
            FROM photos 
            GROUP BY path 
            HAVING count > 1
        """)
        duplicate_paths = cursor.fetchall()
        
        # Show exact duplicate paths
        if duplicate_paths:
            print(f"Found {len(duplicate_paths)} exact duplicate file paths:")
            for path, count in duplicate_paths:
                print(f"  {path} (appears {count} times)")
                # Show the actual duplicate records
                cursor.execute("SELECT id, filename, path FROM photos WHERE path = ?", (path,))
                for record in cursor.fetchall():
                    print(f"    ID: {record[0]}, Filename: {record[1]}, Path: {record[2]}")
        else:
            print("No duplicate file paths found.")
        
        # Check for duplicate filenames (same filename in different locations)
        print("\nChecking for duplicate filenames in different locations...")
        cursor.execute("""
            SELECT filename, COUNT(*) as count 
            FROM photos 
            GROUP BY filename 
            HAVING count > 1
            ORDER BY count DESC
        """)
        duplicate_filenames = cursor.fetchall()
        
        # Show duplicate filenames
        if duplicate_filenames:
            limit_text = f" (showing top {limit})" if limit else ""
            print(f"Found {len(duplicate_filenames)} filenames with duplicates{limit_text}")
            
            # Apply limit if specified
            if limit:
                duplicate_filenames = duplicate_filenames[:limit]
                
            for filename, count in duplicate_filenames:
                print(f"  - {filename}: {count} occurrences")
                cursor.execute("""
                    SELECT id, path, latitude, longitude
                    FROM photos 
                    WHERE filename = ?
                    ORDER BY id
                """, (filename,))
                for record in cursor.fetchall():
                    print(f"    * ID: {record[0]}, Path: {record[1]}, GPS: {record[2]}, {record[3]}")
        else:
            print("No duplicate filenames found.")
        
        # Get overall statistics
        cursor.execute("SELECT COUNT(*) FROM photos")
        total_photos = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT filename) FROM photos")
        unique_filenames = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT path) FROM photos WHERE path IS NOT NULL")
        unique_paths = cursor.fetchone()[0]
        
        print("\nDatabase statistics:")
        print(f"  Total photos: {total_photos}")
        print(f"  Unique filenames: {unique_filenames}")
        print(f"  Unique file paths: {unique_paths}")
        print(f"  Duplicate filenames: {total_photos - unique_filenames}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check for duplicates in photo database")
    parser.add_argument("--file", "-f", help="Search for a specific filename")
    parser.add_argument("--limit", "-l", type=int, help="Limit number of results")
    args = parser.parse_args()
    
    db_paths = [
        os.path.join(os.getcwd(), 'data', 'photo_library.db'),
        os.path.join(os.getcwd(), 'photo_library.db')
    ]
    
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    for path in db_paths:
        print(f"Looking for database at: {path}")
        if os.path.exists(path):
            print(f"Connecting to database: {path}")
            check_database_duplicates(path, args.limit, args.file)
            break
    else:
        print("No database file found.")
