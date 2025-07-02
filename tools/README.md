# Photo Heatmap Viewer Diagnostic Tools

This directory contains diagnostic scripts to help troubleshoot issues with the Photo Heatmap Viewer application. These tools are particularly useful when debugging database issues, deduplication problems, or photo clustering concerns.

## Available Tools

### check_cluster.py
Examines photos within specific geographic clusters to identify duplicates.

```
python tools/check_cluster.py [latitude] [longitude] [optional_radius]
# Example:
python tools/check_cluster.py 40.7128 -74.0060 0.0005
```

Or search by filename:
```
python tools/check_cluster.py "IMG_1234.jpg"
```

### check_db.py
Performs basic database validation and checks for duplicate filenames.

```
python tools/check_db.py
```

### check_duplicates.py
Finds duplicate photos in the database by filename and path.

```
python tools/check_duplicates.py
```

### check_near_duplicates.py
Identifies photos with same filename but slightly different coordinates, which can cause issues with clustering.

```
python tools/check_near_duplicates.py
```

### check_photo.py
Examines details of a specific photo by ID and shows other photos with the same filename.

```
python tools/check_photo.py [photo_id]
# Example:
python tools/check_photo.py 12345
```

### check_specific_photos.py
Tests deduplication for specific photos across libraries.

```
python tools/check_specific_photos.py
```

### check_sql.py
Validates SQL deduplication queries are working correctly by comparing raw counts with deduplicated counts.

```
python tools/check_sql.py
```

### verify_deduplication.py
Compares the effectiveness of different deduplication strategies (filename-only vs. filename+coordinates).

```
python tools/verify_deduplication.py
```

## Documentation Files

### deduplication_fix.md
Documentation of the SQL and JavaScript changes implemented to fix duplicate photo issues in the application.

### photo_loading_fix.md
Documents the solutions to multiple photo loading requests issue, including the implementation of a consistent quality parameter and limited retries.

## Usage Notes

These scripts are intended primarily for development and debugging purposes. They access the database directly and can help identify issues that might be causing:

1. Duplicate photos appearing in clusters
2. Photos not appearing where expected
3. Issues with SQL deduplication
4. Database integrity problems

Most scripts will automatically look for the database in both the standard location (`data/photo_library.db`) and the root directory (`photo_library.db`).

## Deduplication Strategy

The current deduplication strategy used in the main application:

1. **Server-side**: SQL query uses `ROW_NUMBER() OVER(PARTITION BY p.filename ORDER BY p.id) as rn` to ensure only one instance of each filename is returned
2. **Client-side**: JavaScript in markers.js implements deduplication to ensure unique photos in clusters using photo IDs or filenames
