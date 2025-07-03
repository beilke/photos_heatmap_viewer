#!/bin/bash
# Script to debug and fix cron issues in the photo-heatmap-processor container

# Function to display a section header
section() {
  echo ""
  echo "==================================================================="
  echo "  $1"
  echo "==================================================================="
  echo ""
}

section "Checking container status"
docker ps | grep photo-heatmap-processor

section "Checking for photo libraries"
docker exec photo-heatmap-processor ls -la /photos/

section "Checking libraries.txt content"
docker exec photo-heatmap-processor cat /app/logs/libraries.txt

section "Checking current crontab content"
docker exec photo-heatmap-processor crontab -l

section "Checking cron.d directory"
docker exec photo-heatmap-processor ls -la /etc/cron.d/

section "Checking process_photos cron file"
docker exec photo-heatmap-processor cat /etc/cron.d/process_photos

section "Checking for cron logs"
docker exec photo-heatmap-processor ls -la /app/logs/

section "Fixing cron configuration"

# Create a corrected cron file
cat > fixed_cron << EOF
# Setting environment variables for cron jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/root
LANG=en_US.UTF-8
PYTHONPATH=/app

# Test cron job - runs every minute
* * * * * root echo "[$(date +%s)] Cron test successful" >> /app/logs/cron_test.log 2>&1
EOF

# Get library information from the container
docker exec photo-heatmap-processor cat /app/logs/libraries.txt > temp_libraries.txt

# Add processing jobs for each library
if [ -s temp_libraries.txt ]; then
  while IFS=: read -r LIB_PATH LIB_NAME; do
    echo "*/1 * * * * root /usr/bin/python /app/process_photos.py --process ${LIB_PATH} --library ${LIB_NAME} --db /app/data/photo_library.db >> /app/logs/cron_${LIB_NAME}.log 2>&1" >> fixed_cron
    echo "Added job for library: $LIB_NAME"
  done < temp_libraries.txt
else
  echo "WARNING: No libraries found!"
fi

# Copy the fixed cron file to the container
docker cp fixed_cron photo-heatmap-processor:/etc/cron.d/process_photos
docker exec photo-heatmap-processor chmod 0644 /etc/cron.d/process_photos
docker exec photo-heatmap-processor crontab /etc/cron.d/process_photos

section "Checking updated crontab"
docker exec photo-heatmap-processor crontab -l

section "Running manual test"
docker exec photo-heatmap-processor bash -c '
for DIR in /photos/*; do
  if [ -d "$DIR" ]; then
    NAME=$(basename "$DIR")
    echo "Testing manual processing for: $NAME"
    /usr/bin/python /app/process_photos.py --process "$DIR" --library "$NAME" --db /app/data/photo_library.db
  fi
done'

section "Restarting cron service"
docker exec photo-heatmap-processor bash -c 'pkill cron; sleep 1; cron -f -L 15 &'

section "Fix completed"
echo "The cron configuration has been fixed."
echo "To verify it's working, check the logs in a few minutes:"
echo "docker exec photo-heatmap-processor cat /app/logs/cron_test.log"
echo "docker exec photo-heatmap-processor ls -la /app/logs/"
echo ""
echo "You may need to restart the container:"
echo "docker restart photo-heatmap-processor"

# Clean up temp files
rm -f fixed_cron temp_libraries.txt
