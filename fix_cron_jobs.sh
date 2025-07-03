#!/bin/bash
# Script to fix the cron job issues in the photo-heatmap-processor container

echo "This script will fix the cron job issues in the photo-heatmap-processor container."
echo "It will:"
echo "1. Create a properly formatted cron file"
echo "2. Apply it to the container"
echo "3. Test the execution"

# Create a proper cron file with all necessary environment settings
cat <<'EOF' > fix_cron.txt
# Setting environment variables for cron jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/root
LANG=en_US.UTF-8
PYTHONPATH=/app

# Test cron job - runs every minute
* * * * * root bash -c 'echo "[$(date +\%s)] Cron test successful" >> /app/logs/cron_test.log 2>&1'

# Photo processing jobs - use the UPDATE_INTERVAL environment variable from inside the container
EOF

# Fetch the libraries from the container to add them to our cron file
echo "Fetching libraries from container..."
docker exec photo-heatmap-processor cat /app/logs/libraries.txt > temp_libraries.txt

# Find out the Python executable path in the container with verification
echo "Checking Python path in container..."
PYTHON_PATH=$(docker exec photo-heatmap-processor bash -c 'which python3 || which python || echo "python"')
echo "Found Python path: $PYTHON_PATH"

# Verify Python path actually works
echo "Verifying Python executable..."
if docker exec photo-heatmap-processor bash -c "$PYTHON_PATH --version" &>/dev/null; then
  echo "Python executable verified: $PYTHON_PATH"
else
  echo "WARNING: $PYTHON_PATH might not be valid. Trying alternatives..."
  # Try to find a valid Python interpreter
  PYTHON_PATH=$(docker exec photo-heatmap-processor bash -c 'find /usr/bin /usr/local/bin -name "python*" 2>/dev/null | grep -E "python[0-9]?$" | head -1 || echo "python"')
  echo "Using alternative Python path: $PYTHON_PATH"
  # Final verification
  if ! docker exec photo-heatmap-processor bash -c "$PYTHON_PATH --version" &>/dev/null; then
    echo "WARNING: Could not find working Python interpreter. Using 'python' and hoping for the best."
    PYTHON_PATH="python"
  fi
fi

# Get the current update interval
INTERVAL=$(docker exec photo-heatmap-processor sh -c 'echo $UPDATE_INTERVAL')
if [ -z "$INTERVAL" ]; then
  INTERVAL="*/1 * * * *"
  echo "Using default interval: $INTERVAL"
else
  echo "Using configured interval: $INTERVAL"
fi

# Add the library processing jobs to the cron file
echo "Adding library processing jobs to cron file..."
while IFS=: read -r LIB_PATH LIB_NAME; do
  # NOTE: We're using the proper format for cron.d files - username field is required
  # But we're making sure the command is properly quoted to avoid the 'root: command not found' error
  echo "$INTERVAL root bash -c \"cd /app && $PYTHON_PATH /app/process_photos.py --process ${LIB_PATH} --library ${LIB_NAME} --db /app/data/photo_library.db >> /app/logs/cron_${LIB_NAME}.log 2>&1\"" >> fix_cron.txt
  echo "Added job for library: $LIB_NAME"
done < temp_libraries.txt

# Add debugging info to the logs
echo "# The following entries were added by fix_cron_jobs.sh on $(date)" >> fix_cron.txt

# Check if container is running
echo "Checking if container is running..."
if ! docker ps | grep -q photo-heatmap-processor; then
  echo "ERROR: Container photo-heatmap-processor is not running!"
  exit 1
fi

# Make sure libraries.txt exists
if [ ! -s temp_libraries.txt ]; then
  echo "WARNING: No libraries found in libraries.txt. Checking if file exists in container..."
  if docker exec photo-heatmap-processor ls -la /app/logs/libraries.txt; then
    echo "Libraries file exists but might be empty. Creating sample entry for testing..."
    echo "/photos/sample:sample" > temp_libraries.txt
  else
    echo "ERROR: libraries.txt not found in container!"
    exit 1
  fi
fi

# Copy and install the cron file
echo "Copying cron file to container..."
docker cp fix_cron.txt photo-heatmap-processor:/etc/cron.d/process_photos

# Set proper permissions
echo "Setting proper permissions..."
docker exec photo-heatmap-processor chmod 0644 /etc/cron.d/process_photos

# Install the cron file - NOTE: We'll use a different approach to avoid confusion between cron.d format and user crontab
echo "Installing cron file..."
# We'll just use the cron.d directory and not try to install it to user crontab
# This will make sure the 'root' username field is properly handled
docker exec photo-heatmap-processor bash -c 'cat /etc/cron.d/process_photos'

# Verify installation
echo "Verifying crontab contents:"
docker exec photo-heatmap-processor crontab -l

# Restart the cron service
echo "Restarting cron service..."
docker exec photo-heatmap-processor bash -c 'pkill cron; sleep 1; cron -f -L 15 &'

# Create a test script to manually execute the jobs
echo "Creating a test script to manually execute jobs..."
cat <<'EOF' > test_process.sh
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
EOF

# Copy test script to container
docker cp test_process.sh photo-heatmap-processor:/app/test_process.sh
docker exec photo-heatmap-processor chmod +x /app/test_process.sh

# Clean up temporary files
rm fix_cron.txt temp_libraries.txt

echo ""
echo "Fix applied. The cron jobs should now execute properly."
echo ""
echo "To manually test the photo processing, run:"
echo "docker exec -it photo-heatmap-processor /app/test_process.sh"
echo ""
echo "To check if cron is working, check the test log:"
echo "docker exec -it photo-heatmap-processor cat /app/logs/cron_test.log"
echo ""
echo "To check the actual processing logs, run:"
echo "docker exec -it photo-heatmap-processor ls -la /app/logs/"
echo "docker exec -it photo-heatmap-processor cat /app/logs/cron_<library_name>.log"
