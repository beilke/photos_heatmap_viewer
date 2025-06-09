# Clean Data Script
# This script cleans the photo database and JSON data file
# Use with caution as it will delete all library and photo data

param (
    [switch]$Force = $false,
    [switch]$KeepBackups = $false
)

# Define paths - looking in data directory first, then fallback to root
$dataDir = Join-Path (Get-Location) "data"
$dbPathInData = Join-Path $dataDir "photo_library.db" 
$dbPathInRoot = "photo_library.db"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Check if database exists in either location
$dbInDataExists = Test-Path $dbPathInData
$dbInRootExists = Test-Path $dbPathInRoot

# Determine which path to use
if ($dbInDataExists) {
    $dbPath = $dbPathInData
    $dbExists = $true
} elseif ($dbInRootExists) {
    $dbPath = $dbPathInRoot
    $dbExists = $true
} else {
    $dbExists = $false
    $dbPath = $dbPathInData  # Default to data directory for new DB
}

if (-not $dbExists) {
    Write-Host "No database found. Nothing to clean." -ForegroundColor Yellow
    exit 0
}

# Prompt for confirmation unless Force is used
if (-not $Force) {
    Write-Host "WARNING: This will delete all your library and photo data!" -ForegroundColor Red
    Write-Host "Database file: $dbPath ($(if ($dbExists) {"exists"} else {"not found"}))" -ForegroundColor Yellow
    
    $confirmation = Read-Host "Are you sure you want to proceed? (y/n)"
    if ($confirmation -ne "y") {
        Write-Host "Operation cancelled." -ForegroundColor Cyan
        exit 0
    }
}

# Create backup directory if it doesn't exist
$backupDir = Join-Path (Get-Location) "backups"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

# Create backup if database exists
if ($dbExists) {
    $dbBackupName = "photo_library.db.backup_${timestamp}"
    $dbBackup = Join-Path $backupDir $dbBackupName
    Write-Host "Creating database backup: $dbBackup" -ForegroundColor Cyan
    Copy-Item -Path $dbPath -Destination $dbBackup -Force
}

# Remove the legacy timestamp text files
$updateFiles = Get-ChildItem -Path $dataDir -Filter "last_update_*.txt" -ErrorAction SilentlyContinue
if ($updateFiles) {
    Write-Host "Removing legacy timestamp files..." -ForegroundColor Cyan
    $updateFiles | ForEach-Object {
        Remove-Item -Path $_.FullName -Force
        Write-Host "  Removed $($_.Name)" -ForegroundColor Gray
    }
    Write-Host "Legacy timestamp files removed." -ForegroundColor Green
}

# Remove the database file
if ($dbExists) {
    Remove-Item -Path $dbPath -Force
    Write-Host "Database file removed." -ForegroundColor Green
}

# Ensure the data directory exists
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
    Write-Host "Created data directory: $dataDir" -ForegroundColor Cyan
}

# Initialize a new empty database
Write-Host "Initializing new database..." -ForegroundColor Cyan
python init_db.py --db $dbPath
Write-Host "New empty database created at: $dbPath" -ForegroundColor Green

# Clean up backups if not keeping them
if (-not $KeepBackups) {
    if ($dbExists) {
        Remove-Item -Path $dbBackup -Force
    }
    Write-Host "Backup files removed." -ForegroundColor Cyan
} else {
    Write-Host "Backup files kept at:" -ForegroundColor Yellow
    if ($dbExists) {
        Write-Host "  - $dbBackup" -ForegroundColor Yellow
    }
}

Write-Host "Cleaning complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To rebuild your library:" -ForegroundColor Cyan
Write-Host "  1. Use manage_libraries.ps1 to create a new library" -ForegroundColor Cyan
Write-Host "  2. Process photos with process_photos.py" -ForegroundColor Cyan
Write-Host "  3. Restart the server" -ForegroundColor Cyan
