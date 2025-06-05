# Quick Start Demo for Multiple Libraries
# This script demonstrates how to create and manage multiple libraries
# Run this script to set up a sample environment with multiple libraries

# Initialize the database with our new schema
python init_db.py

# Create two demo libraries
Write-Host "Creating 'Vacation' library..."
.\manage_libraries.ps1 create "Vacation" ".\sample_photos\vacation" -description "Vacation photos from various trips"

Write-Host "Creating 'Family' library..."
.\manage_libraries.ps1 create "Family" ".\sample_photos\family" -description "Family photos and events"

# List all libraries
.\manage_libraries.ps1 list

# Export the data
.\manage_libraries.ps1 export

# Start the server
Write-Host ""
Write-Host "Starting server - Press Ctrl+C to stop"
Write-Host "Open http://localhost:8000 in your browser"
python server.py
