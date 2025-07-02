import sqlite3
import os
import json
import sys

def check_cluster_duplicates(lat=None, lon=None, filename=None, radius=0.0001):
    """Check for duplicate photos in a cluster based on coordinates or filename"""
    
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
    
    # Search by coordinates with a small radius if provided
    if lat is not None and lon is not None:
        print(f"Checking photos at coordinates: {lat}, {lon} (radius: {radius})")
        cursor.execute("""
            SELECT id, filename, path, library_id, latitude, longitude
            FROM photos
            WHERE latitude BETWEEN ? AND ?
              AND longitude BETWEEN ? AND ?
            ORDER BY filename
        """, (lat - radius, lat + radius, lon - radius, lon + radius))
        
    # Or search by filename pattern if provided
    elif filename:
        print(f"Checking photos with filename like: {filename}")
        cursor.execute("""
            SELECT id, filename, path, library_id, latitude, longitude
            FROM photos
            WHERE filename LIKE ?
            ORDER BY filename
        """, (f'%{filename}%',))
    
    # Default to recent photos if no search criteria specified
    else:
        print("No search criteria provided. Showing recent photos with GPS data:")
        cursor.execute("""
            SELECT id, filename, path, library_id, latitude, longitude
            FROM photos
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY id DESC
            LIMIT 20
        """)
    
    rows = cursor.fetchall()
    print(f"Found {len(rows)} matching photos")
    
    # Group by filename to find duplicates
    filename_groups = {}
    for row in rows:
        key = row['filename']
        if key not in filename_groups:
            filename_groups[key] = []
        filename_groups[key].append(row)
    
    # Count unique filenames and duplicates
    unique_filenames = len(filename_groups)
    print(f"Found {unique_filenames} unique filenames in this cluster")
    
    # Show duplicate details
    print("\nDuplicates by filename:")
    for filename, group in filename_groups.items():
        if len(group) > 1:
            print(f"\n{filename} ({len(group)} copies):")
            for row in group:
                print(f"  ID: {row['id']}, Path: {row['path']}")
                print(f"  Library: {row['library_id']}, GPS: {row['latitude']}, {row['longitude']}")
    
    # Now check what would be returned by our API deduplication
    print("\nChecking what would be returned by the API deduplication query:")
    
    if lat is not None and lon is not None:
        cursor.execute("""
            WITH RankedPhotos AS (
                SELECT 
                    p.id, p.filename, p.path, p.latitude, p.longitude, p.library_id,
                    ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
                FROM photos p
                WHERE p.latitude BETWEEN ? AND ?
                  AND p.longitude BETWEEN ? AND ?
            )
            SELECT id, filename, path, library_id, latitude, longitude
            FROM RankedPhotos
            WHERE rn = 1
        """, (lat - radius, lat + radius, lon - radius, lon + radius))
    else:
        # Use the same subset of photos as above
        photo_ids = ",".join([str(row['id']) for row in rows])
        if not photo_ids:
            print("No photos to check with deduplication query")
            return
            
        cursor.execute(f"""
            WITH RankedPhotos AS (
                SELECT 
                    p.id, p.filename, p.path, p.latitude, p.longitude, p.library_id,
                    ROW_NUMBER() OVER(PARTITION BY p.filename, p.latitude, p.longitude ORDER BY p.id) as rn
                FROM photos p
                WHERE p.id IN ({photo_ids})
            )
            SELECT id, filename, path, library_id, latitude, longitude
            FROM RankedPhotos
            WHERE rn = 1
        """)
    
    deduplicated = cursor.fetchall()
    print(f"After deduplication: {len(deduplicated)} unique photos would be in the API response")
    
    print("\nPhotos after API deduplication:")
    for row in deduplicated:
        print(f"  {row['filename']} (ID: {row['id']}, Library: {row['library_id']})")
        
    # Check for uniqueness within the query result itself
    filename_coords = {}
    for row in deduplicated:
        key = f"{row['filename']}_{row['latitude']}_{row['longitude']}"
        if key in filename_coords:
            print(f"\nWARNING: Duplicate found even after deduplication!")
            print(f"  {row['filename']} at {row['latitude']}, {row['longitude']}")
            print(f"  First instance: ID={filename_coords[key]['id']}, Library={filename_coords[key]['library_id']}")
            print(f"  Duplicate: ID={row['id']}, Library={row['library_id']}")
        else:
            filename_coords[key] = row
        
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        try:
            lat = float(sys.argv[1])
            lon = float(sys.argv[2])
            radius = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0001
            check_cluster_duplicates(lat, lon, None, radius)
        except ValueError:
            print("Error: Coordinates must be valid numbers")
            print("Usage: python tools/check_cluster.py [latitude] [longitude] [optional_radius]")
            sys.exit(1)
    elif len(sys.argv) == 2:
        check_cluster_duplicates(None, None, sys.argv[1])
    else:
        print("Checking recent photos with GPS data")
        check_cluster_duplicates()
