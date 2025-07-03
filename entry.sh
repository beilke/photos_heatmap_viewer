#!/bin/sh
# This script will copy the process_libraries.sh to the correct location and set permissions
# then execute it

# Copy the script from mounted volume to the container
cp /scripts/process_libraries.sh /app/process_libraries.sh
chmod +x /app/process_libraries.sh

# Apply the cron fixes
if [ -f "/app/fix_cron_format.sh" ]; then
    echo "Applying cron formatting fix..."
    chmod +x /app/fix_cron_format.sh
    # Execute the fix script after process_libraries.sh runs
    /app/process_libraries.sh && /app/fix_cron_format.sh
else
    # Execute the script without fixes
    exec /app/process_libraries.sh
fi
