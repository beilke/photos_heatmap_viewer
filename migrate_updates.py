#!/usr/bin/env python3
"""
Migration script to update library timestamps from text files to database.
This script helps transition from the file-based timestamp system to database storage.
"""

import os
import sqlite3
import glob
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_timestamps(data_dir=None, db_path=None):
    """
    Migrate timestamps from text files to database fields
    
    Args:
        data_dir (str): Directory containing last_update_*.txt files
        db_path (str): Path to the database file
    """
    # Determine paths
    if data_dir is None:
        data_dir = './data' if os.path.exists('./data') else '.'
    
    if db_path is None:
        db_path = os.path.join(data_dir, 'photo_library.db')
        if not os.path.exists(db_path):
            db_path = './photo_library.db'
    
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return False
    
    # Find timestamp files
    timestamp_files = glob.glob(os.path.join(data_dir, 'last_update_*.txt'))
    if not timestamp_files:
        logger.info(f"No timestamp files found in {data_dir}")
        return False
    
    logger.info(f"Found {len(timestamp_files)} timestamp files")
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Make sure the last_updated column exists
        cursor.execute("PRAGMA table_info(libraries)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'last_updated' not in columns:
            logger.info("Adding last_updated column to libraries table")
            cursor.execute("ALTER TABLE libraries ADD COLUMN last_updated TEXT")
            conn.commit()
        
        # Process each timestamp file
        updated_count = 0
        for file_path in timestamp_files:
            try:
                # Extract library name from filename
                file_name = os.path.basename(file_path)
                library_name = file_name.replace('last_update_', '').replace('.txt', '')
                
                # Read timestamp from file
                with open(file_path, 'r') as f:
                    timestamp = f.read().strip()
                
                # Update database
                cursor.execute(
                    "UPDATE libraries SET last_updated = ? WHERE name = ?",
                    (timestamp, library_name)
                )
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated timestamp for library '{library_name}': {timestamp}")
                    updated_count += 1
                else:
                    logger.warning(f"Library '{library_name}' not found in database")
            
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Migration complete: {updated_count} libraries updated")
        return True
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate library update timestamps from files to database')
    parser.add_argument('--data-dir', help='Directory containing timestamp files')
    parser.add_argument('--db', help='Database file path')
    
    args = parser.parse_args()
    
    success = migrate_timestamps(args.data_dir, args.db)
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
