# Optimized version for faster performance
import os
import multiprocessing
import logging
import time

logger = logging.getLogger(__name__)

# Define this as a top-level function so it can be pickled for multiprocessing
def _scan_single_directory(args):
    """Scan a single directory for image files - optimized version
    
    Args:
        args: Tuple of (dir_path, image_extensions, existing_paths_list)
        
    Returns:
        Tuple of (files_found, total_files_in_directory)
    """
    dir_path, image_extensions, existing_paths_list = args
    
    # Use a set for faster lookups (only convert once)
    existing_paths_set = set(existing_paths_list)
    files_found = []
    total = 0
    
    # Optimize file checks by collecting all filenames first
    try:
        # Get all filenames first
        all_files = os.listdir(dir_path)
        
        # Filter in memory for better performance
        for filename in all_files:
            # Check extension first (faster than path operations)
            if not filename.lower().endswith(image_extensions):
                continue
                
            # Build full path only for matching files
            full_path = os.path.join(dir_path, filename)
            
            # Skip directories that end with image extensions
            if not os.path.isfile(full_path):
                continue
                
            total += 1
            if full_path not in existing_paths_set:
                files_found.append(full_path)
                
    except (PermissionError, FileNotFoundError, OSError) as e:
        # Handle permission errors or directories that disappeared
        logger.debug(f"Error scanning directory {dir_path}: {e}")
    
    return files_found, total

def scan_directory_parallel(root_dir, image_extensions, existing_paths=None):
    """Scan a directory for image files in parallel using multiprocessing - optimized version"""    
    start_time = time.time()
    if existing_paths is None:
        existing_paths = set()
    
    # Get all directories under the root in a single pass (more efficient)
    all_dirs = []
    dir_count = 0
    
    # For large sets, convert only once for better performance
    existing_paths_list = list(existing_paths) if existing_paths else []
    
    # Pre-scan directories first (faster than walking the whole tree)
    logger.info(f"First pass - collecting directories from {root_dir}")
    for dirpath, dirnames, _ in os.walk(root_dir):
        dir_count += 1
        all_dirs.append((dirpath, image_extensions, existing_paths_list))
        
        # Print progress for large directories
        if dir_count % 100 == 0:
            logger.debug(f"Found {dir_count} directories so far...")
    
    logger.info(f"Found {len(all_dirs)} directories to scan in {time.time() - start_time:.2f} seconds")
    
    # Calculate optimal number of processes and chunk size
    cpu_count = multiprocessing.cpu_count()
    max_processes = min(cpu_count, 16)  # Cap at 16 processes to avoid excessive overhead
    
    # Use more processes for more directories
    if len(all_dirs) > 500:
        processes = max_processes
    elif len(all_dirs) > 100:
        processes = max(4, cpu_count // 2)
    else:
        processes = max(2, cpu_count // 4)
    
    # Calculate chunk size - larger chunks for more directories
    if len(all_dirs) > 1000:
        chunk_size = len(all_dirs) // (processes * 4)
    else:
        chunk_size = max(1, len(all_dirs) // processes)
    
    logger.info(f"Scanning with {processes} processes and chunk size {chunk_size}")
    
    new_files = []
    total_files = 0
    scan_time_start = time.time()
    
    try:
        # Use process pool for scanning
        with multiprocessing.Pool(processes=processes) as pool:
            # Process directories in chunks for better performance
            results = pool.map(_scan_single_directory, all_dirs, chunksize=chunk_size)
            
            # Collect results
            for files, total in results:
                new_files.extend(files)
                total_files += total
    
    except Exception as e:
        logger.error(f"Parallel scanning failed: {e}. Falling back to serial processing.")
        # Fall back to serial scanning if multiprocessing fails
        for args in all_dirs:
            files, count = _scan_single_directory(args)
            new_files.extend(files)
            total_files += count
    
    scan_time = time.time() - scan_time_start
    rate = len(all_dirs) / scan_time if scan_time > 0 else 0
    logger.info(f"Scan completed in {scan_time:.2f} seconds ({rate:.1f} dirs/sec)")
    
    # Additional performance metrics
    if total_files > 0:
        file_rate = total_files / scan_time if scan_time > 0 else 0
        logger.info(f"Processed {total_files} total files ({file_rate:.1f} files/sec)")
    
    if new_files:
        new_rate = len(new_files) / scan_time if scan_time > 0 else 0
        logger.info(f"Found {len(new_files)} new files ({new_rate:.1f} new files/sec)")
    
    return new_files, total_files
