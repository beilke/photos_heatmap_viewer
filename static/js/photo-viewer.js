/**
 * Photo viewer functionality for Photo Heatmap Viewer
 */

// Constants for photo viewer
const PRELOAD_BATCH_SIZE = 50;
const MAX_LOADED_PHOTOS = 200;

// Open the photo viewer
function openPhotoViewer(photos, startIndex = 0) {
    if (!photos || photos.length === 0) {
        debugLog('Cannot open photo viewer: No photos provided');
        return;
    }

    debugLog(`Opening photo viewer with ${photos.length} photos, starting at index ${startIndex}`);
    
    // Reset the photo viewer image to ensure it has proper styling
    const photoViewerImg = document.getElementById('photoViewerImg');
    if (photoViewerImg) {
        // Reset any inline styles that might have persisted
        photoViewerImg.removeAttribute('style');
        // Ensure proper display characteristics
        photoViewerImg.style.filter = 'none';
        photoViewerImg.style.opacity = '1';
    }

    // Handle large clusters more efficiently
    if (photos.length > 100) {
        debugLog(`Large cluster detected (${photos.length} photos). Using optimized handling.`);
        
        // For large clusters, only load a subset initially and then load more as needed
        // This prevents performance issues when opening very large clusters
        const initialBatch = photos.slice(0, MAX_LOADED_PHOTOS);
        currentClusterPhotos = initialBatch;
        // Store reference to full dataset for later loading
        currentClusterPhotos.fullDataset = photos;
        debugLog(`Initially loaded ${initialBatch.length}/${photos.length} photos`);
    } else {
        currentClusterPhotos = photos;
    }

    currentPhotoIdx = Math.min(startIndex, photos.length - 1);
    
    // Create navigation buttons dynamically
    const photoViewerOverlay = document.getElementById('photoViewerOverlay');
    const photoCounterDiv = photoViewerOverlay.querySelector('.photo-viewer-counter');
    photoCounterDiv.innerHTML = `
        <span id="currentPhotoIndex">${currentPhotoIdx + 1}</span>
        of
        <span id="totalPhotos">${photos.length}</span>
    `;
    
    const navButtonsDiv = photoViewerOverlay.querySelector('.nav-buttons');
    navButtonsDiv.innerHTML = `
        <button id="prevPhotoBtn" class="photo-nav-btn">&lt;</button>
        <button id="nextPhotoBtn" class="photo-nav-btn">&gt;</button>
    `;
    
    // Add event listeners to the newly created buttons
    const prevPhotoBtn = document.getElementById('prevPhotoBtn');
    const nextPhotoBtn = document.getElementById('nextPhotoBtn');
    
    // Use the appropriate event (touchend for mobile, click for desktop)
    const eventType = isMobile ? 'touchend' : 'click';
    
    prevPhotoBtn.addEventListener(eventType, function(e) {
        if (isMobile) e.preventDefault();
        showPreviousPhoto();
    });
    
    nextPhotoBtn.addEventListener(eventType, function(e) {
        if (isMobile) e.preventDefault();
        showNextPhoto();
    });
    
    // Set up the photo info displays
    const photoInfoItemsDiv = photoViewerOverlay.querySelector('.photo-viewer-detail');
    photoInfoItemsDiv.innerHTML = `
        <div class="photo-info-item">
            <div class="photo-info-label">Filename:</div>
            <div id="photoInfoFilename"></div>
        </div>
        <div class="photo-info-item">
            <div class="photo-info-label">Date:</div>
            <div id="photoInfoDate"></div>
        </div>
        <div class="photo-info-item">
            <div class="photo-info-label">Location:</div>
            <div id="photoInfoLocation"></div>
        </div>
    `;
    
    // Show the viewer and update content
    photoViewerOverlay.style.display = 'flex';
    updatePhotoViewerContent();
}

// Update the photo viewer content
function updatePhotoViewerContent() {
    const photo = currentClusterPhotos[currentPhotoIdx];
    if (!photo) {
        debugLog('Cannot update photo viewer: No photo at current index');
        return;
    }
    
    // Set the current photo ID for verification
    const photoViewerImg = document.getElementById('photoViewerImg');
    photoViewerImg.dataset.loadingPhotoId = photo.id || photo.filename;

    // Virtual scrolling: Manage loaded photos based on current index
    if (currentClusterPhotos.fullDataset) {
        const totalPhotos = currentClusterPhotos.fullDataset.length;
        const currentLoadedCount = currentClusterPhotos.length;

        // Calculate the window of photos we want to keep loaded
        const windowStart = Math.max(0, currentPhotoIdx - Math.floor(MAX_LOADED_PHOTOS / 2));
        const windowEnd = Math.min(totalPhotos, windowStart + MAX_LOADED_PHOTOS);

        // Load more photos if we're approaching the end of our loaded set
        if (currentPhotoIdx > currentLoadedCount - PRELOAD_BATCH_SIZE &&
            currentLoadedCount < totalPhotos) {
            
            debugLog(`Loading more photos: ${currentLoadedCount} -> ${Math.min(currentLoadedCount + PRELOAD_BATCH_SIZE, totalPhotos)}`);
            
            // Load the next batch
            const nextBatch = currentClusterPhotos.fullDataset.slice(
                currentLoadedCount,
                currentLoadedCount + PRELOAD_BATCH_SIZE
            );
            
            // Add to our loaded photos
            currentClusterPhotos = currentClusterPhotos.concat(nextBatch);
            // Keep reference to full dataset
            currentClusterPhotos.fullDataset = currentClusterPhotos.fullDataset;
            
            debugLog(`Now loaded ${currentClusterPhotos.length}/${totalPhotos} photos`);
        }
        
        // If we've loaded enough photos and are far enough from the start, 
        // remove some from the beginning to manage memory usage
        if (currentClusterPhotos.length > MAX_LOADED_PHOTOS &&
            currentPhotoIdx > MAX_LOADED_PHOTOS / 2) {
            
            // Calculate how many we can safely remove from the beginning
            const removeCount = Math.min(
                PRELOAD_BATCH_SIZE,
                currentPhotoIdx - PRELOAD_BATCH_SIZE
            );
            
            if (removeCount > 0) {
                debugLog(`Removing ${removeCount} photos from beginning to save memory`);
                currentClusterPhotos = currentClusterPhotos.slice(removeCount);
                // Adjust current index to account for removed photos
                currentPhotoIdx -= removeCount;
                // Keep reference to full dataset
                currentClusterPhotos.fullDataset = currentClusterPhotos.fullDataset;
            }
        }
    }

    // Update photo viewer counter
    const currentPhotoIndex = document.getElementById('currentPhotoIndex');
    const totalPhotos = document.getElementById('totalPhotos');
    
    // Need to add 1 for human-readable index (1-based instead of 0-based)
    currentPhotoIndex.textContent = (currentClusterPhotos.fullDataset ? 
        currentClusterPhotos.fullDataset.indexOf(photo) + 1 : currentPhotoIdx + 1);
    totalPhotos.textContent = currentClusterPhotos.fullDataset ?
        currentClusterPhotos.fullDataset.length : currentClusterPhotos.length;

    // Reset any existing styles on the photo viewer image
    photoViewerImg.removeAttribute('style');
    photoViewerImg.style.opacity = '0.5'; // Higher initial opacity for better visibility
    
    // Store photo filename for reference
    photoViewerImg.dataset.loadingPhotoId = photo.id || photo.filename;
    
    // Check if this is a HEIC file - they need special handling
    const isHeic = photo.filename.toLowerCase().endsWith('.heic');
    
    // Show loading message for HEIC files
    if (isHeic) {
        // Show a loading toast for HEIC images (they take longer)
        if (typeof showFeedbackToast === 'function') {
            showFeedbackToast('Converting HEIC image...', 3000);
        }
        
        // debugLog(`Loading HEIC photo: ${photo.filename}`, 'Converting to JPEG format');
        
        // For HEIC files, load the full resolution converted version directly
        photoViewerImg.src = `/photos/${encodeURIComponent(photo.filename)}?format=jpeg&quality=100`;
    } else {
        // For normal images, load directly with no quality reduction
        photoViewerImg.src = `/photos/${encodeURIComponent(photo.filename)}`;
    }
    
    // When image loads, ensure full opacity
    photoViewerImg.onload = function() {
        // Make sure this is still the photo we want to show
        // (user might have clicked next/prev while loading)
        if (photoViewerImg.dataset.loadingPhotoId === (photo.id || photo.filename)) {
            // Force full opacity - override any previous settings
            photoViewerImg.style.opacity = '1';
            // Remove any filters or transforms that might affect brightness
            photoViewerImg.style.filter = 'none';
            // Set brightness explicitly to normal
            photoViewerImg.style.filter = 'brightness(100%)';
            
            // For HEIC images, show success message
            if (isHeic) {
                // debugLog(`Successfully loaded HEIC photo: ${photo.filename}`);
                if (typeof showFeedbackToast === 'function') {
                    showFeedbackToast('HEIC image displayed successfully', 1500);
                }
            }
        }
    };
    
    // Handle error in loading the image
    photoViewerImg.onerror = function() {
        photoViewerImg.style.opacity = '1';
        photoViewerImg.style.filter = 'none';
        
        if (isHeic) {
            // debugLog(`Failed to load HEIC photo: ${photo.filename}`, 'Attempting fallback methods');
            
            // Try a different approach based on what we've already attempted
            if (this.src.includes('format=jpeg&quality=100')) {
                // First fallback - try with lower quality
                // debugLog(`Trying lower quality HEIC conversion`);
                photoViewerImg.src = `/photos/${encodeURIComponent(photo.filename)}?format=jpeg&quality=90`;
                return;
            } else if (this.src.includes('format=jpeg&quality=90')) {
                // Second fallback - try with even lower quality
                // debugLog(`Trying lower quality HEIC conversion`);
                photoViewerImg.src = `/photos/${encodeURIComponent(photo.filename)}?format=jpeg&quality=80`;
                return;
            } else if (this.src.includes('format=jpeg&quality=80')) {
                // Third fallback - try with the convert endpoint specifically
                // debugLog(`Trying dedicated convert endpoint`);
                photoViewerImg.src = `/convert/${encodeURIComponent(photo.filename)}`;
                
                if (typeof showFeedbackToast === 'function') {
                    showFeedbackToast('Trying alternative conversion method...', 2000);
                }
                return;
            }
            
            // If all conversion attempts failed, show error graphic
            if (typeof showFeedbackToast === 'function') {
                showFeedbackToast('HEIC conversion failed', 3000, true);
            }
            
            photoViewerImg.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="%23f0f0f0"/><text x="50%" y="50%" font-family="Arial" font-size="14" text-anchor="middle" dominant-baseline="middle" fill="%23666">HEIC image not supported</text><text x="50%" y="70%" font-family="Arial" font-size="12" text-anchor="middle" dominant-baseline="middle" fill="%23888">Try enabling pillow-heif</text></svg>';
        } else {
            debugLog(`Failed to load photo: ${photo.filename}`);
            photoViewerImg.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="%23f0f0f0"/><text x="50%" y="50%" font-family="Arial" font-size="14" text-anchor="middle" dominant-baseline="middle" fill="%23666">Image not available</text></svg>';
        }
    };

    // Update image info
    const photoInfoFilename = document.getElementById('photoInfoFilename');
    const photoInfoDate = document.getElementById('photoInfoDate');
    const photoInfoLocation = document.getElementById('photoInfoLocation');
    const photoInfoPath = document.getElementById('photoInfoPath');
    
    photoInfoFilename.textContent = photo.filename || 'Unknown';
    photoInfoDate.textContent = photo.datetime ?
        new Date(photo.datetime).toLocaleString() : 'No date available';
    photoInfoLocation.innerHTML = `${photo.latitude.toFixed(6)}, ${photo.longitude.toFixed(6)}`;
    photoInfoPath.textContent = photo.full_path || photo.path || 'Path not available';
}

// Close the photo viewer
function closePhotoViewer() {
    const photoViewerOverlay = document.getElementById('photoViewerOverlay');
    photoViewerOverlay.style.display = 'none';
    
    // Release large arrays to help garbage collection
    if (currentClusterPhotos.fullDataset && 
        currentClusterPhotos.fullDataset.length > MAX_LOADED_PHOTOS) {
        debugLog(`Releasing memory for large photo cluster (${currentClusterPhotos.fullDataset.length} photos)`);
    }
    
    currentClusterPhotos = [];
    currentPhotoIdx = 0;
}

// Show the next photo
function showNextPhoto() {
    if (currentClusterPhotos.length === 0) return;
    
    // Get total number of photos (from full dataset if available)
    const totalPhotos = currentClusterPhotos.fullDataset ? 
        currentClusterPhotos.fullDataset.length : 
        currentClusterPhotos.length;
    
    // If using fullDataset, calculate current photo's actual index in the full set
    let actualIdx = currentPhotoIdx;
    if (currentClusterPhotos.fullDataset) {
        const currentPhoto = currentClusterPhotos[currentPhotoIdx];
        actualIdx = currentClusterPhotos.fullDataset.indexOf(currentPhoto);
    }
    
    // Only increment if we're not at the end
    if (actualIdx < totalPhotos - 1) {
        if (currentClusterPhotos.fullDataset) {
            // In virtual scrolling mode, we need to find the next photo in our loaded subset
            const nextPhoto = currentClusterPhotos.fullDataset[actualIdx + 1];
            // Find this photo in our loaded subset
            const loadedIdx = currentClusterPhotos.findIndex(p => 
                p.id === nextPhoto.id || 
                (p.filename === nextPhoto.filename && 
                 p.latitude === nextPhoto.latitude && 
                 p.longitude === nextPhoto.longitude)
            );
            
            // If found in loaded subset, use that index
            if (loadedIdx >= 0) {
                currentPhotoIdx = loadedIdx;
            } else {
                // Otherwise, we need to add it to our loaded subset
                currentClusterPhotos.push(nextPhoto);
                currentPhotoIdx = currentClusterPhotos.length - 1;
            }
        } else {
            // Simple case, just increment our index
            currentPhotoIdx++;
        }
        
        debugLog(`Moving to next photo: ${currentPhotoIdx + 1}/${totalPhotos}`);
        
        // Set a higher temporary opacity during transition for better visibility
        const photoImg = document.getElementById('photoViewerImg');
        photoImg.style.opacity = '0.95';
        photoImg.style.filter = 'none'; // Ensure no filters are applied during transition
        updatePhotoViewerContent();
    }
}

// Show the previous photo
function showPreviousPhoto() {
    if (currentClusterPhotos.length === 0) return;
    
    // Get total number of photos (from full dataset if available)
    const totalPhotos = currentClusterPhotos.fullDataset ? 
        currentClusterPhotos.fullDataset.length : 
        currentClusterPhotos.length;
    
    // If using fullDataset, calculate current photo's actual index in the full set
    let actualIdx = currentPhotoIdx;
    if (currentClusterPhotos.fullDataset) {
        const currentPhoto = currentClusterPhotos[currentPhotoIdx];
        actualIdx = currentClusterPhotos.fullDataset.indexOf(currentPhoto);
    }
    
    // Only decrement if we're not at the beginning
    if (actualIdx > 0) {
        if (currentClusterPhotos.fullDataset) {
            // In virtual scrolling mode, we need to find the previous photo in our loaded subset
            const prevPhoto = currentClusterPhotos.fullDataset[actualIdx - 1];
            // Find this photo in our loaded subset
            const loadedIdx = currentClusterPhotos.findIndex(p => 
                p.id === prevPhoto.id || 
                (p.filename === prevPhoto.filename && 
                 p.latitude === prevPhoto.latitude && 
                 p.longitude === prevPhoto.longitude)
            );
            
            // If found in loaded subset, use that index
            if (loadedIdx >= 0) {
                currentPhotoIdx = loadedIdx;
            } else {
                // Otherwise, we need to add it to our loaded subset
                // For previous, add at the beginning
                currentClusterPhotos.unshift(prevPhoto);
                currentPhotoIdx = 0;
            }
        } else {
            // Simple case, just decrement our index
            currentPhotoIdx--;
        }
        
        // debugLog(`Moving to previous photo: ${currentPhotoIdx + 1}/${totalPhotos}`);

        // Set a higher temporary opacity during transition for better visibility
        const photoImg = document.getElementById('photoViewerImg');
        photoImg.style.opacity = '0.95';
        photoImg.style.filter = 'none'; // Ensure no filters are applied during transition
        updatePhotoViewerContent();
    }
}
