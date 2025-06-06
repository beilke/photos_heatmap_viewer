# Fix JSON Script
# This script rebuilds the JSON file from the database

Write-Host "Fixing JSON file issues..." -ForegroundColor Cyan

# Check if the database exists
if (-not (Test-Path "photo_library.db")) {
    Write-Host "Database not found. Cannot rebuild JSON." -ForegroundColor Red
    exit 1
}

# Backup the existing JSON file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$jsonPath = "photo_heatmap_data.json"
if (Test-Path $jsonPath) {
    $backupPath = "${jsonPath}.backup_${timestamp}"
    Write-Host "Creating backup of existing JSON file: $backupPath" -ForegroundColor Yellow
    Copy-Item -Path $jsonPath -Destination $backupPath -Force
    
    # Remove the problematic JSON file
    Remove-Item -Path $jsonPath -Force
    Write-Host "Removed problematic JSON file." -ForegroundColor Green
}

# Run the export process
Write-Host "Rebuilding JSON file from database..." -ForegroundColor Cyan
python process_photos.py --export

# Verify the new JSON file
if (Test-Path $jsonPath) {
    $size = (Get-Item $jsonPath).Length
    Write-Host "New JSON file created successfully (Size: ${size} bytes)." -ForegroundColor Green
    
    # Test the JSON parsing
    try {
        $content = Get-Content $jsonPath -Raw
        $json = ConvertFrom-Json $content -ErrorAction Stop
        $photoCount = $json.photos.Count
        $libraryCount = $json.libraries.Count
        Write-Host "JSON validation successful: Contains $photoCount photos in $libraryCount libraries." -ForegroundColor Green
    }
    catch {
        Write-Host "Warning: The JSON file was created but contains parsing errors:" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
} else {
    Write-Host "Failed to create new JSON file." -ForegroundColor Red
}

Write-Host ""
Write-Host "Fix completed. You may need to restart the server for changes to take effect." -ForegroundColor Cyan
$restart = Read-Host "Do you want to restart the server now? (y/n)"
if ($restart -eq "y") {
    # Stop any running Python processes
    Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "Starting server..." -ForegroundColor Cyan
    Start-Process -FilePath "python" -ArgumentList "server.py", "--debug"
    Write-Host "Server started. You can access it at http://localhost:8000" -ForegroundColor Green
}
