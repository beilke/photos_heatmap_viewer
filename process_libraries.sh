#!/bin/sh 
# Script to process photo libraries and set up cron jobs for updates

echo "Detecting mounted photo libraries..."
mkdir -p /app/logs
rm -f /app/logs/libraries.txt

for DIR in /photos/*; do
  if [ -d "$DIR" ]; then
    NAME=$(basename "$DIR")
    echo "Found library: $NAME at $DIR"
    echo "$DIR:$NAME" >> /app/logs/libraries.txt
  fi
done

# Check if database exists
if [ ! -f /app/data/photo_library.db ]; then
  echo "Database not found. Running initial processing..."

  mkdir -p /app/data

  if [ ! -s /app/logs/libraries.txt ]; then
    echo "ERROR: No photo libraries found. Check if libraries are properly mounted."
    ls -la /photos/
    echo "Will continue setup but no photos will be processed."
  else
    echo "Found libraries to process:"
    cat /app/logs/libraries.txt

    while IFS=: read -r LIB_PATH LIB_NAME; do
      echo "Processing library: $LIB_NAME at path: $LIB_PATH"
      echo "Running: /usr/bin/python /app/process_photos.py --process \"$LIB_PATH\" --library \"$LIB_NAME\" --db /app/data/photo_library.db"
      /usr/bin/python /app/process_photos.py --process "$LIB_PATH" --library "$LIB_NAME" --db /app/data/photo_library.db

      if [ $? -eq 0 ]; then
        echo "Successfully processed library: $LIB_NAME"
      else
        echo "ERROR processing library: $LIB_NAME"
      fi

      echo "$(date +"%Y-%m-%d %H:%M:%S"): Initial processing" > "/app/data/last_update_${LIB_NAME}.txt"
    done < /app/logs/libraries.txt
  fi

  if [ -f /app/data/photo_library.db ]; then
    echo "Database successfully created at /app/data/photo_library.db"
  else
    echo "WARNING: Database file was not created. Check for errors above."
  fi
else
  echo "Database found at /app/data/photo_library.db, skipping initial processing"
fi

# Setup cron for periodic updates
mkdir -p /etc/cron.d

# Use provided UPDATE_INTERVAL or default to every minute
: ${UPDATE_INTERVAL:="*/1 * * * *"}

# Create a properly formatted cron file
rm -f /etc/cron.d/process_photos

# Create cron file content at once rather than line by line to avoid format issues
cat > /etc/cron.d/process_photos << EOF
# Setting environment variables for cron jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/root
LANG=en_US.UTF-8
PYTHONPATH=/app

# Test cron job - runs every minute
* * * * * root echo "[$(date +\%s)] Cron test successful" >> /app/logs/cron_test.log 2>&1
EOF

# Find Python executable path
PYTHON_PATH=$(which python3 || which python || echo "/usr/bin/python")
echo "Using Python path: $PYTHON_PATH"

# Verify Python path works
if ! $PYTHON_PATH --version &>/dev/null; then
  echo "WARNING: Python executable not found at $PYTHON_PATH, searching alternatives..."
  PYTHON_PATH=$(find /usr/bin /usr/local/bin -name "python*" | grep -E "python[0-9]?$" | head -1 || echo "python")
  echo "Using alternative Python path: $PYTHON_PATH"
fi

# Add library processing jobs to the cron file
if [ -s /app/logs/libraries.txt ]; then
  while IFS=: read -r LIB_PATH LIB_NAME; do
    # Format properly for /etc/cron.d/ - use bash -c to wrap the entire command
    echo "${UPDATE_INTERVAL} root bash -c 'cd /app && $PYTHON_PATH /app/process_photos.py --process \"${LIB_PATH}\" --library \"${LIB_NAME}\" --db /app/data/photo_library.db >> /app/logs/cron_${LIB_NAME}.log 2>&1'" >> /etc/cron.d/process_photos
    echo "Added scheduled processing for library: $LIB_NAME"
  done < /app/logs/libraries.txt
else
  echo "WARNING: No libraries found to schedule. Check if libraries are properly mounted."
fi

# Set proper permissions for the cron file
chmod 0644 /etc/cron.d/process_photos

echo "Photo processing schedule set up with interval: $UPDATE_INTERVAL"
echo "Crontab file contents:"
cat /etc/cron.d/process_photos

# Install the cron file
crontab /etc/cron.d/process_photos

# Verify crontab installation
echo "Verifying crontab installation:"
crontab -l

# Start cron service
echo "Starting cron service with verbose logging..."
exec cron -f -L 15
