# Create an empty JSON file if needed
Write-Host "Checking for photo_heatmap_data.json..."
if (-not (Test-Path -Path "photo_heatmap_data.json")) {
    Write-Host "Creating empty JSON file..." -ForegroundColor Yellow
    "[]" | Out-File -FilePath "photo_heatmap_data.json" -Encoding utf8
    Write-Host "Empty JSON file created." -ForegroundColor Green
} else {
    Write-Host "JSON file exists." -ForegroundColor Green
    
    # Check if it's empty or invalid
    try {
        $content = Get-Content -Path "photo_heatmap_data.json" -Raw
        if ([string]::IsNullOrWhiteSpace($content)) {
            Write-Host "JSON file is empty. Creating valid JSON array..." -ForegroundColor Yellow
            "[]" | Out-File -FilePath "photo_heatmap_data.json" -Encoding utf8 -Force
            Write-Host "Valid JSON array created." -ForegroundColor Green
        } else {
            # Try parsing the JSON
            try {
                $null = $content | ConvertFrom-Json
                Write-Host "JSON file exists and appears to be valid." -ForegroundColor Green
            } catch {
                Write-Host "JSON file exists but contains invalid JSON. Creating valid JSON array..." -ForegroundColor Yellow
                "[]" | Out-File -FilePath "photo_heatmap_data.json" -Encoding utf8 -Force
                Write-Host "Valid JSON array created." -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "Error checking JSON file: $_" -ForegroundColor Red
    }
}

# Now create a temporary fixed index.html without the duplicate identifier issue
Write-Host "Creating temporary index_fixed.html without duplicate identifier issues..." -ForegroundColor Cyan

# Get content of the original file
$content = Get-Content -Path "index.html" -Raw

# Replace hidePhotoViewer with closePhotoViewer
$content = $content -replace "closePhotoViewer\.addEventListener\('click', hidePhotoViewer\)", "closePhotoViewerBtn.addEventListener('click', closePhotoViewer)"
$content = $content -replace "const closePhotoViewer = document\.getElementById\('closePhotoViewer'\)", "const closePhotoViewerBtn = document.getElementById('closePhotoViewer')"
$content = $content -replace "function hidePhotoViewer\(\)", "function closePhotoViewer()"
$content = $content -replace "hidePhotoViewer\(\)", "closePhotoViewer()"

# Write to a new file
$content | Out-File -FilePath "index_fixed.html" -Encoding utf8

Write-Host "Fixed index_fixed.html created." -ForegroundColor Green
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "To use the fixed version, please follow these steps:" -ForegroundColor Yellow
Write-Host "1. Stop the current web server (press Ctrl+C in its terminal)" -ForegroundColor Yellow
Write-Host "2. Rename index_fixed.html to index.html:" -ForegroundColor Yellow
Write-Host "   Remove-Item -Path index.html -Force" -ForegroundColor White
Write-Host "   Rename-Item -Path index_fixed.html -NewName index.html" -ForegroundColor White
Write-Host "3. Start the server again:" -ForegroundColor Yellow
Write-Host "   python server.py" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
