#!/bin/bash
# Script to process photos inside a Docker container
# Usage: ./process_in_docker.sh <library_folder> <library_name> [container_name]

# Check if arguments are provided
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <library_folder> <library_name> [container_name]"
    echo "Example: $0 Fernando \"Fernando's Photos\" photo-heatmap-viewer"
    exit 1
fi

LIBRARY_FOLDER=$1
LIBRARY_NAME=$2
CONTAINER_NAME=${3:-photo-heatmap-viewer}  # Default to photo-heatmap-viewer if not specified

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi

# Check if the container exists and is running
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "Container '$CONTAINER_NAME' is not running"
    
    # Check if it exists but is not running
    if docker ps -a | grep -q $CONTAINER_NAME; then
        echo "Container exists but is not running. Starting it..."
        docker start $CONTAINER_NAME
        sleep 2  # Give it time to start
    else
        echo "Container does not exist. Please run it first with docker-compose up"
        exit 1
    fi
fi

# List directories in the container's /photos volume
echo "Available directories in the container's /photos volume:"
docker exec $CONTAINER_NAME ls -la /photos

echo ""
echo "Processing photos from /photos/$LIBRARY_FOLDER for library: $LIBRARY_NAME"
echo "----------------------------------------------------------------"

# Run the processing command inside the container
docker exec $CONTAINER_NAME python /app/process_photos.py --process "/photos/$LIBRARY_FOLDER" --library "$LIBRARY_NAME" --db /app/data/photo_library.db

echo ""
echo "Processing complete. Check the container logs for more details."
