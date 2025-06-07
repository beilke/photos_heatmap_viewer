try:
    from scan_functions import scan_directory_parallel, _scan_single_directory
    HAS_PARALLEL_SCAN = True
except ImportError:
    HAS_PARALLEL_SCAN = False
    print("WARNING: scan_functions.py module not found, parallel scan functionality disabled")

def process_directory_incremental(root_dir, db_path='photo_library.db', max_workers=4, include_all=False, 
                          library_name="Default", use_cache=True, resume=True, use_parallel_scan=True):
    """Fast incremental processing with optimizations:
    - Uses multiprocessing for parallel directory scanning
    - Optional directory cache for avoiding redundant scans
    - SQLite optimizations (WAL mode, memory settings)
    - Resume capability for interrupted operations
    - Directory change detection to skip unchanged directories
    """
    start_time = time.time()
    
    # Validate the directory
    if not os.path.isdir(root_dir):
        logger.error(f"Error: {root_dir} is not a directory")
        return
    
    logger.info(f"Starting optimized incremental scan of {root_dir}")
    
    # Prepare cache and checkpoint files
    workspace_dir = os.path.join(os.path.dirname(db_path), '.workspace')
    os.makedirs(workspace_dir, exist_ok=True)
    
    cache_path = os.path.join(workspace_dir, 'directory_cache.pkl')
    checkpoint_path = os.path.join(workspace_dir, 'process_checkpoint.pkl')
    
    # Connect to database with optimizations
    conn = sqlite3.connect(db_path)
    
    # Apply SQLite optimizations
    optimization_settings = optimize_sqlite_connection(conn)
    logger.info(f"SQLite optimization settings: {optimization_settings}")
    
    cursor = conn.cursor()
    
    # Get or create the library
    library_id = get_or_create_library(cursor, library_name, [root_dir])
    conn.commit()
    
    logger.info(f"Using library: {library_name} (ID: {library_id})")
    
    # Define image extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.heic', '.tiff', '.bmp', '.nef', '.cr2', '.arw', '.dng')
    
    # Load checkpoint if resume is enabled
    checkpoint = None
    processed_files = set()
    if resume:
        checkpoint = load_checkpoint(checkpoint_path)
        if checkpoint:
            processed_files = set(checkpoint['processed_files'])
            logger.info(f"Resuming from checkpoint with {len(processed_files)} already processed files")
    
    # Create index of paths that already exist in the database
    logger.info("Building database path index for incremental comparison...")
    cursor.execute("SELECT path FROM photos")
    existing_paths = {row[0] for row in cursor.fetchall()}
    logger.info(f"Found {len(existing_paths)} files already in database")
    
    # Check if we have a directory cache from previous runs
    dir_cache = {}
    if use_cache:
        dir_cache = get_directory_cache(cache_path)
        logger.info(f"Loaded cache with {len(dir_cache)} directory entries")
    
    # Process directories with directory-level change detection
    new_files = []
    total_files = 0
    unchanged_dirs = 0
    
    # If we have a cache, we can use directory-level change detection
    if use_cache and dir_cache:
        logger.info("Using directory-level change detection...")
        all_dirs = []
        for dirpath, _, _ in os.walk(root_dir):
            all_dirs.append(dirpath)
        
        changed_dirs = []
        for dir_path in all_dirs:
            # Create a hash of the directory contents
            dir_hash = create_directory_hash(dir_path)
            
            # If the directory hasn't changed since last time, skip it
            if dir_path in dir_cache and dir_cache[dir_path] == dir_hash:
                unchanged_dirs += 1
                continue
                
            # Directory has changed or is new, mark for processing
            changed_dirs.append(dir_path)
            dir_cache[dir_path] = dir_hash
        
        logger.info(f"Skipping {unchanged_dirs} unchanged directories. Processing {len(changed_dirs)} changed directories.")
        
        # Only scan the changed directories
        for dir_path in changed_dirs:
            for filename in os.listdir(dir_path):
                if filename.lower().endswith(image_extensions):
                    full_path = os.path.join(dir_path, filename)
                    if os.path.isfile(full_path):
                        total_files += 1
                        if full_path not in existing_paths and full_path not in processed_files:
                            new_files.append(full_path)
    else:
        # Without cache or directory change detection, decide on scanning method
        if use_parallel_scan and HAS_PARALLEL_SCAN:
            logger.info("Using parallel directory scanning...")
            new_files, total_files = scan_directory_parallel(
                root_dir, image_extensions, existing_paths.union(processed_files)
            )
        else:
            logger.info("Using serial directory scanning...")
            # Traditional serial scanning method
            total_files = 0
            new_files = []
            for dirpath, _, filenames in os.walk(root_dir):
                rel_path = os.path.relpath(dirpath, root_dir)
                if rel_path != '.' and total_files % 1000 == 0:
                    logger.info(f"Scanning: {rel_path}")
                
                for filename in filenames:
                    if filename.lower().endswith(image_extensions):
                        total_files += 1
                        full_path = os.path.join(dirpath, filename)
                        
                        # Skip if file already exists in database (by path)
                        if full_path not in existing_paths and full_path not in processed_files:
                            new_files.append(full_path)
    
    # Save the updated directory cache
    if use_cache:
        save_directory_cache(cache_path, dir_cache)
    
    logger.info(f"Found {total_files} total files")
    logger.info(f"Found {len(new_files)} new files to process")
    
    if not new_files:
        logger.info("No new files to process. Exiting.")
        conn.close()
        end_time = time.time()
        logger.info(f"Incremental scan completed in {end_time - start_time:.2f} seconds")
        return
