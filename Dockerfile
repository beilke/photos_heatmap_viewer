FROM python:3.10-slim

WORKDIR /app

# Install required packages and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    cron \
    logrotate \
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
# Check if database exists\n\
if [ ! -f /app/data/photo_library.db ]; then\n\
  echo '"'"'Database not found. Running initial processing...'"'"'\n\
  while IFS=: read -r LIB_PATH LIB_NAME; do\n\
    echo "Processing library: $LIB_NAME"\n\
    python /app/process_photos.py --process "$LIB_PATH" --library "$LIB_NAME"\n\
  done < /app/logs/libraries.txt\n\
fi\n\
\n\
# Setup cron for periodic updates\n\
mkdir -p /etc/cron.d\n\
\n\
# Create cron jobs for libraries\n\
rm -f /etc/cron.d/process_photos\n\
while IFS=: read -r LIB_PATH LIB_NAME; do\n\
  echo "${UPDATE_INTERVAL} python /app/process_photos.py --process \\"$LIB_PATH\\" --library \\"$LIB_NAME\\" >> /app/logs/cron_${LIB_NAME}.log 2>&1" >> /etc/cron.d/process_photos\n\
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
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["./healthcheck.sh"]

# Run the server
CMD ["python", "server.py", "--db", "/app/data/photo_library.db", "--host", "0.0.0.0", "--port", "8000"]
