# PowerShell script to fix GPS data extraction and rebuild the photo database
Write-Host "Photo Database GPS Fix Tool" -ForegroundColor Green

# Install required Python packages
Write-Host "Installing necessary packages for GPS extraction..." -ForegroundColor Cyan
pip install -r requirements.txt

# Clean the existing database
Write-Host "Cleaning the existing database..." -ForegroundColor Cyan
python process_photos.py --clean

# Process photos with improved GPS extraction
Write-Host "Processing photos with improved GPS extraction for each library..." -ForegroundColor Cyan

# Get libraries from database
$libraries = python -c "import sqlite3; conn = sqlite3.connect('photo_library.db'); cursor = conn.cursor(); cursor.execute('SELECT id, name FROM libraries'); print('\n'.join([f'{row[0]}|{row[1]}' for row in cursor.fetchall()])); conn.close()"

if ($libraries) {
    $libraries.Split("`n") | ForEach-Object {
        $libraryInfo = $_ -split '\|'
        if ($libraryInfo.Length -eq 2) {
            $id = $libraryInfo[0]
            $name = $libraryInfo[1]
            
            Write-Host "Processing library: $name (ID: $id)" -ForegroundColor Yellow
            
            # Get source directories for this library
            $sourceDirs = python -c "import sqlite3, json; conn = sqlite3.connect('photo_library.db'); cursor = conn.cursor(); cursor.execute('SELECT source_dirs FROM libraries WHERE id = ?', ($id,)); result = cursor.fetchone(); print(json.loads(result[0]) if result and result[0] else ''); conn.close()"
            
            if ($sourceDirs) {
                $sourceDirsArray = $sourceDirs -replace '\[|\]|''|"', '' -split ','
                foreach ($dir in $sourceDirsArray) {
                    $cleanDir = $dir.Trim()
                    if ($cleanDir) {
                        Write-Host "  Processing directory: $cleanDir" -ForegroundColor Cyan
                        python process_photos.py --process "$cleanDir" --library "$name"
                    }
                }
            } else {
                Write-Host "  No source directories found for this library" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "No libraries found in database. Creating a default one..." -ForegroundColor Yellow
    
    # Ask for a default directory
    $defaultDir = Read-Host "Enter the path to your photos directory"
    if ($defaultDir -and (Test-Path $defaultDir)) {
        python process_photos.py --process "$defaultDir" --library "Default"
    } else {
        Write-Host "Invalid directory or no directory provided" -ForegroundColor Red
    }
}

# Export the data to JSON
Write-Host "Exporting photo data to JSON..." -ForegroundColor Cyan
python process_photos.py --export

Write-Host "`nProcess complete!" -ForegroundColor Green
Write-Host "The database should now have GPS coordinates extracted properly." -ForegroundColor Green
Write-Host "Restart your server and try loading the website again." -ForegroundColor Green
