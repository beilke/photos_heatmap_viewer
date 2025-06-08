#!/bin/bash
# Setup script for Photo Heatmap Viewer Docker environment

# Create required directories
mkdir -p ./data ./logs ./photos/{library1,library2}

echo "Created directory structure:"
echo "  ./data - For database and output files"
echo "  ./logs - For application logs"
echo "  ./photos - Root directory for photo libraries"
echo "    ./photos/library1 - First photo library"
echo "    ./photos/library2 - Second photo library"

# Create .env file for Docker Compose from template
cp setup.env .env
# Update photos path to absolute path
sed -i "s|PHOTOS_ROOT_DIR=./photos|PHOTOS_ROOT_DIR=$(pwd)/photos|g" .env
echo "Created .env file with environment settings"

# Check for requirements.txt
if [ ! -f "requirements.txt" ]; then
  echo "Creating requirements.txt file..."
  cat > requirements.txt <<EOL
Flask>=2.0.0
Pillow>=8.0.0
piexif>=1.1.3
exifread>=2.3.2
pillow-heif>=0.5.0
psutil>=5.9.0
EOL
  echo "Created requirements.txt with necessary dependencies"
fi

echo ""
echo "Setup complete! You can now run the application with:"
echo "  docker-compose up -d"
echo ""
echo "To run with the photo processor service:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.processor.yml up -d"
echo ""
echo "To process a specific library manually:"
echo "  docker exec photo-heatmap-photo-processor-1 /app/process_library.sh /photos/your_library \"Your Library Name\""
echo ""
echo "The application will be available at: http://localhost:8000"
