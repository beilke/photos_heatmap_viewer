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
            self.serve_original_photo(path[8:])  # Remove '/photos/' prefix
        # Add API endpoint for photo markers
        elif path.startswith('/api/markers'):
            logger.info(f"API request received: {path}")
            self.serve_photo_markers()
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

            # Open and serve the original file
            with open(normalized_path, 'rb') as f:
                fs = os.fstat(f.fileno())
                content_length = fs[6]

                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')  # Could be made more dynamic
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
                return
                
            # Generate thumbnail
            logger.debug(f"Generating thumbnail for: {normalized_path}")
            with Image.open(normalized_path) as img:
                # Resize to a thumbnail
                img.thumbnail((200, 200))
                
                # Prepare to send the image
                buffer = io.BytesIO()
                img_format = img.format if img.format else 'JPEG'
                img.save(buffer, format=img_format)
                buffer.seek(0)
                
                # Send headers
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
            
            # Get photos with location data - include path
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
            
            # Create final data structure with photos
            result = json.dumps({"photos": photos})
            self.wfile.write(result.encode('utf-8'))
            
            logger.info(f"Successfully served {len(photos)} photo markers")
            conn.close()
            
        except Exception as e:
            logger.exception(f"Error serving photo markers: {e}")
            self.send_error(500, f"Internal server error: {str(e)}")

def signal_handler(sig, frame):
    logger.info("Gracefully shutting down server...")
    sys.exit(0)

def start_server(port=8000, directory='.', debug_mode=False):
    """Start a simple HTTP server to serve the photo heatmap viewer"""
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set log level based on debug mode
    if debug_mode:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug mode enabled - verbose logging activated")
    
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
    
    # Create the server with our responsive subclass and custom handler
    with QuickResponseTCPServer(("", port), PhotoHTTPRequestHandler) as httpd:
        logger.info(f"Serving at http://localhost:{port}")
        logger.info(f"Press Ctrl+C to stop the server")
        
        try:
            # Use polling pattern instead of serve_forever() for more responsiveness
            while True:
                httpd.handle_request()
                time.sleep(0.01)  # Small sleep to prevent CPU hogging
        except KeyboardInterrupt:
            logger.info("Server stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start a web server for the Photo Heatmap Viewer')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--dir', default='.', help='Directory to serve files from')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set log level based on debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")
    
    start_server(args.port, args.dir)
