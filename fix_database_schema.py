#!/usr/bin/env python3
import os
import sqlite3
import argparse
import logging
import json
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_and_update_database(db_path):
    """Check if the database has the last_updated column and add it if missing"""
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
    
    conn = None
    try:
        logger.info(f"Opening database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if last_updated column exists in libraries table
        cursor.execute("PRAGMA table_info(libraries)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        logger.info(f"Current columns in libraries table: {column_names}")
        
        if 'last_updated' not in column_names:
            logger.info("Adding 'last_updated' column to libraries table")
            cursor.execute("ALTER TABLE libraries ADD COLUMN last_updated TEXT")
            
            # Set last_updated for all libraries to current timestamp
            current_time = datetime.datetime.now().isoformat()
            cursor.execute("UPDATE libraries SET last_updated = ?", (current_time,))
            logger.info(f"Set last_updated to {current_time} for all libraries")
            
            conn.commit()
            logger.info("Database schema updated successfully")
        else:
            logger.info("last_updated column already exists in libraries table")
        
        # Check for existing timestamp files in data directory
        data_dir = os.path.dirname(db_path)
        if not data_dir:
            data_dir = '.'
            
        logger.info(f"Checking for timestamp files in {data_dir}")
        timestamp_files = [f for f in os.listdir(data_dir) if f.startswith('last_update_') and f.endswith('.txt')]
        
        if timestamp_files:
            logger.info(f"Found {len(timestamp_files)} timestamp files")
            
            # Get all libraries
            cursor.execute("SELECT id, name FROM libraries")
            libraries = cursor.fetchall()
            library_map = {name: id for id, name in libraries}
            
            # Import timestamps from files
            for file in timestamp_files:
                library_name = file.replace('last_update_', '').replace('.txt', '')
                file_path = os.path.join(data_dir, file)
                
                try:
                    with open(file_path, 'r') as f:
                        timestamp = f.read().strip()
                    
                    logger.info(f"Read timestamp {timestamp} for library {library_name}")
                    
                    if library_name in library_map:
                        cursor.execute(
                            "UPDATE libraries SET last_updated = ? WHERE id = ?", 
                            (timestamp, library_map[library_name])
                        )
                        logger.info(f"Updated timestamp for library '{library_name}'")
                except Exception as e:
                    logger.error(f"Error reading timestamp file {file}: {e}")
            
            conn.commit()
            logger.info("Timestamps imported from files")
        else:
            logger.warning("No timestamp files found")
            
        # Show libraries with last_updated values
        cursor.execute("SELECT id, name, last_updated FROM libraries")
        libraries = cursor.fetchall()
        
        logger.info("\nLibraries with timestamps:")
        for lib_id, name, timestamp in libraries:
            logger.info(f"  ID: {lib_id}, Name: {name}, Last Updated: {timestamp or 'NULL'}")
        
        # Create sample timestamp files if needed
        if not timestamp_files:
            logger.info("Creating sample timestamp files for libraries")
            current_time = datetime.datetime.now().isoformat()
            
            for lib_id, name, _ in libraries:
                if name:
                    file_path = os.path.join(data_dir, f"last_update_{name}.txt")
                    try:
                        with open(file_path, 'w') as f:
                            f.write(current_time)
                        logger.info(f"Created timestamp file for library '{name}'")
                        
                        # Update database with this timestamp
                        cursor.execute(
                            "UPDATE libraries SET last_updated = ? WHERE id = ?", 
                            (current_time, lib_id)
                        )
                    except Exception as e:
                        logger.error(f"Error creating timestamp file for {name}: {e}")
            
            conn.commit()
        
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and update photo database schema")
    parser.add_argument('--db', default='data/photo_library.db', help='Database file path')
    args = parser.parse_args()
    
    # Ensure the data directory exists
    db_dir = os.path.dirname(args.db)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created directory: {db_dir}")
        
    success = check_and_update_database(args.db)
    
    if success:
        print("Database schema check and update completed successfully")
    else:
        print("Failed to update database schema")
