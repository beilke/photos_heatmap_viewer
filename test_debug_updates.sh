#!/bin/bash

# Debug Test Script for Library Updates Panel
# This script creates test update files and starts the Flask server

echo "========= DEBUG TEST FOR LIBRARY UPDATES DISPLAY ========="

# Create data directory if it doesn't exist
mkdir -p data
echo "Data directory created/confirmed at $(pwd)/data"

# Create some test library update files with clear debug markers
echo "$(date +'%Y-%m-%d %H:%M:%S') [TEST FILE 1]" > "./data/last_update_Debug_Library_1.txt"
echo "$(date -d '1 hour ago' +'%Y-%m-%d %H:%M:%S') [TEST FILE 2]" > "./data/last_update_Debug_Library_2.txt"
echo "$(date -d '1 day ago' +'%Y-%m-%d %H:%M:%S') [TEST FILE 3]" > "./data/last_update_Debug_Library_3.txt"

echo "Created test update files:"
ls -la ./data/last_update_*.txt

# Run the server with debug mode enabled
echo "Starting Flask server with debug output..."
echo "Please access http://localhost:8000 in your browser"
echo "You should see a RED panel in the bottom right with debug information"
echo "====================================================="

# Start the server
python server.py --port 8000 --dir . --debug
