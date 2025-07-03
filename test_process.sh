#!/bin/bash
# Test script to manually run the photo processing

echo "Running photo processing manually..."
# Get Python path
PYTHON_PATH=$(which python)
echo "Using Python at: $PYTHON_PATH"

while IFS=: read -r LIB_PATH LIB_NAME; do
  echo "Processing library: $LIB_NAME from $LIB_PATH"
  $PYTHON_PATH /app/process_photos.py --process "$LIB_PATH" --library "$LIB_NAME" --db /app/data/photo_library.db
done < /app/logs/libraries.txt
