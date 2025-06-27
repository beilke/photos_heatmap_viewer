#!/usr/bin/env python
"""
Cache management script for Photo Heatmap Viewer
This script cleans up old cache files to prevent disk space issues
"""

import os
import argparse
import time
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cache_cleanup.log')
    ]
)
logger = logging.getLogger(__name__)

def clean_cache(cache_dir, max_age_days=7, max_size_mb=500):
    """
    Clean up old cache files:
    - Delete files older than max_age_days
    - If cache still exceeds max_size_mb, delete the oldest files until size is under limit
    """
    if not os.path.exists(cache_dir):
        logger.error(f"Cache directory {cache_dir} does not exist")
        return False
        
    try:
        # Get the current time and the cutoff time for old files
        now = time.time()
        cutoff_time = now - (max_age_days * 24 * 60 * 60)
        
        # List all cache files with their details
        cache_files = []
        total_cache_size = 0
        
        logger.info(f"Scanning cache directory: {cache_dir}")
        for filename in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, filename)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_time = os.path.getmtime(file_path)
                cache_files.append({
                    "path": file_path,
                    "size": file_size,
                    "mtime": file_time
                })
                total_cache_size += file_size
        
        # Convert total size to MB for reporting
        total_cache_size_mb = total_cache_size / (1024 * 1024)
        logger.info(f"Found {len(cache_files)} cache files totaling {total_cache_size_mb:.2f}MB")
        
        # Step 1: Delete files older than the cutoff date
        deleted_files = 0
        deleted_size = 0
        
        for file_info in list(cache_files):
            if file_info["mtime"] < cutoff_time:
                logger.debug(f"Deleting old cache file: {file_info['path']}")
                try:
                    os.remove(file_info["path"])
                    deleted_files += 1
                    deleted_size += file_info["size"]
                    cache_files.remove(file_info)
                except Exception as e:
                    logger.error(f"Error deleting {file_info['path']}: {e}")
                    
        # Recalculate total size after deleting old files
        total_cache_size = sum(f["size"] for f in cache_files)
        total_cache_size_mb = total_cache_size / (1024 * 1024)
        
        logger.info(f"Deleted {deleted_files} old cache files ({deleted_size / (1024 * 1024):.2f}MB)")
        logger.info(f"Remaining cache size: {total_cache_size_mb:.2f}MB")
        
        # Step 2: If we're still over the max size, delete oldest files until we're under the limit
        if total_cache_size_mb > max_size_mb:
            logger.info(f"Cache size ({total_cache_size_mb:.2f}MB) exceeds limit ({max_size_mb}MB), removing oldest files")
            
            # Sort files by modification time (oldest first)
            cache_files.sort(key=lambda x: x["mtime"])
            
            # Delete files until we're under the limit
            size_to_remove = total_cache_size - (max_size_mb * 1024 * 1024)
            removed_size = 0
            removed_count = 0
            
            for file_info in cache_files:
                if removed_size >= size_to_remove:
                    break
                    
                try:
                    os.remove(file_info["path"])
                    removed_size += file_info["size"]
                    removed_count += 1
                    logger.debug(f"Removed cache file to reduce size: {file_info['path']}")
                except Exception as e:
                    logger.error(f"Error removing {file_info['path']}: {e}")
            
            logger.info(f"Removed {removed_count} additional files ({removed_size / (1024 * 1024):.2f}MB) to meet size limit")
            
        # Final cache stats
        remaining_files = len(os.listdir(cache_dir))
        remaining_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f)))
        remaining_size_mb = remaining_size / (1024 * 1024)
        
        logger.info(f"Cache cleanup complete. Remaining: {remaining_files} files, {remaining_size_mb:.2f}MB")
        return True
        
    except Exception as e:
        logger.exception(f"Error during cache cleanup: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean up old image cache files')
    parser.add_argument('--cache-dir', default=os.path.join('data', 'image_cache'), 
                       help='Path to the image cache directory')
    parser.add_argument('--max-age', type=int, default=7,
                       help='Maximum age of cache files in days')
    parser.add_argument('--max-size', type=int, default=500,
                       help='Maximum cache size in MB')
    
    args = parser.parse_args()
    
    # Normalize path
    cache_dir = os.path.abspath(args.cache_dir)
    
    logger.info(f"Starting cache cleanup: max age={args.max_age} days, max size={args.max_size}MB")
    
    if clean_cache(cache_dir, args.max_age, args.max_size):
        logger.info("Cache cleanup completed successfully")
    else:
        logger.error("Cache cleanup failed")
        exit(1)
