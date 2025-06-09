#!/usr/bin/env python3
import os
import sqlite3
import json
import logging
import sys
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_clusters.log')
    ]
)
logger = logging.getLogger(__name__)

def diagnose_cluster_issue(db_path, fix=False):
    """
    Diagnose issues where multiple markers appear at the same location.
    If fix=True, attempt to fix these issues by merging duplicate records.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        logger.info(f"Checking for cluster issues in {db_path}")
        
        # Find locations with multiple photos (potential clusters)
        cursor.execute("""
            SELECT latitude, longitude, COUNT(*) as photo_count
            FROM photos
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY latitude, longitude
            HAVING COUNT(*) > 1
            ORDER BY photo_count DESC
        """)
        
        clusters = cursor.fetchall()
        logger.info(f"Found {len(clusters)} locations with multiple photos (clusters)")
        
        # Initialize counters
        total_duplicates = 0
        fixed_duplicates = 0
        
        # Examine each cluster
        for cluster in clusters:
            lat = cluster['latitude']
            lng = cluster['longitude']
            count = cluster['photo_count']
            
            logger.info(f"Examining cluster at {lat}, {lng} with {count} photos")
            
            # Get all photos at this location
            cursor.execute("""
                SELECT id, filename, path, library_id, hash
                FROM photos
                WHERE latitude = ? AND longitude = ?
            """, (lat, lng))
            
            photos = cursor.fetchall()
            
            # Check for duplicate filenames or hashes at this location
            filename_map = {}
            hash_map = {}
            duplicates = []
            
            for photo in photos:
                photo_id = photo['id']
                filename = photo['filename']
                photo_hash = photo['hash']
                
                # Check for duplicate filenames
                if filename in filename_map:
                    logger.warning(f"Duplicate filename found: {filename} (IDs: {filename_map[filename]}, {photo_id})")
                    duplicates.append((photo_id, filename_map[filename], f"Duplicate filename: {filename}"))
                else:
                    filename_map[filename] = photo_id
                
                # Check for duplicate hashes (if available)
                if photo_hash and photo_hash in hash_map:
                    logger.warning(f"Duplicate hash found: {photo_hash[:10]}... (IDs: {hash_map[photo_hash]}, {photo_id})")
                    duplicates.append((photo_id, hash_map[photo_hash], f"Duplicate hash: {photo_hash[:10]}..."))
                elif photo_hash:
                    hash_map[photo_hash] = photo_id
            
            # Handle duplicates if found
            if duplicates:
                total_duplicates += len(duplicates)
                logger.warning(f"Found {len(duplicates)} duplicates at location {lat}, {lng}")
                
                if fix:
                    # Fix the duplicates by removing them
                    for dup_id, original_id, reason in duplicates:
                        logger.info(f"Fixing: {reason} - Keeping ID {original_id}, removing ID {dup_id}")
                        
                        cursor.execute("DELETE FROM photos WHERE id = ?", (dup_id,))
                        fixed_duplicates += 1
            else:
                logger.info(f"No duplicates found at this location - these are likely legitimate separate photos")
        
        # Commit changes if we made any
        if fix and fixed_duplicates > 0:
            logger.info(f"Committing changes - removed {fixed_duplicates} duplicate entries")
            conn.commit()
        
        # Show summary
        if total_duplicates > 0:
            logger.warning(f"Summary: Found {total_duplicates} total duplicates across {len(clusters)} clusters")
            if fix:
                logger.info(f"Fixed {fixed_duplicates} duplicates")
            else:
                logger.info(f"Run with --fix to automatically remove duplicates")
        else:
            logger.info("No duplicate entries found in clusters")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error diagnosing cluster issues: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnose and fix issues with photo clusters")
    parser.add_argument('--db', default='data/photo_library.db', help='Database file path')
    parser.add_argument('--fix', action='store_true', help='Fix issues by removing duplicate entries')
    args = parser.parse_args()
    
    diagnose_cluster_issue(args.db, args.fix)
