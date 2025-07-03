#!/bin/bash
# Script to build and publish the Photo Heatmap Viewer image to DockerHub

# Configuration
DOCKERHUB_USERNAME="fbeilke"  # Your DockerHub username
IMAGE_NAME="photo-heatmap-viewer"
VERSION="1.0.0"  # Initial version

# Check Docker status
echo "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running or not accessible"
  exit 1
fi

# Check login status and attempt login if necessary
echo "Checking DockerHub login status..."
if ! docker info | grep -q "Username"; then
  echo "Not logged in to DockerHub. Attempting login..."
  
  # Prompt for username and password
  read -p "DockerHub Username: " DOCKER_USERNAME
  read -s -p "DockerHub Password: " DOCKER_PASSWORD
  echo
  
  # Try to login
  if ! echo "$DOCKER_PASSWORD" | docker login --username "$DOCKER_USERNAME" --password-stdin; then
    echo "Login failed. Please check your credentials and try again."
    exit 1
  fi
  echo "Login successful!"
else
  echo "Already logged in to DockerHub."
fi

# Stop and remove any existing container
echo "Cleaning up existing containers..."
docker kill $(docker ps -aqf "name=$IMAGE_NAME") 2>/dev/null || true
docker rm $(docker ps -aqf "name=$IMAGE_NAME") 2>/dev/null || true

# Create a dedicated Dockerfile for publishing
cat > Dockerfile.dockerhub <<EOF
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    libheif-dev \\
    tini \\
    curl \\
    cron \\
    procps && \\
    apt-get clean && \\
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py /app/
COPY index.html /app/
COPY static /app/static/

# Copy the process_libraries.sh script
COPY process_libraries.sh /app/

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs && chmod +x /app/process_libraries.sh

# Set environment variables
ENV PORT=8000 \\
    HOST="0.0.0.0" \\
    DEBUG="0" \\
    UPDATE_INTERVAL="0 */6 * * *"

# Expose the port
EXPOSE 8000

# Create healthcheck script
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/health || exit 1' > /app/healthcheck.sh && chmod +x /app/healthcheck.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
  CMD /app/healthcheck.sh

# Define volumes for persistent data
VOLUME ["/app/data", "/app/logs"]

# Use tini as init
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the server
CMD ["python", "server.py", "--port", "8000", "--host", "0.0.0.0"]
EOF

# Build the image without using cache
echo "Building Docker image..."
docker build --no-cache -f Dockerfile.dockerhub -t $IMAGE_NAME:latest .

# Tag the image with version and latest
echo "Tagging images..."
docker tag $IMAGE_NAME:latest $DOCKERHUB_USERNAME/$IMAGE_NAME:$VERSION
docker tag $IMAGE_NAME:latest $DOCKERHUB_USERNAME/$IMAGE_NAME:latest

# Push to DockerHub
echo "Pushing to DockerHub..."
docker push $DOCKERHUB_USERNAME/$IMAGE_NAME:$VERSION
docker push $DOCKERHUB_USERNAME/$IMAGE_NAME:latest

echo "Successfully pushed $DOCKERHUB_USERNAME/$IMAGE_NAME:$VERSION to DockerHub"
echo "Also pushed as $DOCKERHUB_USERNAME/$IMAGE_NAME:latest"
echo ""
echo "Users can pull your image with:"
echo "docker pull $DOCKERHUB_USERNAME/$IMAGE_NAME:latest"
echo ""
echo "To run the container:"
echo "docker run -d --name photo-heatmap-viewer \\"
echo "  -p 8000:8000 \\"
echo "  -v /path/to/photos:/photos \\"
echo "  -v /path/to/data:/app/data \\"
echo "  -v /path/to/logs:/app/logs \\"
echo "  $DOCKERHUB_USERNAME/$IMAGE_NAME:latest"
