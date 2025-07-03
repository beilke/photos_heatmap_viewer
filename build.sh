#!/bin/bash
# Script to build the photo-heatmap Docker image with all fixes incorporated

echo "Building photo-heatmap Docker image with all cron fixes..."

# Build the image
docker build -t photo-heatmap:latest .

# Tag with today's date for versioning
DATE_TAG=$(date +%Y%m%d)
docker tag photo-heatmap:latest photo-heatmap:$DATE_TAG

echo "Build complete. Images created:"
echo "- photo-heatmap:latest"
echo "- photo-heatmap:$DATE_TAG"

# Optionally push to Docker Hub if credentials are provided
if [ "$1" == "--push" ]; then
  DOCKER_HUB_USER=${2:-yourusername}
  echo "Pushing to Docker Hub as $DOCKER_HUB_USER/photo-heatmap..."
  docker tag photo-heatmap:latest $DOCKER_HUB_USER/photo-heatmap:latest
  docker tag photo-heatmap:latest $DOCKER_HUB_USER/photo-heatmap:$DATE_TAG
  docker push $DOCKER_HUB_USER/photo-heatmap:latest
  docker push $DOCKER_HUB_USER/photo-heatmap:$DATE_TAG
  echo "Push complete."
fi

echo ""
echo "To run the container:"
echo "docker-compose up -d"
echo ""
echo "To check logs:"
echo "docker exec photo-heatmap-processor cat /app/logs/cron_test.log"
