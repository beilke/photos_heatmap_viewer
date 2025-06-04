import sqlite3
import argparse
import os
import json
from datetime import datetime

def add_tag_to_photos(db_path, tag, where_clause=None):
    """Add a tag to photos matching the where clause"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if where_clause:
        # Get photos that match the where clause
        cursor.execute(f"SELECT id, tags FROM photos WHERE {where_clause}")
    else:
        # Get all photos
        cursor.execute("SELECT id, tags FROM photos")
    
    rows = cursor.fetchall()
    updated_count = 0
    
    for row in rows:
        photo_id, tags_str = row
        
        # Parse existing tags or create empty list
        tags = []
        if tags_str:
            try:
                tags = json.loads(tags_str)
            except json.JSONDecodeError:
                tags = [t.strip() for t in tags_str.split(',')]
        
        # Add new tag if not already present
        if tag not in tags:
            tags.append(tag)
            tags_json = json.dumps(tags)
            
            cursor.execute("UPDATE photos SET tags = ? WHERE id = ?", 
                          (tags_json, photo_id))
            updated_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Added tag '{tag}' to {updated_count} photos")

def get_stats(db_path):
    """Get statistics about the photo database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Total photos
    cursor.execute("SELECT COUNT(*) FROM photos")
    total_photos = cursor.fetchone()[0]
    
    # Geotagged photos
    cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    geotagged_photos = cursor.fetchone()[0]
      # Date range
    cursor.execute("SELECT MIN(datetime), MAX(datetime) FROM photos WHERE datetime IS NOT NULL")
    date_range = cursor.fetchone()
    
    conn.close()
    
    print("==== Photo Database Statistics ====")
    print(f"Total photos: {total_photos}")
    
    if total_photos > 0:
        percentage = geotagged_photos/total_photos*100
        print(f"Geotagged photos: {geotagged_photos} ({percentage:.1f}%)")
    else:
        print("Geotagged photos: 0 (0.0%)")
    
    if date_range[0] and date_range[1]:
        start_date = date_range[0].split('T')[0] if 'T' in date_range[0] else date_range[0]
        end_date = date_range[1].split('T')[0] if 'T' in date_range[1] else date_range[1]
        print(f"Date range: {start_date} to {end_date}")

def delete_photos(db_path, where_clause):
    """Delete photos matching the where clause"""
    if not where_clause:
        print("Error: You must provide a WHERE clause to delete photos")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First count how many will be deleted
    cursor.execute(f"SELECT COUNT(*) FROM photos WHERE {where_clause}")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("No photos match the criteria")
        conn.close()
        return
    
    confirm = input(f"This will delete {count} photos. Are you sure? (y/n): ")
    if confirm.lower() != 'y':
        print("Deletion cancelled")
        conn.close()
        return
    
    cursor.execute(f"DELETE FROM photos WHERE {where_clause}")
    conn.commit()
    
    print(f"Deleted {count} photos")
    conn.close()

def vacuum_database(db_path):
    """Optimize the database by running VACUUM"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Running VACUUM to optimize database...")
    cursor.execute("VACUUM")
    
    conn.close()
    print("Database optimization complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Photo database maintenance tools')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--add-tag', help='Add a tag to photos')
    parser.add_argument('--where', help='SQL WHERE clause for filtering photos')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--delete', action='store_true', help='Delete photos (requires --where)')
    parser.add_argument('--optimize', action='store_true', help='Optimize the database')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        print(f"Error: Database file '{args.db}' not found")
        exit(1)
    
    if args.add_tag:
        add_tag_to_photos(args.db, args.add_tag, args.where)
    
    if args.stats:
        get_stats(args.db)
    
    if args.delete:
        if not args.where:
            print("Error: --delete requires --where clause")
        else:
            delete_photos(args.db, args.where)
    
    if args.optimize:
        vacuum_database(args.db)
