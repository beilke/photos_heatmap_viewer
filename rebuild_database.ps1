Write-Host "Rebuilding Photo Database with Fixed GPS Extraction" -ForegroundColor Green

Write-Host "Cleaning current database..." -ForegroundColor Cyan
python process_photos.py --clean

Write-Host "Processing photos (Default library)..." -ForegroundColor Cyan
python process_photos.py --process "D:\photogps" --library "Default"

Write-Host "Processing photos (Fernando library)..." -ForegroundColor Cyan
python process_photos.py --process "D:\photogps" --library "Fernando"

Write-Host "Exporting photo data to JSON..." -ForegroundColor Cyan
python process_photos.py --export

Write-Host "Done! Please restart your server and try loading the web page again." -ForegroundColor Green
