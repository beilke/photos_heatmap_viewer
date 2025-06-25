import http.server
import socketserver
import os
import argparse
import signal
import sys
import time
import sqlite3
import urllib.parse
from PIL import Image
import io
import logging
import json
import datetime
import mimetypes
from flask import Flask, send_from_directory, render_template, request

# Initialize Flask app
app = Flask(__name__, 
           static_folder=os.path.abspath('.'),
           template_folder=os.path.abspath('.'))

# Add MIME type for HEIC files
mimetypes.add_type('image/heic', '.heic')
mimetypes.add_type('image/heic', '.HEIC')

# Try to import HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False
    
# Helper function for EXIF data
def get_exif_data(img):
    """Get EXIF data from an image, handling different image types"""
    if hasattr(img, 'getexif'):  # Newer versions of PIL or regular image formats
        return img.getexif()
    elif hasattr(img, '_getexif'):  # Older versions of PIL
        return img._getexif()
    else:
        # HEIC and other formats might not have these methods
        return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('server.log')
    ]
)
logger = logging.getLogger(__name__)

# Make server more responsive to shutdown
class QuickResponseTCPServer(socketserver.TCPServer):
    # Reduce timeout for faster shutdown
    timeout = 0.5
    # Allow reuse of the address (faster restarts)
    allow_reuse_address = True

# Health check endpoint for Docker container
@app.route('/health')
def health_check():
    """Health check endpoint for Docker container"""
    return "OK", 200

# Library updates endpoint
@app.route('/library_updates')
def library_updates():
    """API endpoint to get the last update times for all libraries"""
    updates = get_last_update_times()
    logger.debug(f"Library updates endpoint called, returning {len(updates)} updates")
    return {
        "updates": updates
    }

# API endpoint for photo markers
@app.route('/api/markers')
def api_markers():
    """Serve photo markers from the database"""
    logger.info("Serving photo markers from database")
    
    try:        # Connect to database
        db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
        if not os.path.exists(db_path):
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                return {"error": "Database not found"}, 404
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # First get the libraries information with last_updated timestamp
        cursor.execute("SELECT id, name, description, source_dirs, last_updated FROM libraries")
        library_rows = cursor.fetchall()
        libraries = []
        
        for row in library_rows:
            lib = dict(row)
            # Parse source_dirs from JSON string
            try:
                lib['source_dirs'] = json.loads(lib['source_dirs']) if lib['source_dirs'] else []
            except Exception:
                lib['source_dirs'] = []
            libraries.append(lib)
            
        logger.info(f"Found {len(libraries)} libraries")
        
        # Then get photos with location data - include path and ID
        cursor.execute('''
        SELECT p.id, p.filename, p.path, p.latitude, p.longitude, p.datetime, 
               p.marker_data, p.library_id, l.name as library_name
        FROM photos p
        LEFT JOIN libraries l ON p.library_id = l.id
        WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        ''')
        
        rows = cursor.fetchall()
        photos = []
        
        for row in rows:
            photo = dict(row)
            # Parse marker_data from JSON string if available
            if photo['marker_data']:
                try:
                    photo['marker_data'] = json.loads(photo['marker_data'])
                except Exception:
                    photo['marker_data'] = {}
            else:
                photo['marker_data'] = {}
            
            photos.append(photo)
        
        # Return response as JSON
        result = {
            "photos": photos,
            "libraries": libraries
        }
        logger.info(f"Successfully served {len(photos)} photo markers from {len(libraries)} libraries")
        return result
        
    except Exception as e:
        logger.exception(f"Error serving photo markers: {e}")
        return {"error": str(e)}, 500

# Function to get last update times for libraries
def get_last_update_times():
    """Get the last update times for all libraries from the database"""
    updates = {}
    
    try:
        # Connect to database
        db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
        if not os.path.exists(db_path):
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            
        if not os.path.exists(db_path):
            logger.error(f"Database not found: {db_path}")
            return updates
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        cursor = conn.cursor()
        
        # Get the libraries with their last_updated timestamps
        cursor.execute("SELECT name, last_updated FROM libraries")
        rows = cursor.fetchall()
        
        for row in rows:
            if row['last_updated']:  # Only add if there's a timestamp
                updates[row['name']] = row['last_updated']
        
        conn.close()
        logger.debug(f"Found {len(updates)} library update times in database")
        
    except Exception as e:
        logger.error(f"Error getting library update times: {e}")
        
    # Fall back to legacy file-based update times if database didn't provide any
    if not updates:
        updates = get_legacy_update_times()
        
    return updates

def get_legacy_update_times():
    """Get the last update times for all libraries from legacy text files (for backward compatibility)"""
    updates = {}
    data_dir = os.path.join(os.getcwd(), 'data') if os.path.exists(os.path.join(os.getcwd(), 'data')) else os.getcwd()
    
    try:
        update_files = [f for f in os.listdir(data_dir) if f.startswith("last_update_") and f.endswith(".txt")]
        logger.debug(f"Found {len(update_files)} legacy library update files")
        
        for file in update_files:
            library_name = file.replace("last_update_", "").replace(".txt", "")
            try:
                file_path = os.path.join(data_dir, file)
                with open(file_path, "r") as f:
                    content = f.read().strip()
                    updates[library_name] = content
            except Exception as e:
                logger.error(f"Error reading legacy update time for {library_name}: {e}")
    except Exception as e:
        logger.error(f"Error accessing data directory {data_dir}: {e}")
        
    return updates

# Make last update times available to all templates
@app.context_processor
def inject_last_updates():
    return {
        "last_updates": get_last_update_times()
    }

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

# Custom request handler to serve photo thumbnails
class PhotoHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to use our logger instead of printing directly"""
        logger.info("%s - %s" % (self.address_string(), format % args))
    
    def serve_json_with_logging(self):
        """Serve JSON files with additional logging"""
        path = self.path[1:]  # Remove leading '/'
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    
                    # Check if the file uses the new format with photos and libraries
                    if isinstance(json_data, dict) and 'photos' in json_data:
                        photos = json_data.get('photos', [])
                        libraries = json_data.get('libraries', [])
                        logger.info(f"Serving JSON file: {path} with {len(photos)} photos in {len(libraries)} libraries")
                        
                        # Log some data statistics for debugging
                        if photos:
                            has_gps = sum(1 for item in photos if item.get('latitude') and item.get('longitude'))
                            logger.info(f"JSON data stats: {has_gps}/{len(photos)} items have GPS coordinates")
                            
                        # Log libraries
                        if libraries:
                            logger.info(f"Libraries: {', '.join(lib.get('name', 'Unnamed') for lib in libraries)}")
                    else:
                        # Handle old format (just a list of photos)
                        photo_count = len(json_data) if isinstance(json_data, list) else 0
                        logger.info(f"Serving JSON file: {path} with {photo_count} entries (old format)")
                        
                        # Log some data statistics for debugging
                        if photo_count > 0:
                            has_gps = sum(1 for item in json_data if 'latitude' in item and 'longitude' in item)
                            logger.info(f"JSON data stats: {has_gps}/{photo_count} items have GPS coordinates")

                # Send the file
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                with open(path, 'rb') as f:
                    self.wfile.write(f.read())
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in {path}: {e}")
                self.send_error(500, f"JSON parse error: {str(e)}")
            except Exception as e:
                logger.error(f"Error serving JSON {path}: {e}")
                self.send_error(500, f"Internal server error: {str(e)}")
        else:
            self.send_error(404, "File not found")
        
    def do_GET(self):
        # Parse URL path
        path = self.path
        
        # Check if this is a thumbnail request
        if path.startswith('/thumbnails/'):
            logger.info(f"Thumbnail request received: {path}")
            self.serve_thumbnail(path[11:])  # Remove '/thumbnails/' prefix
        # Check if this is a full photo request
        elif path.startswith('/photos/'):
            logger.info(f"Full photo request received: {path}")
            self.serve_original_photo(path[8:])  # Remove '/photos/' prefix        # Add API endpoint for photo markers
        elif path.startswith('/api/markers'):
            logger.info(f"API request received: {path}")
            self.serve_photo_markers()
            return  # Important: return after serving API response
        # Add special handling for JSON data requests        
        elif path.endswith('.json'):
            logger.info(f"JSON request received: {path}")
            self.serve_json_with_logging()
        else:
            # Handle as a normal file request
            logger.debug(f"Regular file request: {path}")
            super().do_GET()
            
    def serve_original_photo(self, filename):
        """Serve the original photo file without any resizing"""
        # URL decode the filename
        filename = urllib.parse.unquote(filename)
        
        logger.info(f"Serving original photo: {filename}")
        
        try:
            # Connect to database
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                self.send_error(404, "Database not found")
                return
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Look up the photo path
            cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.error(f"Photo not found in database: {filename}")
                self.send_error(404, "Photo not found in database")
                return
                
            photo_path = result[0]
            logger.debug(f"Found photo path in DB: {photo_path}")
            
            normalized_path = normalize_path(photo_path)
            
            if not os.path.exists(normalized_path):
                logger.error(f"Photo file not found at {normalized_path}")
                self.send_error(404, f"Photo file not found at {normalized_path}")
                return

            # Check if this is a HEIC file
            is_heic = filename.lower().endswith('.heic')
            
            if is_heic and HEIC_SUPPORT:
                # For HEIC files with support, convert to JPEG on the fly
                try:
                    logger.debug(f"Converting HEIC file to JPEG: {normalized_path}")
                    with Image.open(normalized_path) as img:
                        buffer = io.BytesIO()
                        # Convert to JPEG for browser compatibility
                        img.save(buffer, format='JPEG', quality=95)
                        buffer.seek(0)
                        
                        content = buffer.getvalue()
                        content_length = len(content)
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(content_length))
                        self.end_headers()
                        
                        # Send the converted image
                        self.wfile.write(content)
                        return
                except Exception as e:
                    logger.error(f"Error converting HEIC file: {e}")
                    # Fall back to serving the original file
            
            # For non-HEIC files or if conversion failed, serve the original file
            with open(normalized_path, 'rb') as f:
                fs = os.fstat(f.fileno())
                content_length = fs[6]

                self.send_response(200)
                
                # Determine content type based on file extension
                content_type = mimetypes.guess_type(normalized_path)[0] or 'application/octet-stream'
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(content_length))
                self.end_headers()
                
                # Send the file in chunks to handle large files
                chunk_size = 8192
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except ConnectionAbortedError:
                        logger.warning(f"Client aborted connection while downloading {filename}")
                        break

                logger.debug(f"Successfully served original photo: {filename}")
                
        except Exception as e:
            logger.exception(f"Error serving original photo: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")

    def serve_thumbnail(self, filename):
        """Serve a thumbnail version of the photo"""
        # URL decode the filename
        filename = urllib.parse.unquote(filename)
        
        logger.info(f"Serving thumbnail: {filename}")
        
        try:
            # Connect to database
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                self.send_error(404, "Database not found")
                return
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Look up the photo path
            cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.error(f"Photo not found in database: {filename}")
                self.send_error(404, "Photo not found in database")
                return
                
            photo_path = result[0]
            logger.debug(f"Found photo path in DB: {photo_path}")
            
            normalized_path = normalize_path(photo_path)
            
            if not os.path.exists(normalized_path):
                logger.error(f"Photo file not found at {normalized_path}")
                self.send_error(404, f"Photo file not found at {normalized_path}")
                return            # Generate thumbnail
            logger.debug(f"Generating thumbnail for: {normalized_path}")
            try:
                with Image.open(normalized_path) as img:
                    # Resize to a thumbnail
                    img.thumbnail((200, 200))
                    
                    # Prepare to send the image
                    buffer = io.BytesIO()
                    
                    # For HEIC files, always convert to JPEG for better browser compatibility
                    if filename.lower().endswith('.heic'):
                        img_format = 'JPEG'
                    else:
                        img_format = img.format if img.format else 'JPEG'
                    
                    # Save with appropriate format and quality
                    if img_format == 'JPEG':
                        img.save(buffer, format=img_format, quality=85)
                    else:
                        img.save(buffer, format=img_format)
                        
                    buffer.seek(0)
                    
                    # Send headers
            except Exception as e:
                logger.error(f"Error generating thumbnail for {filename}: {e}")
                self.send_error(500, f"Error generating thumbnail: {str(e)}")
                return
                self.send_response(200)
                self.send_header('Content-type', f'image/{img_format.lower()}')
                self.send_header('Content-Length', str(buffer.getbuffer().nbytes))
                self.end_headers()
                
                # Send thumbnail data                
                self.wfile.write(buffer.getvalue())
                logger.debug(f"Successfully served thumbnail for: {filename}")
        except Exception as e:
            logger.exception(f"Error serving thumbnail: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")
            
    def serve_photo_markers(self):
        """Serve photo markers from the database"""
        logger.info("Serving photo markers from database")
        
        try:
            # Connect to database
            db_path = os.path.join(os.getcwd(), 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                self.send_error(404, "Database not found")
                return
                
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            cursor = conn.cursor()
            
            # First get the libraries information
            cursor.execute("SELECT id, name, description, source_dirs FROM libraries")
            library_rows = cursor.fetchall()
            libraries = []
            
            for row in library_rows:
                lib = dict(row)
                # Parse source_dirs from JSON string
                try:
                    lib['source_dirs'] = json.loads(lib['source_dirs']) if lib['source_dirs'] else []
                except Exception:
                    lib['source_dirs'] = []
                libraries.append(lib)
                
            logger.info(f"Found {len(libraries)} libraries")
            
            # Then get photos with location data - include path
            cursor.execute('''
            SELECT p.filename, p.path, p.latitude, p.longitude, p.datetime, 
                   p.marker_data, p.library_id, l.name as library_name
            FROM photos p
            LEFT JOIN libraries l ON p.library_id = l.id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
            ''')
            
            rows = cursor.fetchall()
            photos = []
            
            for row in rows:
                photo = dict(row)
                # Parse marker_data from JSON string if available
                if photo['marker_data']:
                    try:
                        photo['marker_data'] = json.loads(photo['marker_data'])
                    except Exception:
                        photo['marker_data'] = {}
                else:
                    photo['marker_data'] = {}
                
                photos.append(photo)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
              # Create final data structure with photos AND libraries
            result = json.dumps({
                "photos": photos,
                "libraries": libraries
            }, ensure_ascii=False)
            self.wfile.write(result.encode('utf-8'))
            
            logger.info(f"Successfully served {len(photos)} photo markers from {len(libraries)} libraries")
            conn.close()
            
        except Exception as e:
            logger.exception(f"Error serving photo markers: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")

def signal_handler(sig, frame):
    logger.info("Gracefully shutting down server...")
    sys.exit(0)

def start_server(port=8000, directory='.', debug_mode=False, db_path=None, host="0.0.0.0"):
    """Start a Flask server to serve the photo heatmap viewer"""
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set log level based on debug mode
    if debug_mode:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled - verbose logging activated")
    
    # Log HEIC support status
    if HEIC_SUPPORT:
        logger.info("HEIC file support is enabled")
    else:
        logger.warning("HEIC file support is not available. Install pillow-heif package for HEIC support.")
    
    # Change to the specified directory
    os.chdir(directory)
    
    # Log server startup
    logger.info(f"Starting server in directory: {os.path.abspath(directory)}")
    
    # Check for JSON data file
    json_file = 'photo_heatmap_data.json'
    if os.path.exists(json_file):
        try:
            file_size = os.path.getsize(json_file)
            logger.info(f"Found {json_file} with size: {file_size} bytes")
            
            if file_size == 0:
                logger.error(f"JSON file {json_file} is empty (0 bytes)")
            else:
                with open(json_file, 'r', encoding='utf-8') as f:
                    file_start = f.read(100)  # Read first 100 chars for logging
                    logger.info(f"JSON file starts with: {file_start}...")
                    
                    # Reset file pointer and parse
                    f.seek(0)
                    data = json.load(f)
                    photo_count = len(data) if isinstance(data, list) else 0
                    logger.info(f"Found {json_file} with {photo_count} entries")
                    
                    # In debug mode, analyze JSON data content
                    if debug_mode and isinstance(data, list) and len(data) > 0:
                        gps_count = sum(1 for item in data if 'latitude' in item and 'longitude' in item 
                                    and item['latitude'] is not None and item['longitude'] is not None)
                        logger.info(f"Items with GPS coordinates: {gps_count}/{photo_count} ({gps_count/photo_count*100:.1f}%)")
                        
                        # Log sample data for first entry
                        if len(data) > 0:
                            sample = data[0]
                            logger.info(f"Sample entry: {json.dumps(sample, indent=2)}")
                    
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {json_file}: {e}")
            
            # In debug mode, try to identify where the JSON is malformed
            if debug_mode:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        logger.debug(f"JSON content (first 500 chars): {content[:500]}")
                except Exception as inner_e:
                    logger.error(f"Error reading JSON content: {inner_e}")
                    
        except Exception as e:
            logger.error(f"Error checking {json_file}: {e}")
    else:
        logger.warning(f"{json_file} not found in {os.path.abspath(directory)}")
    
    # Define Flask routes for serving static files
    @app.route('/')
    def serve_index():
        return send_from_directory(os.path.abspath(directory), 'index.html')
    
    # Endpoint for serving original photos
    @app.route('/photos/<path:filename>')
    def serve_original_photo(filename):
        """Serve the original photo file"""
        filename = urllib.parse.unquote(filename)
        logger.info(f"Serving original photo: {filename}")
        
        # Check for additional query parameters (id or path)
        photo_id = request.args.get('id')
        path_hint = request.args.get('path')
        
        try:
            # Connect to database
            db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                return "Database not found", 404
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Try different lookup strategies in order of specificity
            if photo_id is not None:
                logger.debug(f"Looking up photo by ID: {photo_id}")
                cursor.execute("SELECT path FROM photos WHERE id = ?", (photo_id,))
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Found photo by ID: {photo_id}")
            else:
                result = None
                
            # If ID lookup failed or wasn't provided, try path hint if available
            if not result and path_hint:
                logger.debug(f"Looking up photo by path hint: {path_hint}")
                cursor.execute("SELECT path FROM photos WHERE path = ?", (path_hint,))
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Found photo by path hint: {path_hint}")
            
            # If both ID and path lookup failed or weren't provided, fall back to filename
            if not result:
                logger.debug(f"Looking up photo by filename: {filename}")
                cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
                result = cursor.fetchone()
                
            conn.close()
            
            if not result:
                logger.error(f"Photo not found in database: {filename}")
                return "Photo not found in database", 404
                
            photo_path = result[0]
            logger.debug(f"Found photo path in DB: {photo_path}")
            
            normalized_path = normalize_path(photo_path)
            
            if not os.path.exists(normalized_path):
                logger.error(f"Photo file not found at {normalized_path}")
                return f"Photo file not found at {normalized_path}", 404
            
            # Get the file's mimetype
            mimetype, _ = mimetypes.guess_type(normalized_path)
            
            # Return the file
            return send_from_directory(os.path.dirname(normalized_path), os.path.basename(normalized_path), mimetype=mimetype)
            
        except Exception as e:
            logger.exception(f"Error serving original photo: {e}")
            return f"Internal server error: {str(e)}", 500
    
    # Endpoint for serving thumbnails
    @app.route('/thumbnails/<path:filename>')
    def serve_thumbnail(filename):
        """Serve a thumbnail version of the photo"""
        filename = urllib.parse.unquote(filename)
        logger.info(f"Serving thumbnail: {filename}")
        
        # Check for additional query parameters (id or path)
        photo_id = request.args.get('id')
        path_hint = request.args.get('path')
        
        try:
            # Connect to database
            db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
            if not os.path.exists(db_path):
                logger.error(f"Database not found: {db_path}")
                return "Database not found", 404
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Try different lookup strategies in order of specificity
            if photo_id is not None:
                logger.debug(f"Looking up photo by ID: {photo_id}")
                cursor.execute("SELECT path FROM photos WHERE id = ?", (photo_id,))
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Found photo by ID: {photo_id}")
            else:
                result = None
                
            # If ID lookup failed or wasn't provided, try path hint if available
            if not result and path_hint:
                logger.debug(f"Looking up photo by path hint: {path_hint}")
                cursor.execute("SELECT path FROM photos WHERE path = ?", (path_hint,))
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Found photo by path hint: {path_hint}")
            
            # If both ID and path lookup failed or weren't provided, fall back to filename
            if not result:
                logger.debug(f"Looking up photo by filename: {filename}")
                cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
                result = cursor.fetchone()
                
            conn.close()
            
            if not result:
                logger.error(f"Photo not found in database: {filename}")
                return "Photo not found in database", 404
                
            photo_path = result[0]
            logger.debug(f"Found photo path in DB: {photo_path}")
            
            normalized_path = normalize_path(photo_path)
            
            if not os.path.exists(normalized_path):
                logger.error(f"Photo file not found at {normalized_path}")
                return f"Photo file not found at {normalized_path}", 404
                
            # Generate thumbnail
            logger.debug(f"Generating thumbnail for: {normalized_path}")
            try:
                with Image.open(normalized_path) as img:
                    # Resize to a thumbnail
                    img.thumbnail((200, 200))
                    
                    # Prepare to send the image
                    buffer = io.BytesIO()
                    
                    # For HEIC files, always convert to JPEG for better browser compatibility
                    if filename.lower().endswith('.heic'):
                        img_format = 'JPEG'
                    else:
                        img_format = img.format if img.format else 'JPEG'
                    
                    # Save with appropriate format and quality
                    if img_format == 'JPEG':
                        img.save(buffer, format=img_format, quality=85)
                    else:
                        img.save(buffer, format=img_format)
                        
                    buffer.seek(0)
                    
                    return buffer.getvalue(), 200, {'Content-Type': f'image/{img_format.lower()}'}
            except Exception as e:
                logger.error(f"Error generating thumbnail for {filename}: {e}")
                return f"Error generating thumbnail: {str(e)}", 500
                
        except Exception as e:
            logger.exception(f"Error serving thumbnail: {e}")
            return f"Internal server error: {str(e)}", 500
    
    @app.route('/<path:path>')
    def serve_static(path):
        return send_from_directory(os.path.abspath(directory), path)
    
    # Start the Flask application
    logger.info(f"Starting Flask server at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug_mode)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start a web server for the Photo Heatmap Viewer')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--dir', default='.', help='Directory to serve files from')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--db', default=None, help='Path to the photo library database')
    parser.add_argument('--host', default='0.0.0.0', help='Host address to bind the server to')
    
    args = parser.parse_args()
    
    # Set log level based on debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
    
    start_server(port=args.port, directory=args.dir, debug_mode=args.debug, db_path=args.db, host=args.host)