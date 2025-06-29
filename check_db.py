import sqlite3
import os

# Get the current directory
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# Check if the database file exists
db_path = os.path.join(current_dir, "data", "photo_library.db")
print(f"Looking for database at: {db_path}")
if not os.path.exists(db_path):
    print(f"Database file not found at {db_path}")
    
    # Try alternate location
    db_path = os.path.join(current_dir, "photo_library.db")
    print(f"Trying alternate location: {db_path}")
    if not os.path.exists(db_path):
        print(f"Database file not found at alternate location either")
        exit(1)

# Connect to the database
print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get list of tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in the database:")
for table in tables:
    print(f"  - {table[0]}")

# Look for duplicate filenames
print("\nChecking for duplicate filenames:")
cursor.execute("""
SELECT filename, COUNT(*) as count 
FROM photos 
GROUP BY filename 
HAVING count > 1
ORDER BY count DESC
LIMIT 10
""")
duplicates = cursor.fetchall()

if not duplicates:
    print("No duplicate filenames found")
else:
    print(f"Found {len(duplicates)} filenames with duplicates")
    for filename, count in duplicates:
        print(f"  - {filename}: {count} occurrences")
        
        # Get details about these duplicates
        cursor.execute("""
        SELECT id, path, filename, latitude, longitude
        FROM photos
        WHERE filename = ?
        LIMIT 5
        """, (filename,))
        
        details = cursor.fetchall()
        for id, path, filename, lat, lon in details:
            print(f"    * ID: {id}, Path: {path}, GPS: {lat:.6f}, {lon:.6f}")
            
            # Check if there's a specific duplicate with path matching IMG_8338.HEIC
            if "IMG_8338.HEIC" in filename:
                print("\nFound the specific IMG_8338.HEIC case mentioned in logs:")
                cursor.execute("""
                SELECT id, path, filename, latitude, longitude
                FROM photos
                WHERE filename = 'IMG_8338.HEIC'
                """)
                heic_details = cursor.fetchall()
                print(f"  Found {len(heic_details)} entries for IMG_8338.HEIC:")
                for h_id, h_path, h_filename, h_lat, h_lon in heic_details:
                    print(f"    * ID: {h_id}, Path: {h_path}, GPS: {h_lat:.6f}, {h_lon:.6f}")

conn.close()
