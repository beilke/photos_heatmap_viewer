#!/bin/sh
# This script will copy the process_libraries.sh to the correct location and set permissions
# then execute it

# Copy the script from mounted volume to the container
cp /scripts/process_libraries.sh /app/process_libraries.sh
chmod +x /app/process_libraries.sh

# Execute the script
exec /app/process_libraries.sh
