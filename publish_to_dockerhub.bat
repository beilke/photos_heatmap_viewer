@echo off
REM Windows batch file to build and publish the Docker image

REM Configuration
SET DOCKERHUB_USERNAME=fbeilke
SET IMAGE_NAME=photo-heatmap-viewer
SET VERSION=1.0.0

echo Checking Docker status...
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo Error: Docker is not running or not accessible
  exit /b 1
)

echo Checking DockerHub login status...
docker info | findstr Username >nul
if %ERRORLEVEL% NEQ 0 (
  echo Not logged in to DockerHub. Please login manually using:
  echo docker login
  docker login
  if %ERRORLEVEL% NEQ 0 (
    echo Login failed. Please check your credentials and try again.
    exit /b 1
  )
  echo Login successful!
) else (
  echo Already logged in to DockerHub.
)

echo Cleaning up existing containers...
for /f "tokens=*" %%i in ('docker ps -aqf "name=%IMAGE_NAME%"') do docker kill %%i 2>nul
for /f "tokens=*" %%i in ('docker ps -aqf "name=%IMAGE_NAME%"') do docker rm %%i 2>nul

REM Create Dockerfile.dockerhub with updated process_libraries.sh
echo Building Docker image with no cache...
docker build --no-cache -f Dockerfile.dockerhub -t %IMAGE_NAME%:latest .

REM Tag the image with version and latest
echo Tagging images...
docker tag %IMAGE_NAME%:latest %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%VERSION%
docker tag %IMAGE_NAME%:latest %DOCKERHUB_USERNAME%/%IMAGE_NAME%:latest

REM Push to DockerHub
echo Pushing to DockerHub...
docker push %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%VERSION%
docker push %DOCKERHUB_USERNAME%/%IMAGE_NAME%:latest

echo Successfully pushed %DOCKERHUB_USERNAME%/%IMAGE_NAME%:%VERSION% to DockerHub
echo Also pushed as %DOCKERHUB_USERNAME%/%IMAGE_NAME%:latest
echo.
echo Users can pull your image with:
echo docker pull %DOCKERHUB_USERNAME%/%IMAGE_NAME%:latest
echo.
echo To run the container:
echo docker run -d --name photo-heatmap-viewer ^
echo   -p 8000:8000 ^
echo   -v /path/to/photos:/photos ^
echo   -v /path/to/data:/app/data ^
echo   -v /path/to/logs:/app/logs ^
echo   %DOCKERHUB_USERNAME%/%IMAGE_NAME%:latest
