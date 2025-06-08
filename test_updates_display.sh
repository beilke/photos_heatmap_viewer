#!/bin/bash

# Test script to demonstrate the library update times feature

# Create data directory if it doesn't exist
mkdir -p data

# Create some test library update files
echo "$(date +"%Y-%m-%d %H:%M:%S")" > "./data/last_update_Test_Library_1.txt"
echo "$(date -d '1 hour ago' +"%Y-%m-%d %H:%M:%S")" > "./data/last_update_Test_Library_2.txt"
echo "$(date -d '1 day ago' +"%Y-%m-%d %H:%M:%S")" > "./data/last_update_Test_Library_3.txt"

# Run the server with Flask
echo "Starting server with library update times display enabled..."
echo "Open http://localhost:8000 in your browser to see the update times"
python server.py --port 8000 --dir . --debug
