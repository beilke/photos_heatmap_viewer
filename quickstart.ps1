# Photo Heatmap Viewer - Quick Start Script

# Check if Python is installed
try {
    $pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "Using Python $pythonVersion"
} catch {
    Write-Host "Error: Python is not installed or not in the PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.6 or higher from https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# Check if first parameter is provided
if (-not $args[0]) {
    Write-Host ""
    Write-Host "Usage: " -ForegroundColor Yellow
    Write-Host "   .\quickstart.ps1 [photos_directory] [options]"
    Write-Host ""
    Write-Host "Parameters:" -ForegroundColor Yellow
    Write-Host "   [photos_directory] - Path to your photo collection directory"
    Write-Host "   [options]         - (Optional) One or more of:"
    Write-Host "                        all: Include photos without GPS data"
    Write-Host "                        clean: Clean database before import"
    Write-Host "                        force: Import all photos even if they already exist"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "   .\quickstart.ps1 D:\Photos\MyVacation"
    Write-Host "   .\quickstart.ps1 'D:\Photos\Family Vacation 2024'"
    Write-Host "   .\quickstart.ps1 D:\Photos\MyVacation all"
    Write-Host "   .\quickstart.ps1 D:\Photos\MyVacation clean"
    Write-Host "   .\quickstart.ps1 D:\Photos\MyVacation all clean"
    Write-Host ""
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

$photosDir = $args[0]

# Install requirements
Write-Host "Installing required packages..." -ForegroundColor Cyan
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install requirements." -ForegroundColor Red
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# Initialize database if it doesn't exist
if (-not (Test-Path -Path "photo_library.db")) {
    Write-Host "Initializing database..." -ForegroundColor Cyan
    python init_db.py
}

# Process photos directory
Write-Host ""
Write-Host "Processing photos from: $photosDir" -ForegroundColor Green
Write-Host "This may take a while for large photo collections..." -ForegroundColor Yellow

# Check if the directory exists and handle potential driver letter differences
if (-not (Test-Path -Path $photosDir)) {
    # Try to handle drive letter differences by checking if path is valid but with a different drive letter
    $pathWithoutDrive = $photosDir.Substring(2)
    $foundAlternatePath = $false
    
    foreach ($driveLetter in [char[]](65..90)) { # A-Z
        $alternatePath = "${driveLetter}:$pathWithoutDrive"
        if (Test-Path -Path $alternatePath) {
            Write-Host "Original path not found, but found an alternate path at: $alternatePath" -ForegroundColor Yellow
            $photosDir = $alternatePath
            $foundAlternatePath = $true
            break
        }
    }
    
    if (-not $foundAlternatePath) {
        Write-Host "ERROR: The directory does not exist: $photosDir" -ForegroundColor Red
        Read-Host -Prompt "Press Enter to exit"
        exit 1
    }
}

# Process optional parameters
$includeNonGeotagged = $false
$cleanDb = $false
$forceImport = $false

# Check all arguments after the first one
for ($i = 1; $i -lt $args.Count; $i++) {
    $option = $args[$i].ToLower()
    if ($option -eq "all" -or $option -eq "true") {
        $includeNonGeotagged = $true
        Write-Host "Including photos without GPS data" -ForegroundColor Yellow
    }
    elseif ($option -eq "clean") {
        $cleanDb = $true
        Write-Host "Will clean database before import" -ForegroundColor Yellow
    }
    elseif ($option -eq "force") {
        $forceImport = $true
        Write-Host "Will force import of all photos" -ForegroundColor Yellow
    }
}

# Build the processing command
$processCommand = "python process_photos.py --process `"$photosDir`""

# Add options
if ($includeNonGeotagged) {
    $processCommand += " --include-all"
    Write-Host "Processing all photos (including those without GPS data)..." -ForegroundColor Cyan
} else {
    Write-Host "Processing only photos with GPS data..." -ForegroundColor Cyan
}

if ($cleanDb) {
    $processCommand += " --clean"
    Write-Host "Cleaning database before import..." -ForegroundColor Cyan
}

if ($forceImport) {
    $processCommand += " --force"
    Write-Host "Forcing import of all photos..." -ForegroundColor Cyan
}

# Execute the command
Write-Host "Command: $processCommand" -ForegroundColor DarkGray

try {
    Invoke-Expression $processCommand 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to process photos. Exit code: $LASTEXITCODE" -ForegroundColor Red
        Read-Host -Prompt "Press Enter to exit"
        exit 1
    }
}
catch {
    Write-Host "Error executing command: $_" -ForegroundColor Red
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# Export to JSON
Write-Host ""
Write-Host "Exporting data to JSON..." -ForegroundColor Cyan

# Build the export command
$exportCommand = "python process_photos.py --export"
if ($includeNonGeotagged) {
    $exportCommand += " --export-all"
}

# Execute the export command
Write-Host "Command: $exportCommand" -ForegroundColor DarkGray

try {
    Invoke-Expression $exportCommand 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to export data. Exit code: $LASTEXITCODE" -ForegroundColor Red
        Read-Host -Prompt "Press Enter to exit"
        exit 1
    }
    
    # Verify JSON file exists and isn't empty
    if (-not (Test-Path -Path "photo_heatmap_data.json")) {
        Write-Host "Warning: JSON file was not created. Will try to create an empty one." -ForegroundColor Yellow
        "[{}]" | Out-File -FilePath "photo_heatmap_data.json" -Encoding utf8
    } elseif ((Get-Item -Path "photo_heatmap_data.json").Length -eq 0) {
        Write-Host "Warning: JSON file is empty. Will create a valid empty array." -ForegroundColor Yellow
        "[]" | Out-File -FilePath "photo_heatmap_data.json" -Encoding utf8 -Force
    }
}
catch {
    Write-Host "Error executing export command: $_" -ForegroundColor Red
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

# Show stats
Write-Host ""
Write-Host "Database Statistics:" -ForegroundColor Cyan
python maintain_db.py --stats

# Start the web server
Write-Host ""
Write-Host "----------------------------------------------------" -ForegroundColor Green
Write-Host "✓ Database setup complete!" -ForegroundColor Green
Write-Host "✓ Photos processed successfully!" -ForegroundColor Green
Write-Host "✓ JSON data exported!" -ForegroundColor Green
Write-Host "----------------------------------------------------" -ForegroundColor Green
Write-Host ""
Write-Host "Starting web server..." -ForegroundColor Green
Write-Host "Open http://localhost:8000 in your browser" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server (it should respond quickly now)" -ForegroundColor Yellow
Write-Host "Alternatively, you can close this window to stop the server" -ForegroundColor Yellow
Write-Host ""

# Trap Ctrl+C to make stopping cleaner
try {
    python server.py
}
catch {
    Write-Host "`nStopping server..." -ForegroundColor Yellow
}
