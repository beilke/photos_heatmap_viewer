# PowerShell script to debug photo heatmap viewer
Write-Host "This script will help diagnose and fix issues with the Photo Heatmap Viewer." -ForegroundColor Cyan
Write-Host ""

# Check if server is running
$serverRunning = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($serverRunning) {
    Write-Host "Server is running on port 8000. Stopping it first..." -ForegroundColor Yellow
    foreach ($process in $serverRunning) {
        $pid = $process.OwningProcess
        Stop-Process -Id $pid -Force
        Write-Host "Stopped process with PID $pid"
    }
}

Write-Host "Inspecting JSON data file..." -ForegroundColor Cyan
python inspect_json.py

$fixJson = Read-Host "Would you like to fix the JSON file if there are issues? (y/n)"
if ($fixJson -eq "y") {
    Write-Host "Attempting to fix JSON file..." -ForegroundColor Yellow
    python inspect_json.py --fix
}

Write-Host ""
Write-Host "Starting server with debug mode enabled..." -ForegroundColor Green
Start-Process python -ArgumentList "server.py --debug" -NoNewWindow

Write-Host ""
Write-Host "Open http://localhost:8000 in your browser to view the photo heatmap." -ForegroundColor Cyan
Write-Host "Press Ctrl+C in this window to stop the server when done." -ForegroundColor Yellow
