# Photo Loading Fix

## Issues Found

1. **Duplicate Entries in Clusters**: Fixed in the previous update by changing SQL deduplication to be based on filename only.

2. **Multiple Requests for Same Photo**: The logs showed that the same photo was being requested multiple times with different quality settings:
   ```
   2025-06-30 10:55:36,107 - INFO - Serving original photo with ID or filename: 43778
   2025-06-30 10:55:36,230 - INFO - 127.0.0.1 - - [30/Jun/2025 10:55:36] "GET /photos/43778?format=jpeg&quality=100 HTTP/1.1" 206 -
   2025-06-30 10:55:36,239 - INFO - Serving original photo with ID or filename: 43778
   2025-06-30 10:55:36,331 - INFO - 127.0.0.1 - - [30/Jun/2025 10:55:36] "GET /photos/43778?format=jpeg&quality=90 HTTP/1.1" 206 -
   2025-06-30 10:55:36,340 - INFO - Serving original photo with ID or filename: 43778
   2025-06-30 10:55:36,343 - INFO - Serving original photo with ID or filename: 43778
   2025-06-30 10:55:36,464 - INFO - 127.0.0.1 - - [30/Jun/2025 10:55:36] "GET /photos/43778?format=jpeg&quality=80 HTTP/1.1" 206 -
   2025-06-30 10:55:36,475 - INFO - 127.0.0.1 - - [30/Jun/2025 10:55:36] "GET /photos/43778?format=jpeg&quality=90 HTTP/1.1" 206 -
   ```

## Solution

Modified the photo viewer logic to:

1. **Use Single Quality Parameter**: For regular images, now using only quality=80 with no fallbacks.

2. **Track Load Attempts**: Keeping the counter to track image load attempts but removing quality fallbacks.

3. **Limit Retries**: If the initial load fails:
   - For HEIC images: Still try once more with the standard photos endpoint
   - For regular images: No more quality fallbacks - only try with quality=80 once
   - After that, show an error image instead of making more requests

4. **Better Error Handling**: Added clearer error feedback when image loading fails.

## Code Changes

The main changes were in `photo-viewer.js`:

1. Added load attempt tracking:
   ```javascript
   photoViewerImg.dataset.loadAttempts = "0";
   ```

2. Used single quality parameter:
   ```javascript
   photoViewerImg.src = `/photos/${encodeURIComponent(photo.id)}?format=jpeg&quality=80`;
   ```

3. Limited retries and improved error handling:
   ```javascript
   // Get current attempts count
   const attempts = parseInt(photoViewerImg.dataset.loadAttempts || "0", 10);
   
   // Only try alternative method for HEIC files, no quality fallbacks for regular images
   if (attempts < 1) {
       photoViewerImg.dataset.loadAttempts = (attempts + 1).toString();
       
       if (isHeic) {
           // HEIC-specific retry logic
       }
       // No quality fallback for regular images - using consistent quality=80
   }
   ```

These changes should significantly reduce server load and prevent the duplicate requests that were occurring before.
