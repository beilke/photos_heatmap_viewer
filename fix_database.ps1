# Fix Database and JSON Files
# This script helps repair common issues with the photo database and JSON files

param (
    [switch]$FixMissingLibraries = $false,
    [switch]$SyncDbToJson = $false,
    [switch]$SyncJsonToDb = $false,
    [switch]$VerifyFiles = $false,
    [switch]$RemoveOrphans = $false
)

# Import required modules
Add-Type -AssemblyName System.Data.SQLite
Add-Type -AssemblyName System.Web.Extensions

# Check if any option is selected
if (-not ($FixMissingLibraries -or $SyncDbToJson -or $SyncJsonToDb -or $VerifyFiles -or $RemoveOrphans)) {
    Write-Host "Please specify at least one operation to perform:" -ForegroundColor Yellow
    Write-Host "  -FixMissingLibraries : Add missing libraries to the database" -ForegroundColor Yellow
    Write-Host "  -SyncDbToJson       : Synchronize JSON file from database" -ForegroundColor Yellow
    Write-Host "  -SyncJsonToDb       : Synchronize database from JSON file" -ForegroundColor Yellow
    Write-Host "  -VerifyFiles        : Verify all photo files exist" -ForegroundColor Yellow
    Write-Host "  -RemoveOrphans      : Remove photos without valid files" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Example: .\fix_database.ps1 -FixMissingLibraries -SyncDbToJson" -ForegroundColor Cyan
    exit 0
}

# File paths
$dbPath = "photo_library.db"
$jsonPath = "photo_heatmap_data.json"

# Check if files exist
$dbExists = Test-Path $dbPath
$jsonExists = Test-Path $jsonPath

if (-not $dbExists) {
    Write-Host "Database file not found: $dbPath" -ForegroundColor Red
    Write-Host "Run init_db.py to create a new database." -ForegroundColor Yellow
    exit 1
}

if (-not $jsonExists) {
    Write-Host "JSON file not found: $jsonPath" -ForegroundColor Red
    Write-Host "Run process_photos.py --export to create the JSON file." -ForegroundColor Yellow
    exit 1
}

# Function to connect to the database
function Get-DbConnection {
    $conn = New-Object System.Data.SQLite.SQLiteConnection
    $conn.ConnectionString = "Data Source=$dbPath;Version=3;"
    $conn.Open()
    return $conn
}

# Fix missing libraries
if ($FixMissingLibraries) {
    Write-Host "Fixing missing libraries..." -ForegroundColor Cyan
    
    # Load JSON data
    $jsonContent = Get-Content $jsonPath -Raw
    $jsonData = ConvertFrom-Json $jsonContent
    
    # Connect to database
    $conn = Get-DbConnection
    
    # Check for photos without libraries
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT COUNT(*) FROM photos WHERE library_id IS NULL OR library_id NOT IN (SELECT id FROM libraries)"
    $orphanedPhotosCount = $cmd.ExecuteScalar()
    
    if ($orphanedPhotosCount -gt 0) {
        Write-Host "Found $orphanedPhotosCount photos without a valid library." -ForegroundColor Yellow
        
        # Create a default library if none exists
        $cmd.CommandText = "SELECT COUNT(*) FROM libraries"
        $libraryCount = $cmd.ExecuteScalar()
        
        if ($libraryCount -eq 0) {
            Write-Host "Creating a default library..." -ForegroundColor Cyan
            $cmd.CommandText = "INSERT INTO libraries (name, description) VALUES ('Default', 'Default Library for orphaned photos')"
            $cmd.ExecuteNonQuery()
            
            $cmd.CommandText = "SELECT last_insert_rowid()"
            $defaultLibraryId = $cmd.ExecuteScalar()
            
            # Add the default library to JSON
            $newLibrary = New-Object PSObject -Property @{
                id = $defaultLibraryId
                name = "Default"
                description = "Default Library for orphaned photos"
            }
            $jsonData.libraries += $newLibrary
            
            # Update the JSON file
            $jsonContent = ConvertTo-Json $jsonData -Depth 10
            Set-Content -Path $jsonPath -Value $jsonContent
            
            Write-Host "Default library created with ID: $defaultLibraryId" -ForegroundColor Green
        } else {
            # Get the first library ID to use
            $cmd.CommandText = "SELECT id FROM libraries LIMIT 1"
            $defaultLibraryId = $cmd.ExecuteScalar()
            Write-Host "Using existing library with ID: $defaultLibraryId" -ForegroundColor Cyan
        }
        
        # Assign orphaned photos to the default library
        $cmd.CommandText = "UPDATE photos SET library_id = $defaultLibraryId WHERE library_id IS NULL OR library_id NOT IN (SELECT id FROM libraries)"
        $updatedPhotos = $cmd.ExecuteNonQuery()
        Write-Host "Updated $updatedPhotos photos to use library ID: $defaultLibraryId" -ForegroundColor Green
    } else {
        Write-Host "No orphaned photos found." -ForegroundColor Green
    }
    
    $conn.Close()
}

# Sync database to JSON
if ($SyncDbToJson) {
    Write-Host "Synchronizing JSON file from database..." -ForegroundColor Cyan
    
    # Use process_photos.py to export the data
    & python process_photos.py --export
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "JSON file updated successfully." -ForegroundColor Green
    } else {
        Write-Host "Failed to update JSON file." -ForegroundColor Red
    }
}

# Verify files exist
if ($VerifyFiles) {
    Write-Host "Verifying photo files..." -ForegroundColor Cyan
    
    # Connect to database
    $conn = Get-DbConnection
    
    # Get all photos
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT id, path FROM photos"
    $reader = $cmd.ExecuteReader()
    
    $totalPhotos = 0
    $missingPhotos = 0
    $missingIds = @()
    
    while ($reader.Read()) {
        $totalPhotos++
        $id = $reader["id"]
        $path = $reader["path"]
        
        if (-not (Test-Path $path)) {
            $missingPhotos++
            $missingIds += $id
            Write-Host "Missing file: $path (ID: $id)" -ForegroundColor Yellow
        }
    }
    
    $reader.Close()
    $conn.Close()
    
    Write-Host "Verification complete: $missingPhotos/$totalPhotos files are missing." -ForegroundColor Cyan
    
    if ($missingPhotos -gt 0 -and $RemoveOrphans) {
        # Connect to database again
        $conn = Get-DbConnection
        
        # Remove orphaned photos
        $cmd = $conn.CreateCommand()
        $missingIdsStr = $missingIds -join ","
        $cmd.CommandText = "DELETE FROM photos WHERE id IN ($missingIdsStr)"
        $deletedCount = $cmd.ExecuteNonQuery()
        
        Write-Host "Removed $deletedCount orphaned photos from database." -ForegroundColor Green
        
        $conn.Close()
        
        # Update JSON
        if ($SyncDbToJson) {
            Write-Host "Updating JSON file after removing orphaned photos..." -ForegroundColor Cyan
            & python process_photos.py --export
        } else {
            Write-Host "Run with -SyncDbToJson to update the JSON file too." -ForegroundColor Yellow
        }
    }
}

Write-Host "Database and JSON repair operations completed." -ForegroundColor Green
