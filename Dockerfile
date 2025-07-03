FROM python:3.10-slim

WORKDIR /app

# Install required packages and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    cron \
    logrotate \
    crontab \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir Flask

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/templates /app/static

# Copy application files
COPY *.py ./
COPY *.html ./
# Docker COPY syntax for directories - no trailing slash on source
COPY ./static ./static
# Verify static files were copied correctly
RUN echo "Verifying static files:" && \
    find /app/static -type f | sort
# Database files are mounted via volume at runtime

# Configure logrotate to keep logs for one week
RUN echo '/app/logs/*.log {\n\
    daily\n\
    rotate 7\n\
    compress\n\
    delaycompress\n\
    missingok\n\
    notifempty\n\
    create 644 root root\n\
}' > /etc/logrotate.d/photo_heatmap

# Create a script to process photos and record the update time
RUN echo '#!/bin/bash\n\
LIBRARY_FOLDER="$1"\n\
LIBRARY_NAME="$2"\n\
LOG_FILE="/app/logs/photo_processing_$(date +%Y%m%d_%H%M%S).log"\n\
echo "Processing library: $LIBRARY_NAME from $LIBRARY_FOLDER at $(date)" >> $LOG_FILE\n\
python process_photos.py --process "$LIBRARY_FOLDER" --library "$LIBRARY_NAME" --db /app/data/photo_library.db >> $LOG_FILE 2>&1\n\
# Record the last update time\n\
echo "$(date +"%Y-%m-%d %H:%M:%S"): $LIBRARY_NAME" > "/app/data/last_update_${LIBRARY_NAME}.txt"\n\
echo "Done processing $LIBRARY_NAME at $(date)" >> $LOG_FILE\n\
' > /app/process_library.sh && chmod +x /app/process_library.sh

# Health check script
RUN echo '#!/bin/bash\n\
curl -f http://localhost:8000/health || exit 1\n\
' > /app/healthcheck.sh && chmod +x /app/healthcheck.sh

# Create process_libraries script for batch processing and scheduling
RUN echo '#!/bin/sh\n\
# Script to process photo libraries and set up cron jobs for updates\n\
\n\
# Find all library directories in /photos\n\
echo '"'"'Detecting mounted photo libraries...'"'"'\n\
mkdir -p /app/logs\n\
rm -f /app/logs/libraries.txt\n\
\n\
for DIR in /photos/*; do\n\
  if [ -d "$DIR" ]; then\n\
    NAME=$(basename "$DIR")\n\
    echo "Found library: $NAME at $DIR"\n\
    echo "$DIR:$NAME" >> /app/logs/libraries.txt\n\
  fi\n\
done\n\
\n\
# Find the correct Python path first - so it can be used for both initial processing and cron jobs\n\
PYTHON_PATH=$(which python3 || which python || echo "python")\n\
echo "Using Python path: $PYTHON_PATH"\n\
\n\
# Verify Python path works\n\
if ! $PYTHON_PATH --version &>/dev/null; then\n\
  echo "WARNING: Python path $PYTHON_PATH not working, searching alternatives..."\n\
  PYTHON_PATH=$(find /usr/bin /usr/local/bin -name "python*" | grep -E "python[0-9]?$" | head -1 || echo "python")\n\
  echo "Using alternative Python path: $PYTHON_PATH"\n\
fi\n\
\n\
# Check if database exists\n\
if [ ! -f /app/data/photo_library.db ]; then\n\
  echo '"'"'Database not found. Running initial processing...'"'"'\n\
  mkdir -p /app/data\n\
  \n\
  if [ ! -s /app/logs/libraries.txt ]; then\n\
    echo "ERROR: No photo libraries found. Check if libraries are properly mounted."\n\
    ls -la /photos/\n\
    echo "Will continue setup but no photos will be processed."\n\
  else\n\
    echo "Found libraries to process:"\n\
    cat /app/logs/libraries.txt\n\
    \n\
    while IFS=: read -r LIB_PATH LIB_NAME; do\n\
      echo "Processing library: $LIB_NAME at path: $LIB_PATH"\n\
      echo "Running: $PYTHON_PATH /app/process_photos.py --process \\"$LIB_PATH\\" --library \\"$LIB_NAME\\" --db /app/data/photo_library.db"\n\
      $PYTHON_PATH /app/process_photos.py --process "$LIB_PATH" --library "$LIB_NAME" --db /app/data/photo_library.db\n\
      \n\
      if [ $? -eq 0 ]; then\n\
        echo "Successfully processed library: $LIB_NAME"\n\
      else\n\
        echo "ERROR processing library: $LIB_NAME"\n\
      fi\n\
      \n\
      echo "$(date +"%Y-%m-%d %H:%M:%S"): Initial processing" > "/app/data/last_update_${LIB_NAME}.txt"\n\
    done < /app/logs/libraries.txt\n\
  fi\n\
  \n\
  if [ -f /app/data/photo_library.db ]; then\n\
    echo "Database successfully created at /app/data/photo_library.db"\n\
  else\n\
    echo "WARNING: Database file was not created. Check for errors above."\n\
  fi\n\
else\n\
  echo "Database found at /app/data/photo_library.db, skipping initial processing"\n\
fi\n\
\n\
# Setup cron for periodic updates\n\
mkdir -p /etc/cron.d\n\
\n\
# Python path already defined above\n\
\n\
# Create cron jobs for libraries\n\
rm -f /etc/cron.d/process_photos\n\
\n\
# First create the header with environment settings\n\
cat > /etc/cron.d/process_photos << '"'"'EOF'"'"'\n\
# Setting environment variables for cron jobs\n\
SHELL=/bin/bash\n\
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n\
HOME=/root\n\
LANG=en_US.UTF-8\n\
PYTHONPATH=/app\n\
\n\
# Test cron job - runs every minute\n\
* * * * * root bash -c '"'"'echo "[$(date +\\%s)] Cron test successful" >> /app/logs/cron_test.log 2>&1'"'"'\n\
EOF\n\
\n\
while IFS=: read -r LIB_PATH LIB_NAME; do\n\
  echo "${UPDATE_INTERVAL} root bash -c '"'"'cd /app && $PYTHON_PATH /app/process_photos.py --process \"${LIB_PATH}\" --library \"${LIB_NAME}\" --db /app/data/photo_library.db >> /app/logs/cron_${LIB_NAME}.log 2>&1'"'"'" >> /etc/cron.d/process_photos\n\
  echo "Added scheduled processing for library: $LIB_NAME"\n\
done < /app/logs/libraries.txt\n\
\n\
# Give execution rights to the cron job\n\
chmod 0644 /etc/cron.d/process_photos\n\
\n\
# Apply cron job\n\
crontab /etc/cron.d/process_photos\n\
\n\
echo "Photo processing schedule set up with interval: ${UPDATE_INTERVAL}"\n\
\n\
# Start cron and keep container running\n\
crond -f\n\
' > /app/process_libraries.sh && chmod +x /app/process_libraries.sh

# Expose port
EXPOSE 8000

# Health check
# Add the cron fix script
COPY fix_cron_format.sh /app/fix_cron_format.sh
RUN chmod +x /app/fix_cron_format.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["./healthcheck.sh"]

# Run the server
CMD ["python", "server.py", "--db", "/app/data/photo_library.db", "--host", "0.0.0.0", "--port", "8000"]
