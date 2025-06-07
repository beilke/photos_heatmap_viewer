# Fixed version of the main section with correct indentation
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process images and create a photo heatmap database')
    parser.add_argument('--init', action='store_true', help='Initialize the database')
    parser.add_argument('--process', help='Process images from the specified directory')
    parser.add_argument('--export', action='store_true', help='Export database to JSON')
    parser.add_argument('--db', default='photo_library.db', help='Database file path')
    parser.add_argument('--output', default='photo_heatmap_data.json', help='Output JSON file path')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--include-all', action='store_true', help='Include photos without GPS data')
    parser.add_argument('--export-all', action='store_true', help='Export all photos to JSON, not just those with GPS data')
    parser.add_argument('--clean', action='store_true', help='Clean database before processing')
    parser.add_argument('--force', action='store_true', help='Force import even if photo already exists in database')
    parser.add_argument('--incremental', action='store_true', help='Fast incremental processing - only process new files by path comparison')
    parser.add_argument('--no-cache', action='store_true', help='Disable directory content cache for incremental processing')
    parser.add_argument('--no-resume', action='store_true', help='Disable resume capability for interrupted operations')
    parser.add_argument('--no-optimize-sqlite', action='store_true', help='Disable SQLite optimizations (WAL mode, etc.)')
    parser.add_argument('--serial-scan', action='store_true', help='Disable parallel directory scanning, use serial scanning instead')
    parser.add_argument('--library', default='Default', help='Specify the library name for imported photos')
    parser.add_argument('--description', help='Description for the library (when creating a new library)')
    
    args = parser.parse_args()
    
    if args.init:
        from init_db import create_database
        create_database(args.db)
    
    if args.clean:
        clean_database(args.db)
    
    if args.process:
        if args.incremental:
            # Use optimized incremental processing with our added features
            process_directory_incremental(
                root_dir=args.process,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                library_name=args.library,
                use_cache=not args.no_cache,
                resume=not args.no_resume
            )
        else:
            # Use standard processing
            process_directory(
                root_dir=args.process,
                db_path=args.db,
                max_workers=args.workers,
                include_all=args.include_all,
                skip_existing=not args.force,
                library_name=args.library
            )
    
    if args.export:
        export_to_json(args.db, args.output, include_non_geotagged=args.export_all)
