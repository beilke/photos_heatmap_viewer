#!/bin/bash
# filepath: generateBuild-photo-heatmap-viewer.sh
# Script to download, extract and run the photos_heatmap_viewer project in Docker
# Designed to work on Linux systems

set -e  # Exit immediately if a command exits with a non-zero status

# Setup temporary directory
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: ${TEMP_DIR}"
cd "${TEMP_DIR}"

# Function to clean up on exit
cleanup() {
  echo "Cleaning up temporary directory..."
  if [ -n "${TEMP_DIR}" ] && [ -d "${TEMP_DIR}" ]; then
    cd /
    rm -rf "${TEMP_DIR}"
    echo "Temporary directory cleaned up"
  fi
}

# Set trap for cleanup
trap cleanup EXIT

# Check for required tools
echo "Checking for required tools..."
MISSING_TOOLS=()

if ! command -v docker &> /dev/null; then
  MISSING_TOOLS+=("Docker")
fi

if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
  MISSING_TOOLS+=("curl or wget")
fi

# Check if we have any extraction tool available
HAVE_EXTRACTION_TOOL=false
if command -v unzip &> /dev/null; then
  HAVE_EXTRACTION_TOOL=true
elif command -v tar &> /dev/null; then
  HAVE_EXTRACTION_TOOL=true
elif command -v busybox &> /dev/null && busybox --list | grep -q "unzip"; then
  HAVE_EXTRACTION_TOOL=true
elif command -v 7z &> /dev/null; then
  HAVE_EXTRACTION_TOOL=true
elif command -v jar &> /dev/null; then
  HAVE_EXTRACTION_TOOL=true
fi

if [ "$HAVE_EXTRACTION_TOOL" = false ]; then
  MISSING_TOOLS+=("extraction tool (unzip, tar, busybox, 7z, or jar)")
fi

if [ ${#MISSING_TOOLS[@]} -ne 0 ]; then
  echo "Error: The following required tools are missing:"
  for TOOL in "${MISSING_TOOLS[@]}"; do
    echo "  - ${TOOL}"
  done
  echo "Please install these tools and try again."
  exit 1
fi

# Download the repository
echo "Downloading the repository..."
if command -v curl &> /dev/null; then
  curl -L https://github.com/beilke/photos_heatmap_viewer/archive/refs/heads/main.zip -o repo.zip
  echo "Download completed using curl."
elif command -v wget &> /dev/null; then
  wget https://github.com/beilke/photos_heatmap_viewer/archive/refs/heads/main.zip -O repo.zip
  echo "Download completed using wget."
fi

# Extract the repository
echo "Extracting the repository..."
REPO_DIR="photos_heatmap_viewer-main"
EXTRACTION_DONE=false

# Try different extraction tools in order of preference
if command -v unzip &> /dev/null; then
  unzip -q repo.zip
  EXTRACTION_DONE=true
  echo "Extraction completed using unzip."
elif command -v busybox &> /dev/null && busybox --list | grep -q "unzip"; then
  busybox unzip -q repo.zip
  EXTRACTION_DONE=true
  echo "Extraction completed using busybox unzip."
elif command -v 7z &> /dev/null; then
  7z x repo.zip -y > /dev/null
  EXTRACTION_DONE=true
  echo "Extraction completed using 7z."
elif command -v jar &> /dev/null; then
  jar xf repo.zip
  EXTRACTION_DONE=true
  echo "Extraction completed using jar."
elif command -v tar &> /dev/null; then
  # First convert zip to tar if possible
  if command -v zipdetails &> /dev/null; then
    mkdir -p extracted
    cd extracted
    unzip ../repo.zip
    cd ..
    EXTRACTION_DONE=true
    echo "Extraction completed using zipdetails."
  fi
fi

if [ "$EXTRACTION_DONE" = false ]; then
  echo "Error: Could not extract the repository with available tools."
  exit 1
fi

# Check for the extracted directory
if [ ! -d "$REPO_DIR" ]; then
  echo "Looking for alternate directory names..."
  # Find any directory that might match the expected repository
  for dir in */; do
    if [[ "$dir" == *"photos_heatmap_viewer"* ]]; then
      REPO_DIR="${dir%/}"
      echo "Found repository directory: $REPO_DIR"
      break
    fi
  done
  
  if [ -z "$REPO_DIR" ]; then
    echo "Error: Failed to extract the repository or repository directory not found."
    ls -la
    exit 1
  fi
fi

# Navigate to repository directory
cd "$REPO_DIR"
echo "Working directory: $(pwd)"

# Check if Dockerfile exists in the repository
if [ ! -f "Dockerfile" ]; then
  echo "Error: Dockerfile not found in the repository."
  exit 1
fi

echo "Stopping and removing any existing containers..."
docker ps -aqf "name=photo-heatmap" | xargs -r docker kill 2>/dev/null || true
docker ps -aqf "name=photo-heatmap" | xargs -r docker rm 2>/dev/null || true

# Verify static files before build
echo "Verifying static files before build..."
if [ -d "static/js" ]; then
  JS_COUNT=$(find static/js -name "*.js" | wc -l)
  echo "Found $JS_COUNT JavaScript files in static/js directory"
  echo "JavaScript files: $(find static/js -name "*.js" -exec basename {} \; | tr '\n' ' ')"
else
  echo "Warning: static/js directory not found!"
  mkdir -p static/js
fi

# Build the image
echo "Building Docker image..."
docker build --no-cache -t photo-heatmap .

# Run the container
echo "Starting the container..."
docker run -d \
  -p 8088:8000 \
  -v /volume1/docker/photo-heatmap/data:/app/data \
  -v /volume1/docker/photo-heatmap/logs:/app/logs \
  -v /volume1/homes/fernando/Photos:/photos/fernando:ro \
  -v /volume1/homes/shizue/Photos:/photos/shizue:ro \
  --name photo-heatmap \
  photo-heatmap:latest

# Verify that JS files were included in the container
echo "Verifying container setup..."
CONTAINER_ID=$(docker ps -q -f "name=photo-heatmap")
if [ -n "$CONTAINER_ID" ]; then
  echo "Container is running with ID: $CONTAINER_ID"
  
  # Check if static/js files are included in the container
  JS_FILES_IN_CONTAINER=$(docker exec $CONTAINER_ID ls -la /app/static/js 2>/dev/null | grep -c "\.js")
  if [ "$JS_FILES_IN_CONTAINER" -gt 0 ]; then
    echo "✅ JavaScript files were successfully included in the container"
    echo "Found files: $(docker exec $CONTAINER_ID ls -la /app/static/js | grep "\.js" | awk '{print $NF}' | tr '\n' ' ')"
  else
    echo "❌ ERROR: JavaScript files were not found in the container!"
    echo "Container directory structure:"
    docker exec $CONTAINER_ID find /app/static -type f | sort
  fi
else
  echo "❌ ERROR: Container not running!"
fi

echo "Done! Your photo-heatmap service is running at http://localhost:8088"
echo "To view logs: docker logs photo-heatmap"
echo "To stop: docker stop photo-heatmap"