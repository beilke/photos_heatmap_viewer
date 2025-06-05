# Photo Heatmap Viewer

A tool to visualize a large photo library (1000+ photos) on a heatmap based on geolocation data extracted from EXIF metadata, with support for multiple photo libraries.

## Features

- **Multiple Libraries**: Organize photos into named libraries with separate source directories
- **Library Filtering**: Filter the map to show specific libraries
- **SQLite Database**: Efficiently stores metadata for tens of thousands of photos  
- **Parallel Processing**: Multi-threaded photo scanning for faster imports
- **Heatmap Visualization**: Web-based interactive map showing photo density
- **Date Filtering**: Filter photos by date range
- **JSON Export**: Export database to JSON for web visualization
- **Duplicate Detection**: Basic hash-based duplicate detection
- **Incremental Updates**: By default, only adds new photos to the database
- **Clean Database Option**: Start fresh with a clean database when needed
- **Photo Viewing**: Show actual photos on the map when zoomed in close enough
- **Photo Clustering**: Automatically groups nearby photos for better visualization
- **Enhanced Logging**: Debug utilities for troubleshooting
- **Path Normalization**: Support for cross-platform file paths

## Requirements

- Python 3.6 or higher
- Pillow (PIL Fork) for image processing
- SQLite (included with Python)

## Setup

1. Install the required Python packages:

```
pip install pillow
```

2. Initialize the database:

```
python process_photos.py --init
```

3. Create a new library and import photos:

```
# Using the library management script
.\manage_libraries.ps1 create "Vacation 2023" "D:\Photos\Vacation"
```

   Or use the quickstart script (for a single library):

```
# Process only photos with GPS coordinates
.\quickstart.ps1 "path/to/your/photos"
```

4. Run the web server:

```
python server.py
```

5. Open your browser at `http://localhost:8000`

## Library Management

The `manage_libraries.ps1` script provides tools for managing multiple photo libraries:

```
# List all libraries
.\manage_libraries.ps1 list

# Create a new library
.\manage_libraries.ps1 create "Family Photos" "D:\Photos\Family" -description "Family events"

# Import more photos into an existing library
.\manage_libraries.ps1 import "Family Photos" "E:\More Photos\Family2023"

# Rename a library 
.\manage_libraries.ps1 rename "Family Photos" "Family Collection"

# Delete a library and its photos
.\manage_libraries.ps1 delete "Unwanted Library"

# Export all data to JSON
.\manage_libraries.ps1 export
```

# Process all photos, including those without GPS coordinates
.\quickstart.ps1 "path/to/your/photos" all

# Clean the database before processing
.\quickstart.ps1 "path/to/your/photos" clean

# Multiple options
.\quickstart.ps1 "path/to/your/photos" all clean force
```

4. Export the data to JSON:

```
python process_photos.py --export
```

5. Start the web server:

```
python server.py
```

6. Open a web browser and navigate to:

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
- `--export`: Export database to JSON
- `--db PATH`: Database file path (default: photo_library.db)
- `--output PATH`: Output JSON file path (default: photo_heatmap_data.json)
- `--workers N`: Number of worker threads for processing (default: 4)
- `--include-all`: Include photos without GPS data
- `--export-all`: Export all photos to JSON, not just those with GPS data
- `--clean`: Clean database before processing
- `--force`: Force import even if photo already exists in database

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

### Debug Startup Script

Use the debug startup script for automated troubleshooting:

```
.\debug_start.ps1   # PowerShell version
debug_start.bat     # Batch file version
```

This will:
1. Check if the server is already running
2. Inspect your JSON data file for issues
3. Optionally fix issues in the JSON file
4. Start the server in debug mode

### JSON File Inspector

To diagnose issues with your JSON data file:

```
python inspect_json.py                    # Just inspect the file
python inspect_json.py --fix              # Inspect and try to fix issues
python inspect_json.py --create-empty     # Create a valid empty JSON file
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

1. Check if your JSON file has valid data:
   ```
   python inspect_json.py
   ```

2. Verify that your photos have GPS coordinates:
   ```
   python process_photos.py --process "path/to/photos" --include-all
   ```

3. Try using the debug UI to see detailed error messages.

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

- `init_db.py` - Initialize the SQLite database
- `process_photos.py` - Process photos and extract metadata
- `server.py` - Web server for the heatmap viewer
- `index.html` - Web interface for the heatmap
- `manage_libraries.ps1` - Library management script
- `quickstart.ps1` - Quick setup for single-library usage
- `demo_multi_library.ps1` - Demo script showing multiple library setup

## Implementation Details

- Photos are stored with library references in the SQLite database
- Each photo has associated marker data for efficient display
- Photos are automatically clustered for better performance with large datasets
- The web interface efficiently loads only necessary data when zooming/panning
