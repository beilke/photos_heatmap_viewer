# Run the photo heatmap viewer server with HEIC support
Write-Host "Starting photo heatmap viewer with HEIC support..."

# Stop any existing Python processes
Write-Host "Stopping any existing Python servers..."
Stop-Process -Name python -ErrorAction SilentlyContinue

# Start server with debug enabled
Write-Host "Starting server with debug mode..."
Start-Process -FilePath "python" -ArgumentList "server.py", "--debug" -NoNewWindow

Write-Host "Server started! Open http://localhost:8000 in your browser."
Write-Host "HEIC files should now be properly processed and displayed."
Write-Host "Press Ctrl+C in the terminal window to stop the server."
