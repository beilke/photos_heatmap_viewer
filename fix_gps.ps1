# This script helps diagnose GPS extraction issues

Write-Host "GPS Extraction Diagnostic Tool" -ForegroundColor Cyan

# Ensure we have the required Python packages installed
Write-Host "Checking for required packages..." -ForegroundColor Yellow
Write-Host "Running: pip install Pillow pillow-heif"
python -m pip install Pillow pillow-heif

# Check if the user provided a photo path
if ($args.Count -eq 0) {
    # Try to find a photo in the default directory
    Write-Host "No photo path provided, checking default directories..." -ForegroundColor Yellow
    $possibleDirs = @("D:\photogps", "..\photogps", ".\photogps")
    $testPhoto = $null
    
    foreach ($dir in $possibleDirs) {
        if (Test-Path $dir) {
            $photos = Get-ChildItem -Path $dir -Filter *.jpg -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($photos) {
                $testPhoto = $photos[0].FullName
                Write-Host "Found photo: $testPhoto" -ForegroundColor Green
                break
            }
        }
    }
    
    if (-not $testPhoto) {
        Write-Host "No photos found in default directories. Please provide a path to a photo:" -ForegroundColor Red
        $testPhoto = Read-Host "Enter path to photo (e.g., D:\photos\myphoto.jpg)"
    }
} else {
    $testPhoto = $args[0]
}

# Verify the photo exists
if (-not (Test-Path $testPhoto)) {
    Write-Host "Error: Photo not found at path: $testPhoto" -ForegroundColor Red
    exit 1
}

# Run the GPS extraction test
Write-Host "`nRunning GPS extraction test on: $testPhoto" -ForegroundColor Green
python test_gps_extraction.py "$testPhoto"

Write-Host "`n===== NEXT STEPS =====`n" -ForegroundColor Cyan
Write-Host "If the test shows GPS coordinates, but they're not showing up in your map:"
Write-Host "1. Run a full rebuild of your photo database:"
Write-Host "   python process_photos.py --clean" -ForegroundColor Yellow
Write-Host "   python process_photos.py --process 'D:\photogps' --library 'Fernando'" -ForegroundColor Yellow
Write-Host "   python process_photos.py --export" -ForegroundColor Yellow
Write-Host "`n2. Check your server configuration to ensure it's correctly serving the API endpoint."
Write-Host "3. Verify that your browser isn't caching old data (try Ctrl+F5 to force reload)."
