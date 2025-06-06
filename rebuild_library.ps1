# Rebuild Photo Library
# This script performs a complete rebuild of the photo library

param (
    [Parameter(Mandatory = $true)]
    [string]$LibraryName,
    
    [Parameter(Mandatory = $true)]
    [string]$PhotoDir,
    
    [string]$Description = "",
    
    [switch]$CleanFirst = $false,
    
    [switch]$RestartServer = $false,
    
    [int]$Workers = 4
)

# Display initial info
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Photo Library Rebuild Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Library Name: $LibraryName" -ForegroundColor Yellow
Write-Host "Photo Directory: $PhotoDir" -ForegroundColor Yellow
Write-Host "Description: $(if ($Description) {$Description} else {"<none>"})" -ForegroundColor Yellow
Write-Host "Clean First: $CleanFirst" -ForegroundColor Yellow
Write-Host "Worker Threads: $Workers" -ForegroundColor Yellow
Write-Host ""

# Step 1: Clean data if requested
if ($CleanFirst) {
    Write-Host "Step 1: Cleaning existing data..." -ForegroundColor Cyan
    & .\clean_data.ps1 -Force
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to clean data. Exiting." -ForegroundColor Red
        exit 1
    }
    Write-Host "Clean completed." -ForegroundColor Green
} else {
    Write-Host "Step 1: Clean data skipped." -ForegroundColor Cyan
}

# Step 2: Create the library
Write-Host ""
Write-Host "Step 2: Creating library '$LibraryName'..." -ForegroundColor Cyan
$createArgs = @("create", $LibraryName, $PhotoDir)
if ($Description) {
    $createArgs += "-description"
    $createArgs += $Description
}
& .\manage_libraries.ps1 $createArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create library. Exiting." -ForegroundColor Red
    exit 1
}
Write-Host "Library created." -ForegroundColor Green

# Step 3: Process photos
Write-Host ""
Write-Host "Step 3: Processing photos..." -ForegroundColor Cyan
& python process_photos.py --process $LibraryName --workers $Workers
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to process photos. Exiting." -ForegroundColor Red
    exit 1
}
Write-Host "Photos processed." -ForegroundColor Green

# Step 4: Export data
Write-Host ""
Write-Host "Step 4: Exporting data to JSON..." -ForegroundColor Cyan
& python process_photos.py --export
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to export data. Exiting." -ForegroundColor Red
    exit 1
}
Write-Host "Data exported." -ForegroundColor Green

# Step 5: Restart server if requested
if ($RestartServer) {
    Write-Host ""
    Write-Host "Step 5: Restarting server..." -ForegroundColor Cyan
    
    # Kill any existing Python server
    Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.MainModule.FileName -like "*python.exe" } | Stop-Process -Force
    
    # Start the server in a new process
    $serverProcess = Start-Process -FilePath "python" -ArgumentList "server.py", "--debug" -NoNewWindow -PassThru
    
    if ($serverProcess) {
        Write-Host "Server restarted (PID: $($serverProcess.Id))." -ForegroundColor Green
    } else {
        Write-Host "Failed to restart server." -ForegroundColor Red
    }
} else {
    Write-Host ""
    Write-Host "Step 5: Server restart skipped." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Library rebuild complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Your photo library is now ready to use." -ForegroundColor Yellow
Write-Host "Open http://localhost:8000 in your browser to view it." -ForegroundColor Yellow

# Display some useful commands
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  - View libraries: .\manage_libraries.ps1 list" -ForegroundColor Cyan
Write-Host "  - Start server: python server.py --debug" -ForegroundColor Cyan
Write-Host "  - Add another library: .\rebuild_library.ps1 -LibraryName 'Another' -PhotoDir 'path\to\photos' -CleanFirst:$false" -ForegroundColor Cyan
