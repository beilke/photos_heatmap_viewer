/**
 * Photo viewer functionality for Photo Heatmap Viewer
 */

// Format a date as DD.MM.YYYY HH:MM:SS (24h format)
function formatDateTime(dateStr) {
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            return 'Invalid date';
        }
        
        // Format as DD.MM.YYYY HH:MM:SS
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0'); // Month is 0-indexed
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        
        return `${day}.${month}.${year} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
        console.error('Error formatting date:', e);
        return 'Date format error';
    }
}

// Get location name from coordinates using reverse geocoding
function getLocationNameFromCoordinates(lat, lng) {
    return new Promise((resolve, reject) => {
        try {
            // Check if we have cached this location
            const cacheKey = `${lat.toFixed(4)},${lng.toFixed(4)}`;
            const cachedLocation = sessionStorage.getItem(`location_${cacheKey}`);
            if (cachedLocation) {
                return resolve(cachedLocation);
            }
            
            // Use Nominatim for reverse geocoding
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    let locationName = 'Unknown';
                    
                    if (data && data.address) {
                        const parts = [];
                        
                        // Build location string from city, state, country
                        if (data.address.city || data.address.town || data.address.village) {
                            parts.push(data.address.city || data.address.town || data.address.village);
                        }
                        
                        if (data.address.state) {
                            parts.push(data.address.state);
                        }
                        
                        if (data.address.country) {
                            parts.push(data.address.country);
                        }
                        
                        locationName = parts.join(', ');
                        
                        // Cache this result
                        sessionStorage.setItem(`location_${cacheKey}`, locationName);
                    }
                    
                    resolve(locationName || 'Location not available');
                })
                .catch(err => {
                    console.error('Error in fetch:', err);
                    resolve('Location lookup failed');
                });
        } catch (e) {
            console.error('Error getting location name:', e);
            resolve('Location lookup failed');
        }
    });
}

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
    if (photos.length > MAX_LOADED_PHOTOS) {
        debugLog(`Large cluster detected (${photos.length} photos). Using optimized handling.`);
        
        // For large clusters, only load a subset initially and then load more as needed
        // This prevents performance issues when opening very large clusters
        const initialBatch = photos.slice(0, MAX_LOADED_PHOTOS);
        currentClusterPhotos = initialBatch;
        // Store reference to full dataset for later loading
        currentClusterPhotos.fullDataset = photos;
        debugLog(`Initially loaded ${initialBatch.length}/${photos.length} photos`);
    } else {
        // For smaller clusters, just use all photos directly - no virtual scrolling needed
        debugLog(`Normal sized cluster (${photos.length} photos). Loading all at once.`);
        currentClusterPhotos = photos;
        // Make sure we don't have a fullDataset reference for these
        delete currentClusterPhotos.fullDataset;
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
            <div class="photo-info-label">GPS Coordinates:</div>
            <div id="photoInfoCoordinates"></div>
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
        debugLog(`Cannot update photo viewer: No photo at current index ${currentPhotoIdx}`);
        // Try to recover by resetting to a valid index if possible
        if (currentClusterPhotos.length > 0) {
            currentPhotoIdx = 0;
            debugLog(`Resetting to first photo in cluster`);
            updatePhotoViewerContent();
        }
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
    
    // Track if we're in virtual scrolling mode
    const usingVirtualScroll = !!currentClusterPhotos.fullDataset;
    
    // Need to add 1 for human-readable index (1-based instead of 0-based)
    // First try to find by ID, then fall back to object reference
    let photoIndex = currentPhotoIdx + 1;
    if (usingVirtualScroll) {
        // Try to find by ID first (more reliable)
        const indexById = currentClusterPhotos.fullDataset.findIndex(p => 
            p.id === photo.id
        );
        
        if (indexById >= 0) {
            // Found by ID
            photoIndex = indexById + 1;
            debugLog(`Photo ${photo.id} is #${photoIndex} in full dataset`);
        } else {
            // Fall back to object equality
            const indexByRef = currentClusterPhotos.fullDataset.indexOf(photo);
            if (indexByRef >= 0) {
                photoIndex = indexByRef + 1;
                debugLog(`Photo found by reference at position ${photoIndex}`);
            } else {
                debugLog(`Warning: Could not find photo in full dataset`);
            }
        }
    }
    
    currentPhotoIndex.textContent = photoIndex;
    totalPhotos.textContent = usingVirtualScroll ?
        currentClusterPhotos.fullDataset.length : currentClusterPhotos.length;

    // Reset any existing styles on the photo viewer image
    photoViewerImg.removeAttribute('style');
    photoViewerImg.style.opacity = '0.5'; // Higher initial opacity for better visibility
    
    // Store photo ID for reference (preferred) or fallback to filename
    photoViewerImg.dataset.loadingPhotoId = photo.id || photo.filename;
    
    // Check if this is a HEIC file - they need special handling
    const isHeic = photo.filename.toLowerCase().endsWith('.heic');
    
    // Track image load attempts to prevent multiple requests
    photoViewerImg.dataset.loadAttempts = "0";
    
    // Show loading message for HEIC files
    if (isHeic) {
        // Show a loading toast for HEIC images (they take longer)
        if (typeof showFeedbackToast === 'function') {
            showFeedbackToast('Converting HEIC image...', 3000);
        }
        
        debugLog(`Loading HEIC photo: ${photo.filename} (ID: ${photo.id})`);
        
        // For HEIC files, use only ID without fallback
        if (photo.id) {
            photoViewerImg.src = `/convert/${encodeURIComponent(photo.id)}`;
        } else {
            // If no ID is available (shouldn't happen in normal operation), log a warning and use filename
            debugLog(`Warning: No ID available for HEIC photo: ${photo.filename}`);
            photoViewerImg.src = `/convert/${encodeURIComponent(photo.filename)}`;
        }
    } else {
        // For normal images, use only ID without fallback
        if (photo.id) {
            debugLog(`Loading photo ID: ${photo.id} (${photo.filename})`);
            photoViewerImg.src = `/photos/${encodeURIComponent(photo.id)}?format=jpeg&quality=80`;
        } else {
            // If no ID is available (shouldn't happen in normal operation), log a warning and use filename
            debugLog(`Warning: No ID available for photo: ${photo.filename}`);
            photoViewerImg.src = `/photos/${encodeURIComponent(photo.filename)}?format=jpeg&quality=80`;
        }
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
        }
    };
    
    // Update photo info fields
    const photoInfoFilename = document.getElementById('photoInfoFilename');
    const photoInfoDate = document.getElementById('photoInfoDate');
    const photoInfoCoordinates = document.getElementById('photoInfoCoordinates');
    const photoInfoLocation = document.getElementById('photoInfoLocation');
    const photoInfoPath = document.getElementById('photoInfoPath');
    
    if (photoInfoFilename) {
        photoInfoFilename.textContent = photo.filename || 'Unknown filename';
    }
    
    if (photoInfoDate) {
        photoInfoDate.textContent = photo.datetime ? 
            formatDateTime(photo.datetime) : 
            (photo.date_taken ? formatDateTime(photo.date_taken) : 'Unknown date');
    }
    
    if (photoInfoCoordinates) {
        if (photo.latitude != null && photo.longitude != null) {
            photoInfoCoordinates.textContent = `${photo.latitude.toFixed(6)}, ${photo.longitude.toFixed(6)}`;
        } else {
            photoInfoCoordinates.textContent = 'GPS coordinates unavailable';
        }
    }
    
    // Display location name from coordinates (city, state, country)
    if (photo.latitude != null && photo.longitude != null) {
        getLocationNameFromCoordinates(photo.latitude, photo.longitude)
            .then(locationName => {
                if (photoInfoLocation) {
                    photoInfoLocation.textContent = locationName;
                }
            })
            .catch(err => {
                if (photoInfoLocation) {
                    photoInfoLocation.textContent = 'Location not available';
                }
                console.error('Error getting location name:', err);
            });
    } else if (photoInfoLocation) {
        photoInfoLocation.textContent = 'Location not available';
    }
        
    if (photoInfoPath) {
        photoInfoPath.textContent = photo.full_path || photo.path || 'Path not available';
    }
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
    
    // Track if we're in virtual scrolling mode
    const usingVirtualScroll = !!currentClusterPhotos.fullDataset;
    
    // If using fullDataset, calculate current photo's actual index in the full set
    let actualIdx = currentPhotoIdx;
    let displayIdx = currentPhotoIdx + 1; // 1-based index for display
    
    if (usingVirtualScroll) {
        const currentPhoto = currentClusterPhotos[currentPhotoIdx];
        if (!currentPhoto) {
            debugLog(`Error: Current photo is undefined at index ${currentPhotoIdx}`);
            return;
        }
        
        // Find the current photo in the full dataset by comparing IDs
        actualIdx = currentClusterPhotos.fullDataset.findIndex(p => 
            p.id === currentPhoto.id
        );
        
        // If not found by ID (which should be rare), fall back to object equality
        if (actualIdx < 0) {
            actualIdx = currentClusterPhotos.fullDataset.indexOf(currentPhoto);
            if (actualIdx < 0) {
                debugLog(`Error: Could not find current photo in full dataset`);
                return;
            }
        }
        
        // Use the actual index in the full dataset + 1 for display (1-based)
        displayIdx = actualIdx + 1;
    }
    
    // Only increment if we're not at the end
    if ((usingVirtualScroll && actualIdx < totalPhotos - 1) || 
        (!usingVirtualScroll && currentPhotoIdx < totalPhotos - 1)) {
        
        if (usingVirtualScroll) {
            // In virtual scrolling mode, we need to find the next photo in our loaded subset
            const nextPhoto = currentClusterPhotos.fullDataset[actualIdx + 1];
            if (!nextPhoto) {
                debugLog(`Error: Next photo not found in dataset at index ${actualIdx + 1}`);
                return;
            }
            
            // Find this photo in our loaded subset by ID (most reliable)
            const loadedIdx = currentClusterPhotos.findIndex(p => 
                p.id === nextPhoto.id
            );
            
            // If found in loaded subset, use that index
            if (loadedIdx >= 0) {
                currentPhotoIdx = loadedIdx;
                debugLog(`Found next photo at loaded index ${loadedIdx}`);
            } else {
                // Otherwise, we need to add it to our loaded subset
                currentClusterPhotos.push(nextPhoto);
                currentPhotoIdx = currentClusterPhotos.length - 1;
                debugLog(`Added photo to loaded subset: ${nextPhoto.id || nextPhoto.filename}`);
            }
            
            // Display is based on the position in the full dataset
            debugLog(`Moving to next photo: ${actualIdx + 2}/${totalPhotos}`);
        } else {
            // Simple case, just increment our index
            currentPhotoIdx++;
            debugLog(`Moving to next photo: ${currentPhotoIdx + 1}/${totalPhotos}`);
        }
        
        // Set a higher temporary opacity during transition for better visibility
        const photoImg = document.getElementById('photoViewerImg');
        photoImg.style.opacity = '0.95';
        photoImg.style.filter = 'none'; // Ensure no filters are applied during transition
        updatePhotoViewerContent();
    } else {
        debugLog(`Already at the last photo (${displayIdx}/${totalPhotos})`);
    }
}

// Show the previous photo
function showPreviousPhoto() {
    if (currentClusterPhotos.length === 0) return;
    
    // Get total number of photos (from full dataset if available)
    const totalPhotos = currentClusterPhotos.fullDataset ? 
        currentClusterPhotos.fullDataset.length : 
        currentClusterPhotos.length;
    
    // Track if we're in virtual scrolling mode
    const usingVirtualScroll = !!currentClusterPhotos.fullDataset;
    
    // If using fullDataset, calculate current photo's actual index in the full set
    let actualIdx = currentPhotoIdx;
    let displayIdx = currentPhotoIdx + 1; // 1-based index for display
    
    if (usingVirtualScroll) {
        const currentPhoto = currentClusterPhotos[currentPhotoIdx];
        if (!currentPhoto) {
            debugLog(`Error: Current photo is undefined at index ${currentPhotoIdx}`);
            return;
        }
        
        // Find the current photo in the full dataset by comparing IDs
        actualIdx = currentClusterPhotos.fullDataset.findIndex(p => 
            p.id === currentPhoto.id
        );
        
        // If not found by ID (which should be rare), fall back to object equality
        if (actualIdx < 0) {
            actualIdx = currentClusterPhotos.fullDataset.indexOf(currentPhoto);
            if (actualIdx < 0) {
                debugLog(`Error: Could not find current photo in full dataset`);
                return;
            }
        }
        
        // Use the actual index in the full dataset + 1 for display (1-based)
        displayIdx = actualIdx + 1;
    }
    
    // Only decrement if we're not at the beginning
    if ((usingVirtualScroll && actualIdx > 0) || 
        (!usingVirtualScroll && currentPhotoIdx > 0)) {
        
        if (usingVirtualScroll) {
            // In virtual scrolling mode, we need to find the previous photo in our loaded subset
            const prevPhoto = currentClusterPhotos.fullDataset[actualIdx - 1];
            if (!prevPhoto) {
                debugLog(`Error: Previous photo not found in dataset at index ${actualIdx - 1}`);
                return;
            }
            
            // Find this photo in our loaded subset by ID (most reliable)
            const loadedIdx = currentClusterPhotos.findIndex(p => 
                p.id === prevPhoto.id
            );
            
            // If found in loaded subset, use that index
            if (loadedIdx >= 0) {
                currentPhotoIdx = loadedIdx;
                debugLog(`Found previous photo at loaded index ${loadedIdx}`);
            } else {
                // Otherwise, we need to add it to our loaded subset
                // For previous, add at the beginning
                currentClusterPhotos.unshift(prevPhoto);
                currentPhotoIdx = 0;
                debugLog(`Added photo to loaded subset: ${prevPhoto.id || prevPhoto.filename}`);
            }
            
            // Display is based on the position in the full dataset
            debugLog(`Moving to previous photo: ${actualIdx}/${totalPhotos}`);
        } else {
            // Simple case, just decrement our index
            currentPhotoIdx--;
            debugLog(`Moving to previous photo: ${currentPhotoIdx + 1}/${totalPhotos}`);
        }

        // Set a higher temporary opacity during transition for better visibility
        const photoImg = document.getElementById('photoViewerImg');
        photoImg.style.opacity = '0.95';
        photoImg.style.filter = 'none'; // Ensure no filters are applied during transition
        updatePhotoViewerContent();
    } else {
        debugLog(`Already at the first photo (${displayIdx}/${totalPhotos})`);
    }
}
