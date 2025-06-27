# Photo Heatmap Viewer Performance Improvements

This document outlines the performance improvements implemented to enhance the Photo Heatmap Viewer application, particularly for handling HEIC image files.

## Implemented Improvements

### 1. Image Caching System

- **Cache Directory**: Created `data/image_cache/` to store converted image files
- **Intelligent Caching**: Images are cached based on source file, quality, and resolution
- **Cache Invalidation**: Detects changes to source images and regenerates cache when needed
- **Automatic Cleanup**: Background thread periodically removes old/unused cache files

### 2. HEIC Image Optimization

- **Efficient Conversion**: HEIC files are now converted to JPEG with optimized parameters
- **Background Processing**: Added background threads for non-blocking HEIC conversion
- **Preloading Script**: Created `preload_heic.py` to prepare HEIC images in advance
- **Multiple Resolutions**: Images are converted at appropriate sizes for thumbnails and full-screen viewing

### 3. Database Performance

- **Added Indexes**: Created `add_db_indexes.py` to add proper indexes on frequently accessed columns:
  - `photos.filename`
  - `photos.path`
  - `photos.latitude, photos.longitude`
  - `photos.library_id`
  - `photos.datetime`
  - `libraries.name`

### 4. Memory Management

- **Progressive Loading**: Large clusters are loaded in batches to prevent memory issues
- **Memory Cleanup**: Released memory after viewing to improve garbage collection
- **Resource Optimization**: Added memory optimization function in the `optimize_performance` module

### 5. Server Performance

- **Background Processing**: Added a thread pool for handling intensive tasks
- **LRU Caching**: Added caching for image metadata to reduce I/O operations
- **Smarter MIME Types**: Properly configured MIME types for optimal browser handling
- **Optimized Endpoints**: Streamlined image serving routes for better performance

## Usage Instructions

### Regular Server Startup

```bash
python server.py
```

### Preloading HEIC Images (Recommended before first use)

```bash
python preload_heic.py --workers 4
```

This will:
1. Scan the database for HEIC images
2. Pre-convert them to JPEG at different resolutions
3. Store them in the cache for faster access

### Adding Database Indexes (Recommended for large libraries)

```bash
python add_db_indexes.py
```

This will add performance indexes to the database, significantly improving query speed.

### Cache Maintenance

```bash
python cache_cleanup.py --max-age 7 --max-size 500
```

This will remove:
1. Cache files older than 7 days
2. Oldest files if the cache exceeds 500MB

## Configuration Options

The following parameters can be adjusted in the scripts:

- **Cache Size**: Default max size is 500MB (adjustable in `cache_cleanup.py`)
- **Cache Age**: Default maximum age is 7 days (adjustable in `cache_cleanup.py`)
- **Image Quality**: Default is 90 for full images, 80 for thumbnails (adjustable in requests)
- **Max Resolution**: Default is 2048px for full images, 200px for thumbnails

## Technical Details

### HEIC File Handling

HEIC files are handled using the `pillow-heif` library. The conversion process:

1. Opens the HEIC file using PIL with the HEIF opener registered
2. Converts to RGB mode (necessary for JPEG output)
3. Resizes while maintaining aspect ratio (if needed)
4. Saves as JPEG with the specified quality
5. Stores in cache with a filename encoding the source file and parameters

### Caching Strategy

The cache filename encodes:
- Original filename
- File modification time
- File size
- Output format
- Quality setting
- Maximum dimension

This ensures that:
1. Files are regenerated if the source changes
2. Different quality/size requests create separate cache files
3. Cache files can be matched back to their source

## Browser Optimizations

Frontend optimizations include:
- Using the new `/convert` endpoint for HEIC photos
- Displaying loading feedback during conversion
- Providing fallback mechanisms for browser compatibility
- Improved error handling for failed conversions
