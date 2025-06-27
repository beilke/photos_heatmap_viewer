#!/usr/bin/env python
"""
Preload and prepare HEIC images for faster viewing
This script scans the photo database and pre-converts HEIC images to JPEG format
"""

import os
import argparse
import sqlite3
import logging
import time
from PIL import Image
import concurrent.futures
import sys

# Try to import HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('preload_heic.log')
    ]
)
logger = logging.getLogger(__name__)

def normalize_path(path):
    """Normalize path to handle potential drive letter differences"""
    original_path = path
    if sys.platform == 'win32' and len(path) > 1 and path[1] == ':':
        # Get the path without the drive letter
        drive_free_path = path[2:]
        # Check common drive letters
        for drive in ['C:', 'D:', 'E:', 'F:', 'G:', 'H:', 'I:', 'J:', 'K:', 'L:', 'M:', 'N:', 
                      'O:', 'P:', 'Q:', 'R:', 'S:', 'T:', 'U:', 'V:', 'W:', 'X:', 'Y:', 'Z:']:
            test_path = f"{drive}{drive_free_path}"
            if os.path.exists(test_path):
                if test_path != original_path:
                    logger.info(f"Path normalized: {original_path} -> {test_path}")
                return test_path
    return path

def get_cache_path(original_path, format, quality, max_size):
    """Generate a cache path for converted images"""
    # Create a unique hash based on the original file and parameters
    try:
        file_stat = os.stat(original_path)
        mtime = file_stat.st_mtime
        file_size = file_stat.st_size
    except:
        # If file doesn't exist or can't be accessed, use defaults
        mtime = 0
        file_size = 0
    
    import hashlib
    hash_str = f"{original_path}:{mtime}:{file_size}:{format}:{quality}:{max_size}"
    hash_value = hashlib.md5(hash_str.encode()).hexdigest()[:12]
    
    # Create a cache filename based on original file and parameters
    basename = os.path.basename(original_path)
    name_without_ext = os.path.splitext(basename)[0]
    cache_name = f"{name_without_ext}_{hash_value}_{max_size}px_q{quality}.{format}"
    
    return os.path.join(os.path.join('data', 'image_cache'), cache_name)

def resize_image_if_needed(img, max_size):
    """Resize an image if it's larger than max_size while maintaining aspect ratio"""
    if img.width <= max_size and img.height <= max_size:
        return img  # No resize needed
        
    # Calculate new dimensions while maintaining aspect ratio
    if img.width > img.height:
        new_width = max_size
        new_height = int(img.height * (max_size / img.width))
    else:
        new_height = max_size
        new_width = int(img.width * (max_size / img.height))
        
    # Use LANCZOS resampling for better quality
    return img.resize((new_width, new_height), Image.LANCZOS)

def process_heic_file(args):
    """Convert a HEIC file to JPEG and save in cache"""
    photo_path, quality, max_size = args
    
    try:
        if not os.path.exists(photo_path) or not photo_path.lower().endswith('.heic'):
            return False, f"Skipped {photo_path}: Not a HEIC file or doesn't exist"
            
        # Generate cache path
        cache_path = get_cache_path(photo_path, 'jpg', quality, max_size)
        
        # Skip if already cached
        if os.path.exists(cache_path):
            return True, f"Already cached: {os.path.basename(photo_path)}"
            
        # Convert the file
        start_time = time.time()
        with Image.open(photo_path) as img:
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Resize if needed
            img = resize_image_if_needed(img, max_size)
            
            # Create cache directory if it doesn't exist
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            # Save the converted image
            img.save(cache_path, format='JPEG', quality=quality, optimize=True)
            
        elapsed_time = time.time() - start_time
        file_size = os.path.getsize(cache_path) / 1024  # KB
        
        return True, f"Converted {os.path.basename(photo_path)} in {elapsed_time:.2f}s - Size: {file_size:.1f}KB"
        
    except Exception as e:
        return False, f"Error processing {os.path.basename(photo_path)}: {str(e)}"

def preload_heic_files(db_path, num_workers=4, max_files=None, quality=90, max_size=1920):
    """Preload HEIC files from the database"""
    if not HEIC_SUPPORT:
        logger.error("HEIC support not available. Install pillow-heif package.")
        return False
        
    try:
        # Create cache directory
        cache_dir = os.path.join('data', 'image_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Connect to database
        if not os.path.exists(db_path):
            logger.error(f"Database not found at {db_path}")
            return False
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all HEIC files
        cursor.execute("""
            SELECT path FROM photos
            WHERE LOWER(filename) LIKE '%.heic'
            ORDER BY datetime DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            logger.info("No HEIC files found in database")
            return True
            
        # Limit number of files if specified
        if max_files and max_files > 0:
            results = results[:max_files]
        
        heic_files = [normalize_path(row[0]) for row in results]
        logger.info(f"Found {len(heic_files)} HEIC files to process")
        
        # Create parameter tuples for each file
        tasks = [(path, quality, max_size) for path in heic_files]
        
        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(process_heic_file, args) for args in tasks]
            
            success_count = 0
            error_count = 0
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                success, message = future.result()
                
                # Update counters
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    
                # Log progress
                if i % 10 == 0 or i == len(tasks) - 1:
                    logger.info(f"Progress: {i+1}/{len(tasks)} - {message}")
                else:
                    logger.debug(message)
        
        logger.info(f"Preloading complete: {success_count} successful, {error_count} errors")
        return True
        
    except Exception as e:
        logger.exception(f"Error preloading HEIC files: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Preload HEIC images for faster viewing')
    parser.add_argument('--db', default=None, help='Path to the photo library database')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--limit', type=int, default=None, help='Maximum number of files to process')
    parser.add_argument('--quality', type=int, default=90, help='JPEG quality (1-100)')
    parser.add_argument('--max-size', type=int, default=1920, help='Maximum image dimension')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.quality < 1 or args.quality > 100:
        logger.error("Quality must be between 1 and 100")
        sys.exit(1)
        
    if args.max_size < 100:
        logger.error("Max size must be at least 100 pixels")
        sys.exit(1)
    
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
        sys.exit(1)
        
    logger.info(f"Using database at {db_path}")
    logger.info(f"Processing with {args.workers} workers, quality={args.quality}, max_size={args.max_size}")
    
    if args.limit:
        logger.info(f"Limited to processing {args.limit} files")
    
    if not HEIC_SUPPORT:
        logger.error("HEIC support not available. Install pillow-heif package.")
        sys.exit(1)
    
    start_time = time.time()
    if preload_heic_files(db_path, args.workers, args.limit, args.quality, args.max_size):
        elapsed = time.time() - start_time
        logger.info(f"HEIC preloading completed successfully in {elapsed:.1f} seconds")
    else:
        logger.error("HEIC preloading failed")
        sys.exit(1)
