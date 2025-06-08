# Debug Test Script for Library Updates Panel (PowerShell)
# This script creates test update files and starts the Flask server with debug logging

Write-Host "========= DEBUG TEST FOR LIBRARY UPDATES DISPLAY =========" -ForegroundColor Yellow

# Create data directory if it doesn't exist
if (-not (Test-Path -Path "data")) {
    New-Item -ItemType Directory -Path "data"
}
Write-Host "Data directory created/confirmed at $(Get-Location)\data"

# Create some test library update files with clear debug markers
$currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$hourAgo = (Get-Date).AddHours(-1).ToString("yyyy-MM-dd HH:mm:ss")
$dayAgo = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd HH:mm:ss")

Set-Content -Path ".\data\last_update_Debug_Library_1.txt" -Value "$currentTime [TEST FILE 1]"
Set-Content -Path ".\data\last_update_Debug_Library_2.txt" -Value "$hourAgo [TEST FILE 2]"
Set-Content -Path ".\data\last_update_Debug_Library_3.txt" -Value "$dayAgo [TEST FILE 3]"

Write-Host "Created test update files:" -ForegroundColor Cyan
Get-ChildItem -Path ".\data\last_update_*.txt" | Format-Table Name, Length, LastWriteTime

# Run the server with debug mode enabled
Write-Host "Starting Flask server with debug output..." -ForegroundColor Green
Write-Host "Please access http://localhost:8000 in your browser" -ForegroundColor Cyan
Write-Host "You should see a RED panel in the bottom right with debug information" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Yellow

# Start the server
python server.py --port 8000 --dir . --debug
