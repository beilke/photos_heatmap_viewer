#!/usr/bin/env python3
"""
Enhanced debug server for photo heatmap viewer.
This script starts the server with extra debugging options.
"""

import os
import sys
import logging
import json
from server import start_server

def inspect_json_file():
    """Inspect the JSON data file and print diagnostic information."""
    json_file = 'photo_heatmap_data.json'
    print(f"\n==== JSON FILE INSPECTION ====")
    
    if not os.path.exists(json_file):
        print(f"ERROR: {json_file} not found!")
        return False
        
    try:
        file_size = os.path.getsize(json_file)
        print(f"File exists: {json_file} ({file_size} bytes)")
        
        if file_size == 0:
            print("ERROR: File is empty (0 bytes)")
            return False
            
        with open(json_file, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                
                if not isinstance(data, list):
                    print(f"ERROR: JSON root is not an array, found {type(data).__name__}")
                    return False
                    
                print(f"JSON parsed successfully: {len(data)} items")
                
                if len(data) == 0:
                    print("WARNING: JSON array is empty (no photos)")
                    return True
                    
                gps_count = sum(1 for item in data if 'latitude' in item and 'longitude' in item 
                              and item['latitude'] is not None and item['longitude'] is not None)
                print(f"Items with GPS coordinates: {gps_count}/{len(data)} ({gps_count/len(data)*100:.1f}%)")
                
                if gps_count == 0:
                    print("WARNING: No items have GPS coordinates")
                
                return True
                
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON format: {e}")
                return False
                
    except Exception as e:
        print(f"ERROR inspecting file: {e}")
        return False


def setup_logging():
    """Configure detailed logging."""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('debug_server.log')
        ]
    )
    return logging.getLogger(__name__)


def check_environment():
    """Check environment and print diagnostic information."""
    print("\n==== ENVIRONMENT CHECK ====")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Platform: {sys.platform}")
    
    # Check for required files
    for file in ['server.py', 'photo_heatmap_data.json', 'index.html']:
        status = "✓ Found" if os.path.exists(file) else "✗ Missing"
        print(f"{file}: {status}")


if __name__ == "__main__":
    # Setup enhanced logging
    logger = setup_logging()
    
    # Check environment
    check_environment()
    
    # Inspect JSON file
    json_valid = inspect_json_file()
    
    # Start server with debug mode
    if json_valid:
        print("\n==== STARTING DEBUG SERVER ====")
        print("Server will start with enhanced logging")
        print("Press Ctrl+C to stop the server")
        print("Check debug_server.log for detailed logging")
        
        # Start the server with debug flag
        try:
            start_server(port=8000, directory='.', debug_mode=True)
        except Exception as e:
            logger.exception(f"Server crashed: {e}")
    else:
        print("\nJSON file has issues. Please fix before starting the server.")
