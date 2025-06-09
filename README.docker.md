# Photo Heatmap Viewer - Docker Setup

This Docker setup allows you to run the Photo Heatmap Viewer application along with an optional processor service that automatically updates the photo libraries.

## Features

- **Web Application**: View your photo locations on an interactive map
- **Automatic Processing**: Schedule automatic processing of photo libraries
- **Health Checking**: Docker health checks ensure the application is running correctly
- **Log Rotation**: Logs are stored for one week and automatically rotated
- **Last Update Display**: See when each library was last updated directly on the map

## Quick Start

1. Run the setup script to create the necessary directory structure:

```bash
chmod +x setup.sh
./setup.sh
```

2. Copy or link your photos to the library directories:

```bash
# Example: Link existing photo directories
ln -s /path/to/your/photos ./photos/library1
ln -s /path/to/your/vacation/photos ./photos/library2
```

3. Edit the .env file to configure your libraries and schedules:

```
# Example .env configuration
PHOTOS_ROOT_DIR=/absolute/path/to/photos
LIBRARIES=vacation:Vacation Photos,family:Family Album
UPDATE_SCHEDULE=0 */6 * * *
TZ=UTC
```

4. Start the application:

```bash
# Start just the web application
docker-compose up -d

# Or start both the web application and the processor service
docker-compose -f docker-compose.yml -f docker-compose.processor.yml up -d
```

4. Access the application at http://localhost:8000

## Manual Library Processing

To manually process a photo library:

```bash
docker exec photo-heatmap-photo-processor-1 /app/process_library.sh /photos/your_library "Your Library Name"
```

## Configuration

### Environment Variables

- `PHOTOS_ROOT_DIR`: Absolute path to your photos directory
- `LIBRARIES`: Comma-separated list of libraries in format `folder:name` 
- `UPDATE_SCHEDULE`: Cron schedule for updating libraries (default: every 6 hours)
- `TZ`: Timezone for timestamps (default: UTC)

### Docker Compose Environment Variables

- `PHOTOS_ROOT_DIR`: Root directory for photos (default: `./photos`)

### Customizing Library Processing Schedule

Edit the `docker-compose.processor.yml` file to change the cron schedule for processing libraries:

```yaml
# Example: Process library1 every day at midnight
echo '0 0 * * * /app/process_library.sh /photos/library1 \"Library1\" >> /app/logs/cron.log 2>&1' > /etc/cron.d/process_photos
```

## Directory Structure

- `./data`: Contains the SQLite database and generated JSON files
- `./logs`: Contains application logs (rotated weekly)
- `./photos`: Root directory for photo libraries
  - `./photos/library1`: First photo library
  - `./photos/library2`: Second photo library

## Logs

Application logs are stored in the `./logs` directory and are rotated daily, keeping logs for one week.

- Processing logs: `photo_processing_YYYYMMDD_HHMMSS.log`
- Cron job logs: `cron.log`
- Log rotation logs: `logrotate.log`

## Health Checks

The application includes a health check endpoint at `/health` that returns "OK" when the service is functioning correctly. Docker uses this endpoint to monitor the container's health.
