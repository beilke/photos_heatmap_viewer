#!/bin/bash

docker kill $(docker ps -aqf "name=photo-heatmap")
docker rm $(docker ps -aqf "name=photo-heatmap")

# Build the image (lowercase name)
docker build --no-cache -t photo-heatmap .

# Run the container
docker run -d \
  -p 8088:8000 \
  -v /volume1/docker/photo-heatmap/data:/app/data \
  -v /volume1/docker/photo-heatmap/logs:/app/logs \
  -v /volume1/homes/fernando/Photos:/photos/fernando:ro \
  -v /volume1/homes/shizue/Photos:/photos/shizue:ro \
  --name photo-heatmap \
  photo-heatmap:latest