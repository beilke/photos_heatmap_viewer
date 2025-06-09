#!/usr/bin/env python3
"""
This script adds a fix for the photo heatmap viewer Docker environment.
It patches the server.py file to ensure it can find and serve index.html correctly.
"""

import os
import sys
import re
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def patch_server_file():
    """Patch the server.py file to fix index.html serving in Docker."""
    server_file = "server.py"
    backup_file = "server.py.bak"
    
    logger.info(f"Creating backup of {server_file} as {backup_file}")
    shutil.copy2(server_file, backup_file)
    
    # Read the server file
    with open(server_file, 'r') as f:
        content = f.read()
    
    # Find the Flask initialization and update it
    flask_init_pattern = r"app = Flask\(__name__,\s*\n?\s*static_folder=os\.path\.abspath\('\.'\),\s*\n?\s*template_folder=os\.path\.abspath\('\.'\)\)"
    fixed_flask_init = """app = Flask(__name__,
           static_folder=os.path.abspath('.'),
           template_folder=os.path.abspath('.'))

# Ensure HTML files can be found in both the template directory and current directory
@app.before_request
def before_request():
    # Check if index.html exists, if not try copying it from templates
    if not os.path.exists('index.html') and os.path.exists('templates/index.html'):
        logging.info("Copying index.html from templates to current directory")
        try:
            shutil.copy('templates/index.html', './index.html')
        except Exception as e:
            logging.error(f"Error copying index.html: {e}")"""
    
    if re.search(flask_init_pattern, content):
        logger.info("Found Flask initialization, patching it...")
        updated_content = re.sub(flask_init_pattern, fixed_flask_init, content)
    else:
        logger.warning("Could not find Flask initialization pattern. Manual fix might be needed.")
        updated_content = content
    
    # Fix the root route if necessary
    root_route_pattern = r'@app\.route\(\'/\'\)\s*\n\s*def serve_index\(\):\s*\n\s*return send_from_directory\(os\.path\.abspath\(directory\), \'index\.html\'\)'
    fixed_root_route = """@app.route('/')
    def serve_index():
        # First try the current directory
        if os.path.exists('index.html'):
            return send_from_directory(os.path.abspath('.'), 'index.html')
        # Then try templates directory as fallback
        elif os.path.exists('templates/index.html'):
            return send_from_directory(os.path.abspath('templates'), 'index.html')
        else:
            logger.error("index.html not found in any directory!")
            return "Error: index.html not found", 404"""
    
    if re.search(root_route_pattern, updated_content):
        logger.info("Found root route, patching it...")
        updated_content = re.sub(root_route_pattern, fixed_root_route, updated_content)
    
    # Write the updated content
    with open(server_file, 'w') as f:
        f.write(updated_content)
    
    logger.info(f"Successfully patched {server_file}")
    return True

if __name__ == "__main__":
    if patch_server_file():
        print("Server file patched successfully!")
    else:
        print("Failed to patch server file.")
