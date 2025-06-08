# Test script for Windows PowerShell
# Demonstrates the library update times feature

# Create data directory if it doesn't exist
if (-not (Test-Path -Path "data")) {
    New-Item -ItemType Directory -Path "data"
}

# Create some test library update files
$currentTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$hourAgo = (Get-Date).AddHours(-1).ToString("yyyy-MM-dd HH:mm:ss")
$dayAgo = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd HH:mm:ss")

Set-Content -Path ".\data\last_update_Test_Library_1.txt" -Value $currentTime
Set-Content -Path ".\data\last_update_Test_Library_2.txt" -Value $hourAgo
Set-Content -Path ".\data\last_update_Test_Library_3.txt" -Value $dayAgo

# Run the server with Flask
Write-Host "Starting server with library update times display enabled..."
Write-Host "Open http://localhost:8000 in your browser to see the update times"
python server.py --port 8000 --dir . --debug
