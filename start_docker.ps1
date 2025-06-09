#!/usr/bin/env pwsh

Write-Host "Building and running the photo heatmap viewer Docker container" -ForegroundColor Green

# Step 1: Build the Docker image
Write-Host "Building Docker image..." -ForegroundColor Cyan
docker build -t photo-heatmap:latest .

# Check if the build was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed. Please check the errors above." -ForegroundColor Red
    exit 1
}

# Step 2: Run the Docker container
Write-Host "Starting Docker container..." -ForegroundColor Cyan
docker-compose up -d

Write-Host "Docker container is now running. Access the application at http://localhost:8000" -ForegroundColor Green
