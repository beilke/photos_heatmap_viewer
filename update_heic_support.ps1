# Update script to add HEIC file support
Write-Host "Installing HEIC file support for photo processing..."

# Install pillow-heif package
pip install pillow-heif

Write-Host "Installation complete! You can now process HEIC files."

# Optional: Reprocess the photos if needed
$processNow = Read-Host "Do you want to reprocess your photo libraries now? (y/n)"
if ($processNow -eq "y") {
    Write-Host "Reprocessing photos..."
    # Check if any libraries exist first
    $libraries = python -c "import sqlite3; conn = sqlite3.connect('photo_library.db'); cursor = conn.cursor(); cursor.execute('SELECT id, name FROM libraries'); libraries = cursor.fetchall(); conn.close(); print(len(libraries))"
    if ($libraries -gt 0) {
        # Export all libraries to update the data with HEIC support
        python process_photos.py --export --export-all
        Write-Host "Libraries reprocessed with HEIC support"
    } else {
        Write-Host "No libraries found to reprocess. Add libraries first using manage_libraries.ps1"
    }
}

Write-Host "Update complete. You may need to restart your server if it's currently running."
$restart = Read-Host "Restart server now? (y/n)"
if ($restart -eq "y") {
    Write-Host "Stopping any running Python servers..."
    Stop-Process -Name python -ErrorAction SilentlyContinue
    Write-Host "Starting server..."
    Start-Process -FilePath "python" -ArgumentList "server.py", "--debug" -NoNewWindow
    Write-Host "Server restarted with HEIC support enabled."
}
