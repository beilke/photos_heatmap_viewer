#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Master fix script for the Photo Heatmap Viewer Docker issues.
.DESCRIPTION
    This script diagnoses and fixes Docker-related issues in the Photo Heatmap Viewer application.
    It checks for common issues and applies fixes to ensure the application runs correctly in Docker.
#>

Write-Host "Photo Heatmap Viewer - Docker Fix Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Step 1: Check if required files exist
Write-Host "`nChecking for required files..." -ForegroundColor Yellow
$requiredFiles = @("index.html", "server.py", "Dockerfile")
$missingFiles = @()

foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $missingFiles += $file
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host "Warning: Missing required files: $($missingFiles -join ', ')" -ForegroundColor Red
} else {
    Write-Host "All required files are present." -ForegroundColor Green
}

# Step 2: Check for Docker
Write-Host "`nChecking Docker installation..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version
    Write-Host "Docker is installed: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Docker is not installed or not in PATH. Please install Docker first." -ForegroundColor Red
    exit 1
}

# Step 3: Apply patches to fix Docker issues
Write-Host "`nApplying fixes for Docker environment..." -ForegroundColor Yellow

# Patch server.py for proper file handling
if (Test-Path "patch_server.py") {
    Write-Host "Patching server.py for proper file handling..." -ForegroundColor Cyan
    python patch_server.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to patch server.py. Manual fix might be needed." -ForegroundColor Yellow
    } else {
        Write-Host "Server.py patched successfully." -ForegroundColor Green
    }
}

# Ensure index.html is in the correct location
if (Test-Path "index.html" -and (Test-Path "templates")) {
    Write-Host "Copying index.html to templates directory..." -ForegroundColor Cyan
    Copy-Item -Path "index.html" -Destination "templates/" -Force
}

# Fix Docker file
if (Test-Path "patch_docker.sh") {
    Write-Host "Patching Dockerfile..." -ForegroundColor Cyan
    bash ./patch_docker.sh
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to patch Dockerfile." -ForegroundColor Yellow
    } else {
        Write-Host "Dockerfile patched successfully." -ForegroundColor Green
    }
}

# Step 4: Create data directory if it doesn't exist
if (-not (Test-Path "data")) {
    Write-Host "`nCreating data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "data" | Out-Null
    Write-Host "Data directory created." -ForegroundColor Green
}

# Step 5: Check for database file
if (-not (Test-Path "data/photo_library.db")) {
    Write-Host "`nWarning: Database file not found in data directory." -ForegroundColor Yellow
    $initDb = Read-Host "Do you want to initialize a new database? (y/n)"
    if ($initDb -eq "y") {
        Write-Host "Initializing database..." -ForegroundColor Cyan
        python init_db.py --db data/photo_library.db
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: Failed to initialize database." -ForegroundColor Red
        } else {
            Write-Host "Database initialized." -ForegroundColor Green
        }
    }
} else {
    Write-Host "`nDatabase file exists." -ForegroundColor Green
}

# Step 6: Rebuild and run Docker container
$rebuild = Read-Host "`nDo you want to rebuild and run the Docker container now? (y/n)"
if ($rebuild -eq "y") {
    # Using our improved script
    if (Test-Path "start_docker_fixed.ps1") {
        Write-Host "Running improved Docker start script..." -ForegroundColor Cyan
        pwsh -File start_docker_fixed.ps1
    } else {
        Write-Host "Running original Docker start script..." -ForegroundColor Cyan
        pwsh -File start_docker.ps1
    }
} else {
    Write-Host "`nSkipping Docker rebuild. Run start_docker_fixed.ps1 manually when ready." -ForegroundColor Yellow
}

Write-Host "`nFix script completed. The application should now work correctly in Docker." -ForegroundColor Green
Write-Host "If you still experience issues, check the server logs with: docker logs photo-heatmap" -ForegroundColor Cyan
