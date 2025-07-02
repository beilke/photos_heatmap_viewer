# start_server.ps1
# PowerShell script to start the Photo Heatmap Viewer server

param (
    [switch]$debug = $false,
    [int]$port = 8000,
    [string]$host = "0.0.0.0"
)

# Check if running as administrator, which is needed for some operations like process termination
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Note: Some operations may require administrator privileges." -ForegroundColor Yellow
}

Write-Host "Starting Photo Heatmap Viewer Server..." -ForegroundColor Cyan

# Create logs directory if it doesn't exist
if (-not (Test-Path -Path "logs")) {
    Write-Host "Creating logs directory..." -ForegroundColor Gray
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Stop any existing Python processes running the server (optional, can be commented out)
try {
    Write-Host "Checking for existing server processes..." -ForegroundColor Gray
    $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | 
                      Where-Object { $_.CommandLine -like "*server.py*" }
    
    if ($pythonProcesses) {
        Write-Host "Stopping existing server processes..." -ForegroundColor Yellow
        $pythonProcesses | ForEach-Object { 
            Stop-Process -Id $_.Id -Force
            Write-Host "Stopped process with ID: $($_.Id)" -ForegroundColor Gray
        }
    } else {
        Write-Host "No existing server processes found." -ForegroundColor Gray
    }
} catch {
    Write-Host "Warning: Failed to check or stop existing processes. Continuing anyway." -ForegroundColor Yellow
    Write-Host "Error details: $_" -ForegroundColor DarkGray
}

# Activate the Python virtual environment
Write-Host "Activating Python virtual environment..." -ForegroundColor Cyan

# Check for both venv versions and use the one that exists
if (Test-Path -Path ".\.venv-py39\Scripts\activate.ps1") {
    # Python 3.9 environment
    & .\.venv-py39\Scripts\activate.ps1
    Write-Host "Using Python 3.9 environment" -ForegroundColor Green
} elseif (Test-Path -Path ".\.venv\Scripts\activate.ps1") {
    # Default environment
    & .\.venv\Scripts\activate.ps1
    Write-Host "Using default Python environment" -ForegroundColor Green
} else {
    Write-Host "Warning: No virtual environment found. Using system Python." -ForegroundColor Yellow
}

# Set up logging to redirect to logs folder
$logFile = ".\logs\server.log"
Write-Host "Logs will be saved to: $logFile" -ForegroundColor Cyan

# Start the server
try {
    Write-Host "Starting server..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop the server." -ForegroundColor DarkGray
    
    # Build server command with parameters
    $serverCommand = "server.py"
    $serverArgs = @()
    
    if ($debug) {
        Write-Host "Running in debug mode" -ForegroundColor Yellow
        $serverArgs += "--debug"
    }
    
    if ($port -ne 8000) {
        Write-Host "Using custom port: $port" -ForegroundColor Yellow
        $serverArgs += "--port"
        $serverArgs += "$port"
    }
    
    if ($host -ne "0.0.0.0") {
        $serverArgs += "--host"
        $serverArgs += "$host"
    }
    
    # Combine args into a string for display
    $argsDisplay = $serverArgs -join " "
    Write-Host "Command: python $serverCommand $argsDisplay" -ForegroundColor DarkGray
    
    # Start Python server - directing output to both console and log file
    & python $serverCommand $serverArgs | Tee-Object -FilePath $logFile
} catch {
    Write-Host "Error starting server: $_" -ForegroundColor Red
    Write-Host "Check logs for more details." -ForegroundColor Yellow
    Exit 1
}

Write-Host "Server has stopped." -ForegroundColor Cyan
