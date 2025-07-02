import sqlite3
import os

def check_photo_by_id(photo_id):
    """Check details of a specific photo by ID"""
    
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
    
    # Check the specific photo
    cursor.execute("""
        SELECT id, filename, path, library_id
        FROM photos
        WHERE id = ?
    """, (photo_id,))
    
    result = cursor.fetchall()
    print(f"Found {len(result)} photos with ID {photo_id}:")
    
    for row in result:
        print(f"  ID: {row['id']}, Filename: {row['filename']}")
        print(f"  Path: {row['path']}")
        print(f"  Library ID: {row['library_id']}")
        print()
    
    # Check for other photos with the same filename
    if len(result) > 0:
        cursor.execute("""
            SELECT id, filename, path, library_id
            FROM photos
            WHERE filename = ? AND id != ?
        """, (result[0]['filename'], photo_id))
        
        dups = cursor.fetchall()
        print(f"Found {len(dups)} other photos with filename '{result[0]['filename']}':")
        
        for row in dups:
            print(f"  ID: {row['id']}, Filename: {row['filename']}")
            print(f"  Path: {row['path']}")
            print(f"  Library ID: {row['library_id']}")
            print()
    
    conn.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Please provide a photo ID")
        print("Usage: python tools/check_photo.py [photo_id]")
        sys.exit(1)
        
    try:
        photo_id = int(sys.argv[1])
        check_photo_by_id(photo_id)
    except ValueError:
        print(f"Error: Photo ID must be a number. Got '{sys.argv[1]}'")
        sys.exit(1)
