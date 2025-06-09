#!/usr/bin/env python3
import os
import sqlite3
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_database(db_path='data/photo_library.db'):
    """Add uniqueness constraints and deduplicate photo entries"""
    logger.info(f"Updating database schema at {db_path}")
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return False
        
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Start a transaction
        conn.execute('BEGIN TRANSACTION')
        
        # Create a temporary table to hold unique photos
        logger.info("Creating temporary table for deduplication")
        cursor.execute('''
        CREATE TABLE temp_photos (
          id INTEGER PRIMARY KEY,
          filename TEXT,
          path TEXT,
          latitude REAL,
          longitude REAL,
          datetime TEXT,
          tags TEXT,
          hash TEXT,
          library_id INTEGER,
          marker_data TEXT,
          FOREIGN KEY (library_id) REFERENCES libraries(id)
        )
        ''')
        
        # Identify duplicate photos by filename within the same library
        logger.info("Finding duplicate photos...")
        cursor.execute('''
        SELECT library_id, filename, COUNT(*) as count 
        FROM photos 
        GROUP BY library_id, filename 
        HAVING count > 1
        ''')
        duplicates = cursor.fetchall()
        logger.info(f"Found {len(duplicates)} files with duplicates")
        
        # Insert only unique photos into the temp table
        logger.info("Deduplicating photos...")
        cursor.execute('''
        INSERT INTO temp_photos
        SELECT * FROM photos 
        WHERE rowid IN (
            SELECT MIN(rowid) 
            FROM photos 
            GROUP BY filename, library_id
        )
        ''')
        
        # Get counts before and after
        cursor.execute("SELECT COUNT(*) FROM photos")
        original_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM temp_photos")
        new_count = cursor.fetchone()[0]
        
        logger.info(f"Removed {original_count - new_count} duplicate records")
        
        # Drop old table and rename new one
        logger.info("Replacing photos table with deduplicated version")
        cursor.execute("DROP TABLE photos")
        cursor.execute("ALTER TABLE temp_photos RENAME TO photos")
        
        # Recreate indexes
        logger.info("Recreating indexes")
        cursor.execute('CREATE INDEX idx_coords ON photos(latitude, longitude)')
        cursor.execute('CREATE INDEX idx_datetime ON photos(datetime)')
        cursor.execute('CREATE INDEX idx_filename ON photos(filename)')
        cursor.execute('CREATE INDEX idx_hash ON photos(hash)')
        cursor.execute('CREATE INDEX idx_path ON photos(path)')
        cursor.execute('CREATE INDEX idx_library_id ON photos(library_id)')
        
        # Create a new unique index to prevent future duplicates
        logger.info("Adding unique constraint to prevent future duplicates")
        cursor.execute('CREATE UNIQUE INDEX idx_lib_filename ON photos(library_id, filename)')
        
        # Commit transaction
        conn.commit()
        logger.info("Database schema update complete")
        
        # Run VACUUM to optimize database
        logger.info("Optimizing database...")
        conn.execute('VACUUM')
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating database: {e}")
        # Rollback transaction
        try:
            conn.rollback()
        except:
            pass
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update photo database schema to prevent duplicates")
    parser.add_argument('--db', default='data/photo_library.db', help='Database file path')
    args = parser.parse_args()
    
    # Ensure data directory exists
    db_dir = os.path.dirname(args.db)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"Created directory: {db_dir}")
        
    success = migrate_database(args.db)
    
    if success:
        print("Successfully updated database schema and removed duplicates")
    else:
        print("Failed to update database schema")
