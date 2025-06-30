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

1. In `markers.js`, we added ID-based deduplication (with filename fallback) for the cluster display counts:
```javascript
// Deduplicate by ID if available, otherwise fall back to filename
const uniqueIds = new Set();
let uniqueCount = 0;

markers.forEach(marker => {
    if (marker.photoData) {
        // Use ID for deduplication if available, otherwise use filename
        const uniqueKey = marker.photoData.id || marker.photoData.filename;
        if (uniqueKey && !uniqueIds.has(uniqueKey)) {
            uniqueIds.add(uniqueKey);
            uniqueCount++;
        }
    }
});
```

2. We added ID-based deduplication (with filename fallback) for marker clusters when viewing photos:
```javascript
// Collect all photos from all markers in this cluster with ID/filename deduplication
let allPhotos = [];
const uniqueIds = new Set(); // Track unique IDs (or filenames) to prevent duplicates

// Process only the markers in this specific cluster
markers.forEach(marker => {
    if (marker.photoData) {
        const photo = marker.photoData;
        
        // Always ensure full path is available
        if (!photo.full_path) {
            photo.full_path = photo.path || '';
        }
        
        // Use photo ID for deduplication if available, otherwise use filename
        const uniqueKey = photo.id || photo.filename;
        
        // Only add this photo if we haven't seen this ID/filename yet
        if (!uniqueIds.has(uniqueKey)) {
            uniqueIds.add(uniqueKey);
            allPhotos.push(photo);
        } else {
            debugLog(`Skipping duplicate photo in cluster`);
        }
    }
});
```

3. We implemented the same deduplication logic for the single marker click handler:
```javascript
// Deduplicate by ID if available, otherwise fall back to filename
const uniqueIds = new Set();
const uniquePhotos = [];

photosAtSameLocation.forEach(p => {
    // Always ensure full path is available
    if (!p.full_path) {
        p.full_path = p.path || '';
    }
    
    // Use photo ID for deduplication if available, otherwise use filename
    const uniqueKey = p.id || p.filename;
    
    // Only include photos with unique IDs (or filenames if ID not available)
    if (!uniqueIds.has(uniqueKey)) {
        uniqueIds.add(uniqueKey);
        uniquePhotos.push(p);
    }
});
```

4. We updated image loading to prefer photo IDs over filenames:
```javascript
// Always use photo ID if available, fall back to filename only if needed
img.src = `/photos/${encodeURIComponent(photo.id || photo.filename)}`;
```

## Examples

Files like `COLOR_POP.jpg` appeared up to 10 times in the database with 6 different coordinate sets. Similar patterns were found for many other files. Our solution ensures that each file appears only once regardless of its coordinates.

## Future Considerations

For a more sophisticated approach in the future, the application could:

1. Consider image similarity metrics beyond just filenames
2. Allow users to choose which duplicate to keep when there are multiple versions
3. Use metadata like creation date to determine the "master" copy
