#!/usr/bin/env python
"""
Add indexes to photo_library.db to improve query performance.
This is especially helpful for large photo libraries.
"""

import os
import sqlite3
import logging
import time
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('db_optimize.log')
    ]
)
logger = logging.getLogger(__name__)

def add_indexes_to_db(db_path):
    """Add performance indexes to the photo_library database"""
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return False

    try:
        logger.info(f"Opening database at {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current table structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        logger.info(f"Found {len(tables)} tables in database")
        
        # Get current indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
        existing_indexes = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(existing_indexes)} existing indexes")

        # Define the indexes we want to create
        indexes_to_add = [
            # Photos table indexes
            {
                "name": "idx_photos_filename",
                "sql": "CREATE INDEX IF NOT EXISTS idx_photos_filename ON photos(filename);"
            },
            {
                "name": "idx_photos_path",
                "sql": "CREATE INDEX IF NOT EXISTS idx_photos_path ON photos(path);"
            },
            {
                "name": "idx_photos_location",
                "sql": "CREATE INDEX IF NOT EXISTS idx_photos_location ON photos(latitude, longitude);"
            },
            {
                "name": "idx_photos_library_id",
                "sql": "CREATE INDEX IF NOT EXISTS idx_photos_library_id ON photos(library_id);"
            },
            {
                "name": "idx_photos_datetime",
                "sql": "CREATE INDEX IF NOT EXISTS idx_photos_datetime ON photos(datetime);"
            },
            # Libraries table indexes
            {
                "name": "idx_libraries_name",
                "sql": "CREATE INDEX IF NOT EXISTS idx_libraries_name ON libraries(name);"
            }
        ]
        
        # Check for table existence before creating indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos';")
        photos_table_exists = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libraries';")
        libraries_table_exists = cursor.fetchone() is not None
        
        if not photos_table_exists:
            logger.warning("Photos table not found in database, skipping photo indexes")
            # Filter out photo table indexes
            indexes_to_add = [idx for idx in indexes_to_add if not idx["name"].startswith("idx_photos_")]
        
        if not libraries_table_exists:
            logger.warning("Libraries table not found in database, skipping library indexes")
            # Filter out library table indexes
            indexes_to_add = [idx for idx in indexes_to_add if not idx["name"].startswith("idx_libraries_")]
            
        # Create the indexes
        created_count = 0
        skipped_count = 0
        
        # Analyze the database first
        start_time = time.time()
        logger.info("Analyzing database...")
        cursor.execute("ANALYZE;")
        logger.info(f"Database analysis completed in {time.time() - start_time:.2f} seconds")
        
        for idx in indexes_to_add:
            if idx["name"] in existing_indexes:
                logger.info(f"Index {idx['name']} already exists, skipping")
                skipped_count += 1
                continue
                
            logger.info(f"Creating index {idx['name']}...")
            start_time = time.time()
            cursor.execute(idx["sql"])
            logger.info(f"Created index {idx['name']} in {time.time() - start_time:.2f} seconds")
            created_count += 1
            
        # Optimize the database
        logger.info("Running VACUUM to optimize database...")
        start_time = time.time()
        cursor.execute("VACUUM;")
        vacuum_time = time.time() - start_time
        logger.info(f"VACUUM completed in {vacuum_time:.2f} seconds")
        
        logger.info("Running ANALYZE to update statistics...")
        start_time = time.time()
        cursor.execute("ANALYZE;")
        analyze_time = time.time() - start_time
        logger.info(f"ANALYZE completed in {analyze_time:.2f} seconds")
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        logger.info(f"Database optimization complete: {created_count} indexes created, {skipped_count} already existed")
        return True
        
    except Exception as e:
        logger.exception(f"Error adding indexes to database: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add performance indexes to photo_library database')
    parser.add_argument('--db', default=None, help='Path to the photo library database')
    
    args = parser.parse_args()
    
    # Determine database path
    db_path = args.db
    if db_path is None:
        # Check common locations
        possible_paths = [
            os.path.join(os.getcwd(), 'data', 'photo_library.db'),
            os.path.join(os.getcwd(), 'photo_library.db')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                break
                
    if db_path is None or not os.path.exists(db_path):
        logger.error("Database not found. Please specify the path with --db")
        exit(1)
        
    logger.info(f"Using database at {db_path}")
    
    if add_indexes_to_db(db_path):
        logger.info("Database optimization completed successfully")
    else:
        logger.error("Failed to optimize database")
        exit(1)
