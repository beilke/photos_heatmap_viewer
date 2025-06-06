# Clean Data Script
# This script cleans the photo database and JSON data file
# Use with caution as it will delete all library and photo data

param (
    [switch]$Force = $false,
    [switch]$KeepBackups = $false
)

$dbPath = "photo_library.db"
$jsonPath = "photo_heatmap_data.json"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Check if files exist
$dbExists = Test-Path $dbPath
$jsonExists = Test-Path $jsonPath

if (-not $dbExists -and -not $jsonExists) {
    Write-Host "No database or JSON file found. Nothing to clean." -ForegroundColor Yellow
    exit 0
}

# Prompt for confirmation unless Force is used
if (-not $Force) {
    Write-Host "WARNING: This will delete all your library and photo data!" -ForegroundColor Red
    Write-Host "Database file: $dbPath ($(if ($dbExists) {"exists"} else {"not found"}))" -ForegroundColor Yellow
    Write-Host "JSON data file: $jsonPath ($(if ($jsonExists) {"exists"} else {"not found"}))" -ForegroundColor Yellow
    
    $confirmation = Read-Host "Are you sure you want to proceed? (y/n)"
    if ($confirmation -ne "y") {
        Write-Host "Operation cancelled." -ForegroundColor Cyan
        exit 0
    }
}

# Create backups if files exist
if ($dbExists) {
    $dbBackup = "${dbPath}.backup_${timestamp}"
    Write-Host "Creating database backup: $dbBackup" -ForegroundColor Cyan
    Copy-Item -Path $dbPath -Destination $dbBackup -Force
}

if ($jsonExists) {
    $jsonBackup = "${jsonPath}.backup_${timestamp}"
    Write-Host "Creating JSON backup: $jsonBackup" -ForegroundColor Cyan
    Copy-Item -Path $jsonPath -Destination $jsonBackup -Force
}

# Remove the original files
if ($dbExists) {
    Remove-Item -Path $dbPath -Force
    Write-Host "Database file removed." -ForegroundColor Green
}

if ($jsonExists) {
    Remove-Item -Path $jsonPath -Force
    Write-Host "JSON data file removed." -ForegroundColor Green
}

# Initialize a new empty database
Write-Host "Initializing new database..." -ForegroundColor Cyan
python init_db.py
Write-Host "New empty database created." -ForegroundColor Green

# Create empty JSON file
Write-Host "Creating empty JSON data file..." -ForegroundColor Cyan
@'
{
  "photos": [],
  "libraries": []
}
'@ | Out-File -FilePath $jsonPath -Encoding utf8
Write-Host "New empty JSON file created." -ForegroundColor Green

# Clean up backups if not keeping them
if (-not $KeepBackups) {
    if ($dbExists) {
        Remove-Item -Path $dbBackup -Force
    }
    if ($jsonExists) {
        Remove-Item -Path $jsonBackup -Force
    }
    Write-Host "Backup files removed." -ForegroundColor Cyan
} else {
    Write-Host "Backup files kept at:" -ForegroundColor Yellow
    if ($dbExists) {
        Write-Host "  - $dbBackup" -ForegroundColor Yellow
    }
    if ($jsonExists) {
        Write-Host "  - $jsonBackup" -ForegroundColor Yellow
    }
}

Write-Host "Cleaning complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To rebuild your library:" -ForegroundColor Cyan
Write-Host "  1. Use manage_libraries.ps1 to create a new library" -ForegroundColor Cyan
Write-Host "  2. Process photos with process_photos.py" -ForegroundColor Cyan
Write-Host "  3. Export data with process_photos.py --export" -ForegroundColor Cyan
Write-Host "  4. Restart the server" -ForegroundColor Cyan
