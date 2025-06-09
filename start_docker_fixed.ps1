#!/usr/bin/env pwsh

Write-Host "Building and running the photo heatmap viewer Docker container" -ForegroundColor Green

# Step 0: Stop and remove any existing containers
Write-Host "Stopping and removing any existing containers..." -ForegroundColor Yellow
docker stop photo-heatmap 2>$null
docker rm photo-heatmap 2>$null

# Step 1: Apply Docker file patch if needed
Write-Host "Patching Dockerfile for proper HTML file handling..." -ForegroundColor Cyan
if (Test-Path -Path "./patch_docker.sh") {
    bash ./patch_docker.sh
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to patch Dockerfile. Continuing with existing Dockerfile..." -ForegroundColor Yellow
    }
}

# Step 2: Build the Docker image with no cache to ensure fresh build
Write-Host "Building Docker image..." -ForegroundColor Cyan
docker build --no-cache -t photo-heatmap:latest .

# Check if the build was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed. Please check the errors above." -ForegroundColor Red
    exit 1
}

# Step 3: Run the Docker container
Write-Host "Starting Docker container..." -ForegroundColor Cyan
$photoFolder = Read-Host "Enter the full path to your photos folder (or press Enter to skip mounting)"

if ($photoFolder -and (Test-Path -Path $photoFolder)) {
    Write-Host "Mounting photos folder: $photoFolder" -ForegroundColor Green
    docker run -d -p 8000:8000 `
        -v "${PWD}/data:/app/data" `
        -v "$photoFolder:/photos:ro" `
        --name photo-heatmap `
        photo-heatmap:latest
} else {
    Write-Host "Running without photos folder mount" -ForegroundColor Yellow
    docker run -d -p 8000:8000 `
        -v "${PWD}/data:/app/data" `
        --name photo-heatmap `
        photo-heatmap:latest
}

# Step 4: Show container logs
Write-Host "Container started. Showing logs:" -ForegroundColor Green
docker logs -f photo-heatmap

Write-Host "Docker container is now running. Access the application at http://localhost:8000" -ForegroundColor Green
