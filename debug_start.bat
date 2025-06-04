@echo off
echo This script will help diagnose and fix issues with the Photo Heatmap Viewer.
echo.

REM Check if server is running
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
  echo Server is running on port 8000. Stopping it first...
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /F /PID %%a
  )
)

echo Inspecting JSON data file...
python inspect_json.py

set /p fix_json="Would you like to fix the JSON file if there are issues? (y/n): "
if /i "%fix_json%"=="y" (
  echo Attempting to fix JSON file...
  python inspect_json.py --fix
)

echo.
echo Starting server with debug mode enabled...
python server.py --debug

echo.
echo Open http://localhost:8000 in your browser to view the photo heatmap.
