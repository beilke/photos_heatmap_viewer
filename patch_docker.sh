#!/bin/bash
# Script to patch the Dockerfile for proper file handling

# Backup original Dockerfile
cp Dockerfile Dockerfile.bak

# Create updated Dockerfile
cat > Dockerfile.new << 'EOF'
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
RUN mkdir -p /app/logs /app/data

# Copy application files
COPY *.py ./
COPY *.html ./
COPY *.css ./
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

# Copy the fix script to detect and fix issues with file locations
COPY fix_docker_env.py ./
RUN chmod +x ./fix_docker_env.py
RUN python ./fix_docker_env.py

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["./healthcheck.sh"]

# Run the server
CMD ["python", "server.py", "--db", "/app/data/photo_library.db", "--host", "0.0.0.0", "--port", "8000"]
EOF

# Replace old Dockerfile with new one
mv Dockerfile.new Dockerfile

echo "Dockerfile has been patched to fix HTML file location issues."
