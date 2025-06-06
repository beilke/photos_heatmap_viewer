# Script to check the database structure and content
$dbPath = Join-Path (Get-Location) "photo_library.db"

if (-not (Test-Path $dbPath)) {
    Write-Host "Database file not found: $dbPath" -ForegroundColor Red
    exit
}

Write-Host "Examining database: $dbPath" -ForegroundColor Green

# Create a temporary SQL script
$sqlScript = @"
.headers on
.mode column
.width 30 30 30 30

PRAGMA table_info(libraries);

SELECT 'Libraries Table:' AS '';
SELECT COUNT(*) AS 'Total Libraries' FROM libraries;
SELECT id, name, description FROM libraries LIMIT 5;

SELECT 'Photos Table:' AS '';
PRAGMA table_info(photos);
SELECT COUNT(*) AS 'Total Photos' FROM photos;
SELECT COUNT(*) AS 'Photos with GPS' FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

SELECT 'Sample Photos:' AS '';
SELECT filename, library_id, latitude, longitude FROM photos WHERE latitude IS NOT NULL LIMIT 5;
"@

$tempSqlFile = Join-Path $env:TEMP "db_check.sql"
$sqlScript | Out-File -Encoding utf8 $tempSqlFile

# Execute the SQL using sqlite3
$output = Get-Content $tempSqlFile | & sqlite3 $dbPath

# Display the output
$output

# Clean up
Remove-Item $tempSqlFile
