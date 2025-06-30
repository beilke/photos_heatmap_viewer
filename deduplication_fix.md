# Photo Deduplication Fix

## Issue Description

Photos with the same filename but at different coordinates were appearing multiple times in clusters. The previous deduplication strategy was only preventing duplicates with both the same filename AND coordinates, which meant:

1. Photos with the same filename existing in different libraries would still show multiple times
2. Photos with the same filename but slightly different GPS coordinates would still show multiple times

## Analysis

After analyzing the database, we found:

- The database contains 61,979 photos with GPS coordinates
- Only 41,705 of these have unique filenames (indicating ~20,274 duplicate files)
- Previously, the SQL query was deduplicating based on filename + latitude + longitude
- This approach still left 48,743 photos (removing only 13,236 duplicates or 21.4%)

## Solution

### Server-side Deduplication

We modified the SQL queries in `server.py` to deduplicate based on filename only:

```sql
WITH RankedPhotos AS (
    SELECT 
        p.id, p.filename, p.path, p.latitude, p.longitude, p.datetime, 
        p.marker_data, p.library_id, l.name as library_name,
        ROW_NUMBER() OVER(PARTITION BY p.filename ORDER BY p.id) as rn
    FROM photos p
    LEFT JOIN libraries l ON p.library_id = l.id
    WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
)
SELECT 
    id, filename, path, latitude, longitude, datetime, 
    marker_data, library_id, library_name
FROM RankedPhotos
WHERE rn = 1
```

This approach:
- Removes 20,274 duplicates (32.7% of the total)
- Ensures each filename appears only once, regardless of coordinates
- Eliminates duplicate files across libraries

### Client-side Deduplication

Additionally, we modified the client-side JavaScript code to ensure clusters accurately represent unique photos:

1. In `markers.js`, we added filename-based deduplication for the cluster display counts:
```javascript
// Deduplicate by filename before counting
const uniqueFilenames = new Set();
let uniqueCount = 0;

markers.forEach(marker => {
    if (marker.photoData && marker.photoData.filename) {
        if (!uniqueFilenames.has(marker.photoData.filename)) {
            uniqueFilenames.add(marker.photoData.filename);
            uniqueCount++;
        }
    }
});
```

2. We added filename-based deduplication for marker clusters when viewing photos:
```javascript
// Collect all photos from all markers in this cluster with filename deduplication
let allPhotos = [];
const uniqueFilenames = new Set(); // Track unique filenames to prevent duplicates

// Process only the markers in this specific cluster
markers.forEach(marker => {
    if (marker.photoData) {
        const photo = marker.photoData;
        
        // Only add this photo if we haven't seen this filename yet
        if (!uniqueFilenames.has(photo.filename)) {
            uniqueFilenames.add(photo.filename);
            allPhotos.push(photo);
        } else {
            debugLog(`Skipping duplicate filename in cluster: ${photo.filename}`);
        }
    }
});
```

3. We also implemented the same deduplication logic for the single marker click handler to ensure that even at the same coordinates, photos with the same filename are only shown once.

## Examples

Files like `COLOR_POP.jpg` appeared up to 10 times in the database with 6 different coordinate sets. Similar patterns were found for many other files. Our solution ensures that each file appears only once regardless of its coordinates.

## Future Considerations

For a more sophisticated approach in the future, the application could:

1. Consider image similarity metrics beyond just filenames
2. Allow users to choose which duplicate to keep when there are multiple versions
3. Use metadata like creation date to determine the "master" copy
