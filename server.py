import http.server
import socketserver
import os
import argparse
import signal
import sys
import traceback
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
        logging.FileHandler('logs/server.log')
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
        # Use ROW_NUMBER to ensure we only get one instance of each filename per unique location
        # This prevents duplicates from the same location while allowing same-named photos
        # from different locations to appear on the map
        cursor.execute('''
        WITH RankedPhotos AS (
            SELECT 
                p.id, p.filename, p.path, p.latitude, p.longitude, p.datetime, 
                p.marker_data, p.library_id, l.name as library_name,
                ROW_NUMBER() OVER(PARTITION BY p.filename, ROUND(p.latitude, 4), ROUND(p.longitude, 4) ORDER BY p.id) as rn
            FROM photos p
            LEFT JOIN libraries l ON p.library_id = l.id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        )
        SELECT 
            id, filename, path, latitude, longitude, datetime, 
            marker_data, library_id, library_name
        FROM RankedPhotos
        WHERE rn = 1
        ''')
        
        rows = cursor.fetchall()
        photos = []
        
        # Also count how many photos there would be without deduplication
        cursor.execute('''
        SELECT COUNT(*) as total FROM photos p
        WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        ''')
        total_before = cursor.fetchone()[0]
        
        logger.info(f"Filtered out duplicate photos with same filename regardless of coordinates, returning {len(rows)} unique photos (removed {total_before - len(rows)} duplicates)")
        
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
        """
        Legacy method for serving JSON files - now redirects to database API endpoints
        """
        path = self.path
        
        # Check if this is a request for the main data file
        if path == "/photo_heatmap_data.json":
            # Redirect to the database API endpoint
            self.send_response(302)  # Found/Redirect
            self.send_header('Location', '/api/photos')
            self.end_headers()
            logger.info(f"Redirected JSON file request '{path}' to database API endpoint")
            return
            
        # If the file exists on disk, serve it with a deprecation warning
        file_path = path[1:]  # Remove leading '/'
        if os.path.exists(file_path) and file_path.endswith('.json'):
            logger.warning(f"Serving legacy JSON file: {file_path} (deprecated)")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Deprecated', 'This JSON file is deprecated. Use database API endpoints instead.')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            logger.warning(f"JSON file not found: {file_path} - would redirect to API in production")
            self.send_error(404, "File not found")
        
    def do_GET(self):
        # Parse URL path
        path = self.path
        
        if path.startswith('/photos/'):
            logger.info(f"Full photo request received: {path}")
            logger.info(f"Using modern Flask endpoint for photos - redirecting to /photos/{path[8:]}")
            # Redirect to the Flask route for photos
            self.send_response(302)
            self.send_header('Location', f'/photos/{path[8:]}')
            self.end_headers()
            return
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
            
    # Legacy serve_original_photo method has been removed

    # Thumbnail serving method has been removed
            
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
            # Use ROW_NUMBER to ensure we only get one instance of each unique photo per location
            # This allows photos with same filename but different coordinates to appear separately
            # while still preventing true duplicates
            cursor.execute('''
            WITH RankedPhotos AS (
                SELECT 
                    p.filename, p.path, p.latitude, p.longitude, p.datetime, 
                    p.marker_data, p.library_id, l.name as library_name,
                    ROW_NUMBER() OVER(PARTITION BY p.filename, ROUND(p.latitude, 4), ROUND(p.longitude, 4) ORDER BY p.id) as rn
                FROM photos p
                LEFT JOIN libraries l ON p.library_id = l.id
                WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
            )
            SELECT 
                filename, path, latitude, longitude, datetime, 
                marker_data, library_id, library_name
            FROM RankedPhotos
            WHERE rn = 1
            ''')
            
            rows = cursor.fetchall()
            photos = []
            
            logger.info(f"Legacy API: Filtered out duplicate photos with same filename at same coordinates, returning {len(rows)} unique photos")
            
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

# New endpoint for converting HEIC to JPEG at full resolution
@app.route('/convert/<path:id_or_filename>')
def convert_photo(id_or_filename):
    """Serve a photo file with conversion to JPEG for HEIC files"""
    id_or_filename = urllib.parse.unquote(id_or_filename)
    logger.info(f"Converting and serving photo with ID or filename: {id_or_filename}")
    
    # Check for additional query parameters (path)
    photo_id = id_or_filename  # Now using path parameter as ID first
    path_hint = request.args.get('path')
    quality = int(request.args.get('quality', '90'))
    
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
        
        # No longer fall back to filename lookup when using ID - only use hint if explicitly provided
        if not result and not photo_id.isdigit():
            # Only do a filename lookup if the provided parameter doesn't look like a numeric ID
            filename = id_or_filename
            logger.debug(f"Looking up photo by filename: {filename}")
            cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
            result = cursor.fetchone()
            
        conn.close()
        
        if not result:
            logger.error(f"Photo not found in database: {id_or_filename}")
            return "Photo not found in database", 404
            
        photo_path = result[0]
        logger.debug(f"Found photo path in DB: {photo_path}")
        
        normalized_path = normalize_path(photo_path)
        
        if not os.path.exists(normalized_path):
            logger.error(f"Photo file not found at {normalized_path}")
            return f"Photo file not found at {normalized_path}", 404
        
        # Check if this is a HEIC file that we should convert
        # Get filename from path to check extension
        original_filename = os.path.basename(normalized_path)
        is_heic = original_filename.lower().endswith('.heic')
        
        if is_heic and HEIC_SUPPORT:
            logger.debug(f"Converting HEIC file to JPEG: {normalized_path}")
            try:
                # Ensure HEIF opener is registered
                try:
                    from pillow_heif import register_heif_opener
                    register_heif_opener()
                    logger.debug("HEIF opener registered successfully")
                except ImportError:
                    logger.error("pillow-heif not found, attempting to use PIL directly")
                
                with Image.open(normalized_path) as img:
                    # Get image details for debugging
                    img_format = img.format
                    img_mode = img.mode
                    img_size = img.size
                    logger.info(f"Image details before conversion: format={img_format}, mode={img_mode}, size={img_size}")
                    
                    # Convert to RGB mode if needed
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    buffer = io.BytesIO()
                    # Convert to JPEG at specified quality for full resolution
                    img.save(buffer, format='JPEG', quality=quality, optimize=True)
                    buffer.seek(0)
                    
                    # Log success
                    content_length = buffer.getbuffer().nbytes
                    logger.info(f"Successfully converted HEIC to JPEG: size={img_size}, output bytes={content_length}")
                    
                    return buffer.getvalue(), 200, {
                        'Content-Type': 'image/jpeg',
                        'Content-Length': str(content_length),
                        'Cache-Control': 'max-age=3600'
                    }
            except Exception as e:
                logger.error(f"Error converting HEIC file: {e}")
                return f"Error converting HEIC file: {str(e)}", 500
        else:
            # For non-HEIC files, just serve the file normally
            mimetype, _ = mimetypes.guess_type(normalized_path)
            return send_from_directory(os.path.dirname(normalized_path), os.path.basename(normalized_path), mimetype=mimetype)
        
    except Exception as e:
        logger.exception(f"Error converting photo: {e}")
        return f"Internal server error: {str(e)}", 500

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
    
    # Check if database exists
    db_path = os.path.join(os.getcwd(), 'data', 'photo_library.db')
    if not os.path.exists(db_path):
        db_path = os.path.join(os.getcwd(), 'photo_library.db')
        
    if os.path.exists(db_path):
        logger.info(f"Found database at {db_path}")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get some basic stats
            cursor.execute("SELECT COUNT(*) FROM photos")
            photo_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            gps_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM libraries")
            library_count = cursor.fetchone()[0]
            
            logger.info(f"Database contains {photo_count} photos ({gps_count} with GPS data) in {library_count} libraries")
            conn.close()
        except Exception as e:
            logger.error(f"Error checking database: {e}")
    else:
        logger.warning(f"Database not found at {db_path}")
    
    # Define Flask routes for serving static files
    @app.route('/')
    def serve_index():
        return send_from_directory(os.path.abspath(directory), 'index.html')
    
    # Endpoint for serving original photos
    @app.route('/photos/<path:id_or_filename>')
    def serve_original_photo(id_or_filename):
        """Serve the original photo file by ID or filename"""
        id_or_filename = urllib.parse.unquote(id_or_filename)
        logger.info(f"Serving original photo with ID or filename: {id_or_filename}")
        
        # Check for additional query parameters (path)
        photo_id = id_or_filename  # Now using path parameter as ID first
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
            
            # No longer fall back to filename lookup when using ID - only use hint if explicitly provided
            if not result and not photo_id.isdigit():
                # Only do a filename lookup if the provided parameter doesn't look like a numeric ID
                filename = id_or_filename
                logger.debug(f"Looking up photo by filename: {filename}")
                cursor.execute("SELECT path FROM photos WHERE filename = ?", (filename,))
                result = cursor.fetchone()
                
            conn.close()
            
            if not result:
                logger.error(f"Photo not found in database: {id_or_filename}")
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
    
    # Endpoint for serving thumbnails has been removed
    
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