#!/bin/bash
# Script to fix cron job formatting in the process_libraries.sh script
# This fixes the issue with cron jobs not executing properly

# Also fix the initial processing Python path in process_libraries.sh
sed -i '
/# Check if database exists/,/python \/app\/process_photos.py/ s|/usr/bin/python|$(which python3 || which python || echo "python")|g
' /app/process_libraries.sh

# Replace the cron job creation section with one that uses bash -c properly
sed -i '
/# Add library processing jobs to the cron file/,/fi/ c\
# Find Python executable path\
PYTHON_PATH=$(which python3 || which python || echo "/usr/bin/python")\
echo "Using Python path: $PYTHON_PATH"\
\
# Verify Python path works\
if ! $PYTHON_PATH --version &>/dev/null; then\
  echo "WARNING: Python executable not found at $PYTHON_PATH, searching alternatives..."\
  PYTHON_PATH=$(find /usr/bin /usr/local/bin -name "python*" | grep -E "python[0-9]?$" | head -1 || echo "python")\
  echo "Using alternative Python path: $PYTHON_PATH"\
fi\
\
# Add library processing jobs to the cron file\
if [ -s /app/logs/libraries.txt ]; then\
  while IFS=: read -r LIB_PATH LIB_NAME; do\
    # Format properly for /etc/cron.d/ - use bash -c to wrap the entire command\
    echo "${UPDATE_INTERVAL} root bash -c '"'"'cd /app && $PYTHON_PATH /app/process_photos.py --process \"${LIB_PATH}\" --library \"${LIB_NAME}\" --db /app/data/photo_library.db >> /app/logs/cron_${LIB_NAME}.log 2>&1'"'"'" >> /etc/cron.d/process_photos\
    echo "Added scheduled processing for library: $LIB_NAME"\
  done < /app/logs/libraries.txt\
else\
  echo "WARNING: No libraries found to schedule. Check if libraries are properly mounted."\
fi
' /app/process_libraries.sh

# Replace the test cron job line to use bash -c
sed -i '
/# Test cron job/,/\* \* \* \* \*/ c\
# Test cron job - runs every minute\
* * * * * root bash -c '"'"'echo "[$(date +\\%s)] Cron test successful" >> /app/logs/cron_test.log 2>&1'"'"'
' /etc/cron.d/process_photos

echo "Fixed cron job formatting"
echo "Cron file contents:"
cat /etc/cron.d/process_photos

# Verify crontab installation and restart cron
echo "Restarting cron service..."
pkill cron
sleep 1
cron -f -L 15 &
