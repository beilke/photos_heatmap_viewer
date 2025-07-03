#!/bin/sh
# Script to process photo libraries and set up cron jobs for updates

# Find all library directories in /photos
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
  while IFS=: read -r LIB_PATH LIB_NAME; do
    echo "Processing library: $LIB_NAME"
    python /app/process_photos.py --process "$LIB_PATH" --library "$LIB_NAME"
  done < /app/logs/libraries.txt
fi

# Setup cron for periodic updates
mkdir -p /etc/cron.d

# Default cron schedule if not provided
: ${UPDATE_INTERVAL:="0 */6 * * *"}

# Create cron jobs for libraries
rm -f /etc/cron.d/process_photos
touch /etc/cron.d/process_photos
# Add proper SHELL and PATH to crontab to ensure commands work
echo "SHELL=/bin/sh" >> /etc/cron.d/process_photos
echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/cron.d/process_photos
echo "" >> /etc/cron.d/process_photos
while IFS=: read -r LIB_PATH LIB_NAME; do
  echo "$UPDATE_INTERVAL root python /app/process_photos.py --process \"$LIB_PATH\" --library \"$LIB_NAME\" >> /app/logs/cron_${LIB_NAME}.log 2>&1" >> /etc/cron.d/process_photos
  echo "Added scheduled processing for library: $LIB_NAME"
done < /app/logs/libraries.txt

# Give execution rights to the cron job
chmod 0644 /etc/cron.d/process_photos

# Apply cron configuration
crontab -u root /etc/cron.d/process_photos

echo "Photo processing schedule set up with interval: $UPDATE_INTERVAL"

# Start cron service based on available commands
echo "Starting cron service..."

# Debug which cron commands are available
echo "Available cron commands:"
which cron crond 2>/dev/null || echo "No cron commands found in PATH"
echo "Contents of /usr/sbin:"
ls -la /usr/sbin/cron* 2>/dev/null || echo "No cron files in /usr/sbin"
echo "Contents of /usr/bin:"
ls -la /usr/bin/cron* 2>/dev/null || echo "No cron files in /usr/bin"

if command -v cron >/dev/null 2>&1; then
  echo "Found cron command, starting with cron -f"
  # Start cron in foreground to keep container running
  exec cron -f
elif command -v service >/dev/null 2>&1; then
  echo "Found service command, starting cron service"
  service cron start
  # Keep container running since service runs in background
  echo "Keeping container alive with tail -f /dev/null"
  exec tail -f /dev/null
elif command -v crond >/dev/null 2>&1; then
  echo "Found crond command, starting with crond -f"
  # Start crond in foreground to keep container running
  exec crond -f
else
  echo "WARNING: Could not find cron service or crond command"
  echo "Will run initial processing only"
  # Keep container running even without cron
  echo "Keeping container alive with tail -f /dev/null"
  exec tail -f /dev/null
fi
