# Photo Heatmap Viewer

A tool to visualize a large photo library (1000+ photos) on a heatmap based on geolocation data extracted from EXIF metadata, with support for multiple photo libraries.

## Features

- **Multiple Libraries**: Organize photos into named libraries with separate source directories
- **Library Filtering**: Filter the map to show specific libraries
- **SQLite Database**: Efficiently stores and serves metadata for tens of thousands of photos  
- **Parallel Processing**: Multi-threaded photo scanning for faster imports
- **Heatmap Visualization**: Web-based interactive map showing photo density
- **Date Filtering**: Filter photos by date range
- **HEIC Support**: View HEIC images with on-the-fly conversion
- **Duplicate Detection**: Basic hash-based duplicate detection
- **Incremental Updates**: By default, only adds new photos to the database
- **Clean Database Option**: Start fresh with a clean database when needed
- **Photo Viewing**: Show actual photos on the map when zoomed in close enough
- **Photo Clustering**: Automatically groups nearby photos for better visualization
- **Intelligent Deduplication**: Prevents duplicate photos at the same location while allowing same-named photos from different locations to appear on the map
- **Enhanced Logging**: Debug utilities for troubleshooting
- **Cross Platform**: Support for Windows, Linux and Docker environments

## Requirements

- Python 3.6 or higher
- Pillow (PIL Fork) for image processing
- SQLite (included with Python)

## Setup

1. Install the required Python packages:

```
pip install -r requirements.txt
```

2. Initialize the database:

```
python process_photos.py --init
```

3. Process your photos to add them to the database:

```
python process_photos.py --process "path/to/your/photos"
```

4. Run the web server:

```
python server.py
# or use PowerShell script
.\start_server.ps1
```

5. Open your browser at `http://localhost:8000`

## Library Management

Libraries can be managed directly through process_photos.py:

```
# Create a new library and process photos
python process_photos.py --create-library "Vacation 2023" --description "Summer vacation photos" --process "D:\Photos\Vacation"

# Add more photos to existing library
python process_photos.py --library "Vacation 2023" --process "E:\More Photos\Vacation2023"

# Process with advanced options
python process_photos.py --process "path/to/your/photos" --include-all --clean --force
```

## Starting the Server

```
# Basic server startup
python server.py

# Using PowerShell script (recommended)
.\start_server.ps1

# With debug mode enabled
python server.py --debug
.\start_server.ps1 -debug

# With custom port
python server.py --port 8080
.\start_server.ps1 -port 8080

# With custom host address
python server.py --host 127.0.0.1
.\start_server.ps1 -hostAddress 127.0.0.1
```

Once the server is running, open a web browser and navigate to:

```
http://localhost:8000
```

## Command Line Options

### Photo Processing

```
python process_photos.py --help
```

Options:
- `--init`: Initialize the database
- `--process PATH`: Process images from the specified directory
- `--db PATH`: Database file path (default: photo_library.db)
- `--workers N`: Number of worker threads for processing (default: 4)
- `--include-all`: Include photos without GPS data when processing
- `--clean`: Clean database before processing
- `--force`: Force import even if photo already exists in database
- `--export`: [LEGACY] Export database to JSON (no longer needed)
- `--output PATH`: [LEGACY] Output JSON file path (no longer needed)
- `--export-all`: [LEGACY] Export all photos to JSON (no longer needed)

### Web Server

```
python server.py --help
```

Options:
- `--port PORT`: Port to run the server on (default: 8000)
- `--dir PATH`: Directory to serve files from (default: current directory)

## Web Interface Controls

- **Heat Intensity**: Adjust the intensity of the heatmap
- **Heat Radius**: Adjust the radius of each data point
- **Date Range**: Filter photos by date
- **Apply/Reset**: Apply or reset filters
- **Show Photos on Zoom**: Toggle to show actual photo thumbnails when zoomed in
- **Photo Clusters**: Groups of photos are automatically clustered with a number indicating how many photos are at that location

## For Large Photo Collections

- Increase the number of worker threads (`--workers`) based on your CPU cores
- Process in batches if memory becomes an issue
- Consider running on an SSD for faster database operations

## Debugging and Troubleshooting

If you encounter any issues with the heatmap viewer, there are several debugging utilities available:

### Debug Mode Server

Start the server with debug mode enabled for more detailed logging:

```
python server.py --debug
```

This will generate logs in both the console and a `server.log` file.

### Using Debug Mode

Start the server with debug mode enabled for more detailed logging:

```
# Using server.py directly with debug flag
python server.py --debug

# Using PowerShell script with debug parameter
.\start_server.ps1 -debug
```

This will generate logs in both the console and the logs/server.log file.

### Database Diagnostics

To diagnose issues with your photo database, you can use the tools in the tools directory:

```
python tools/check_db.py                  # Basic database validation
python tools/check_sql.py                 # Verify SQL queries are working correctly
```

### Debug UI

The enhanced debug version of the UI includes a browser-based debug console. 
To use it:

1. Open the regular interface (http://localhost:8000)
2. Click the "Debug" button in the bottom right corner
3. A debug console will appear showing detailed logging information

Alternatively, you can directly open the debug version:

```
http://localhost:8000/index.html.debug
```

## Troubleshooting Common Issues

### No Photos Displaying on Map

1. Check if your database has valid data:
   ```
   python tools/check_db.py
   ```

2. Verify that your photos have GPS coordinates:
   ```
   python process_photos.py --process "path/to/photos" --include-all
   ```

3. Try using the debug UI to see detailed error messages.

### Diagnostic Tools

The project includes several diagnostic scripts in the `tools` directory to help troubleshoot database and photo issues:

- **check_cluster.py**: Examines photos within specific geographic clusters to identify duplicates
- **check_db.py**: Performs basic database validation and checks for duplicate filenames
- **check_duplicates.py**: Finds duplicate photos in the database by filename and path
- **check_near_duplicates.py**: Identifies photos with same filename but slightly different coordinates
- **check_photo.py**: Examines details of a specific photo by ID
- **check_specific_photos.py**: Tests deduplication for specific photos across libraries
- **check_sql.py**: Validates SQL deduplication queries are working correctly

Example usage:
```
python tools/check_db.py                         # Check database health
python tools/check_duplicates.py                 # Find duplicates in database
python tools/check_cluster.py 40.7128 -74.0060   # Check photos near specific coordinates
python tools/check_photo.py 12345                # Get details about photo with ID 12345
```

For more information about the diagnostic tools, see the [tools/README.md](tools/README.md) file.

### Server Won't Start

1. Check if another process is using port 8000:
   ```
   netstat -ano | findstr :8000
   ```

2. Try specifying a different port:
   ```
   python server.py --port 8080
   ```

### Missing Thumbnails

1. Make sure the database file exists and has records
2. Check file paths in the database match your actual file system
3. If using Windows, drive letter normalization should handle path differences
## Project Structure

- `process_photos.py` - Process photos and extract metadata
- `server.py` - Web server for the heatmap viewer
- `start_server.ps1` - PowerShell script to start the server
- `index.html` - Web interface for the heatmap
- `static/` - CSS and JavaScript files for the web interface
- `tools/` - Diagnostic and troubleshooting utilities
- `data/` - Database and image cache storage
- `logs/` - Server log files

## Implementation Details

- Photos are stored with library references in the SQLite database
- Each photo has associated marker data for efficient display
- Photos are automatically clustered for better performance with large datasets
- The web interface efficiently loads only necessary data when zooming/panning
