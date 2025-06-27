/**
 * Marker handling functionality for Photo Heatmap Viewer
 */

// Update markers
function updateMarkers(inputPhotos = []) {
    // Check if we already logged this - prevents duplicate messages
    if (!window._markerUpdateInProgress) {
        window._markerUpdateInProgress = true;
        debugLog('Updating markers');
    }

    // Deduplicate photos
    const photoMap = new Map();
    inputPhotos.forEach(photo => {
        const photoKey = photo.id || `${photo.latitude}_${photo.longitude}_${photo.filename}`;
        if (!photoMap.has(photoKey)) {
            photoMap.set(photoKey, photo);
        }
    });
    const uniquePhotos = Array.from(photoMap.values());
    const dupesRemoved = inputPhotos.length - uniquePhotos.length;

    if (dupesRemoved > 0) {
        debugLog(`Removed ${dupesRemoved} duplicate photos before creating markers`);
    }

    const filteredPhotos = uniquePhotos;
    
    // Check if we've already logged this information to avoid duplicates
    if (!window._markerLoadingLogged) {
        window._markerLoadingLogged = true;
        debugLog(`Loading markers for ${filteredPhotos.length} unique photos...`);
    }

    // Update the main loading indicator instead of creating a new one
    const loadingElement = document.getElementById('loading');
    const loadingMessage = document.getElementById('loadingMessage');
    const progressBar = document.getElementById('progressBar');
    
    // Make sure loading indicator is visible
    if (loadingElement) {
        loadingElement.style.display = 'flex';
    }
    
    if (loadingMessage) {
        loadingMessage.textContent = 'Loading markers...';
    }
    
    if (progressBar) {
        progressBar.style.width = '70%';
    }

    // Remove old markers
    if (typeof markerGroup !== 'undefined' && markerGroup) {
        map.removeLayer(markerGroup);
        markerGroup = null; // Explicitly null it out to ensure full recreation
    }

    // Create new marker group
    try {
        markerGroup = typeof L.markerClusterGroup === 'function'
            ? L.markerClusterGroup({
                // Configure cluster group to properly count markers
                iconCreateFunction: function(cluster) {
                    // Get all child markers in this cluster
                    const markers = cluster.getAllChildMarkers();
                    
                    // Deduplicate based on unique locations
                    const uniqueLocations = new Map();
                    markers.forEach(marker => {
                        if (marker.photoData) {
                            const photo = marker.photoData;
                            const locationKey = `${photo.latitude.toFixed(6)}_${photo.longitude.toFixed(6)}`;
                            
                            // Use full path as secondary key if available
                            const photoKey = photo.path || photo.full_path || 
                                `${locationKey}_${photo.filename}`;
                            
                            if (!uniqueLocations.has(photoKey)) {
                                uniqueLocations.set(photoKey, true);
                            }
                        }
                    });
                    
                    // Get accurate count of unique photos
                    const count = uniqueLocations.size;
                    debugLog(`Cluster has ${count} unique photos out of ${markers.length} markers`);
                    
                    // Use Leaflet.markercluster's default icon creation with our corrected count
                    const childCount = count;
                    
                    let c = ' marker-cluster-';
                    if (childCount < 10) {
                        c += 'small';
                    } else if (childCount < 100) {
                        c += 'medium';
                    } else {
                        c += 'large';
                    }
                    
                    return new L.DivIcon({
                        html: '<div><span>' + childCount + '</span></div>',
                        className: 'marker-cluster' + c,
                        iconSize: new L.Point(40, 40)
                    });
                }
            })
            : L.layerGroup();

        // We don't add the clusterclick handler here anymore
        // The handler is added once after all markers are created
        // to prevent duplicates and ensure proper behavior
    } catch (err) {
        debugLog('Error creating marker group: ' + err.message);
        markerGroup = L.layerGroup();
    }

    // Process markers (chunked if large dataset)
    const chunkSize = 100;
    let currentChunk = 0;
    
    // Handle empty filtered photos case
    if (filteredPhotos.length === 0) {
        debugLog('No photos with GPS data to display');
        loadingMessage.textContent = 'No photos with GPS data to display';
        
        // Staged progress for better UX
        progressBar.style.width = '90%';
        
        // Briefly show the message, then finish loading
        setTimeout(() => {
            progressBar.style.width = '100%';
            loadingMessage.textContent = 'Complete!';
            
            // Hide loading screen after a short delay
            setTimeout(() => {
                const loadingElement = document.getElementById('loading');
                if (loadingElement) {
                    loadingElement.style.display = 'none';
                }
            }, 800);
        }, 800);
        return;
    }
    
    const totalChunks = Math.ceil(filteredPhotos.length / chunkSize);

    function processChunk() {
        const start = currentChunk * chunkSize;
        const end = Math.min(start + chunkSize, filteredPhotos.length);

        for (let i = start; i < end; i++) {
            addMarker(filteredPhotos[i]);
        }

        // Calculate percentage completed and adjust scale to fit in 70-95% range
        // Only going to 95% to leave the last 5% for the final rendering
        const percentComplete = Math.min(100, Math.round((end / filteredPhotos.length) * 100));
        loadingMessage.textContent = `Loading markers: ${percentComplete}%`;
        
        // Scale from 70-95% for marker loading instead of going straight to 100%
        // This leaves room for the final marker rendering step
        const progressWidth = 70 + (percentComplete * 0.25); // Progress from 70% to 95%
        progressBar.style.width = `${progressWidth}%`;

        currentChunk++;
        if (currentChunk < totalChunks) {
            setTimeout(processChunk, 20);
        } else {
            finishMarkerLoading();
        }
    }

    if (filteredPhotos.length > 500) {
        // Only log the chunked processing message if we haven't already
        if (!window._chunkedProcessingLogged) {
            window._chunkedProcessingLogged = true;
            debugLog(`Using chunked processing for ${filteredPhotos.length} markers`);
        }
        processChunk();
    } else {
        if (filteredPhotos.length > 0) {
            // For smaller batches, show that we're at 80% progress while processing
            loadingMessage.textContent = `Loading ${filteredPhotos.length} markers...`;
            progressBar.style.width = '80%';
            
            // Small delay to ensure the UI updates before potentially heavy processing
            setTimeout(() => {
                filteredPhotos.forEach(photo => addMarker(photo));
                finishMarkerLoading();
            }, 50);
        } else {
            finishMarkerLoading();
        }
    }

    function addMarker(photo) {
        if (photo.latitude == null || photo.longitude == null) {
            debugLog(`Skipping photo with invalid coordinates: ${photo.filename}`);
            return;
        }

        const marker = L.marker([photo.latitude, photo.longitude]);
        marker.photoData = photo;

        const container = document.createElement('div');
        container.className = 'marker-popup';
        container.innerHTML = `
            <strong>${photo.filename || 'Unknown'}</strong><br>
            ${photo.datetime ? new Date(photo.datetime).toLocaleString() : 'No date'}<br>
            <div class="popup-image-container" style="width: 150px; height: 150px; background: #f0f0f0; display: flex; align-items: center; justify-content: center;">
                <span class="loading-placeholder">Loading...</span>
            </div>
        `;

        marker.bindPopup(container);

        marker.on('popupopen', function () {
            const imageContainer = container.querySelector('.popup-image-container');
            if (!imageContainer.querySelector('img')) {
                const img = new Image();
                img.style.maxWidth = '150px';
                img.style.maxHeight = '150px';

                img.onload = function () {
                    imageContainer.innerHTML = '';
                    imageContainer.appendChild(img);
                };

                img.onerror = function () {
                    imageContainer.innerHTML = 'Image not available';
                    debugLog(`Failed to load popup image for ${photo.filename}`);
                };

                img.src = `/photos/${encodeURIComponent(photo.filename)}`;
            }
        });

        marker.on('click', function (e) {
            // Find all photos at exactly the same coordinates using what's available in photoData
            // rather than depending on the outer scope's filteredPhotos
            const currentPhotos = filterPhotosByActiveLibraries();
            let photosAtSameLocation = currentPhotos.filter(p =>
                p.latitude === photo.latitude && p.longitude === photo.longitude
            );

            // Log the found photos for verification
            debugLog(`Found ${photosAtSameLocation.length} photos at location ${photo.latitude},${photo.longitude}`);
            
            const locationMap = new Map();
            photosAtSameLocation.forEach(p => {
                // Create a more precise unique key including coordinates
                const key = p.id || `${p.filename}_${p.latitude}_${p.longitude}`;
                if (!locationMap.has(key)) {
                    // Ensure all path info is available
                    if (p.path && !p.full_path) {
                        p.full_path = p.path;
                    }
                    locationMap.set(key, p);
                    debugLog(`Location photo: ${p.filename}`);
                }
            });
            photosAtSameLocation = Array.from(locationMap.values());

            debugLog(`Marker clicked: ${photo.filename} (${photosAtSameLocation.length} unique photos at this location)`);

            const index = photosAtSameLocation.findIndex(p =>
                p.id === photo.id || p.filename === photo.filename
            );

            openPhotoViewer(photosAtSameLocation, index >= 0 ? index : 0);
            e.originalEvent?.stopPropagation();
            L.DomEvent.stopPropagation(e);
        });

        markerGroup.addLayer(marker);
    }

    // Track if finishMarkerLoading has already run to prevent duplicate logging
    let markerFinishComplete = false;
    
    function finishMarkerLoading() {
        // Only add the layer if it's not already on the map
        if (markerGroup && !map.hasLayer(markerGroup)) {
            map.addLayer(markerGroup);
        }
        
        // Add the cluster click handler here to ensure it's only added once
        // after all markers are processed
        if (markerGroup && markerGroup.on) {
            // Remove any existing handlers first to prevent duplicates
            if (typeof markerGroup.off === 'function') {
                markerGroup.off('clusterclick');
            }
            
            // Add our handler with proper photo filtering
            markerGroup.on('clusterclick', function (e) {
                try {
                    const cluster = e.layer;
                    const markers = cluster.getAllChildMarkers();
                    const clusterCount = markers.length;
                    
                    debugLog(`Cluster clicked: ${clusterCount} markers`);
                    
                    // Collect all photos from all markers in this cluster
                    let allPhotos = [];
                    
                    // Process only the markers in this specific cluster
                    markers.forEach(marker => {
                        if (marker.photoData) {
                            const photo = marker.photoData;
                            
                            // Ensure all path info is available for verification
                            if (photo.path && !photo.full_path) {
                                photo.full_path = photo.path;
                            }
                            
                            // Add this photo to our collection
                            allPhotos.push(photo);
                            debugLog(`Cluster photo: ${photo.filename}, lat/long: ${photo.latitude}/${photo.longitude}`);
                        }
                    });
                    
                    // Deduplicate photos using a more robust approach
                    if (allPhotos.length > 0) {
                        debugLog(`Deduplicating ${allPhotos.length} photos from cluster...`);
                        
                        // Use a Map to deduplicate photos with a more unique key
                        const photoMap = new Map();
                        allPhotos.forEach(photo => {
                            // Create a more robust unique key using filename and path if available
                            const photoKey = photo.path || photo.full_path || 
                                            `${photo.filename}_${photo.latitude.toFixed(6)}_${photo.longitude.toFixed(6)}`;
                            if (!photoMap.has(photoKey)) {
                                photoMap.set(photoKey, photo);
                                debugLog(`Added unique photo: ${photo.filename} (key: ${photoKey})`);
                            } else {
                                debugLog(`Skipping duplicate: ${photo.filename} (key: ${photoKey})`);
                            }
                        });
                        
                        allPhotos = Array.from(photoMap.values());
                        debugLog(`After deduplication: ${allPhotos.length} unique photos`);
                    }
                    
                    if (allPhotos.length > 0) {
                        debugLog(`Opening viewer with ${allPhotos.length} unique photos from cluster`);
                        openPhotoViewer(allPhotos, 0);
                    }
                } catch (err) {
                    debugLog('Error in cluster click handler: ' + err.message);
                }
            });
        }
        
        // Update progress only at the very end when markers are actually added to the map
        progressBar.style.width = '100%';
        loadingMessage.textContent = 'Complete!';
        
        // Only log success message if we haven't already done so
        if (!window._markerSuccessLogged) {
            debugLog('Successfully added markers to map');
            window._markerSuccessLogged = true;
        }
        
        // Clean up flags
        if (window._processingLibrarySelection) {
            window._processingLibrarySelection = false;
        }
        
        // Reset the marker update tracking flags except success message
        window._markerUpdateInProgress = false;
        window._markerLoadingLogged = false;
        window._chunkedProcessingLogged = false;
        
        // Reset the success message flag after a short delay
        // This ensures we don't get duplicate messages in quick succession
        // but allows new messages when the user performs a new action
        setTimeout(() => {
            window._markerSuccessLogged = false;
        }, 1000);
        
        // Hide loading screen after a short delay - slightly longer to ensure
        // users see the 100% state before it disappears
        setTimeout(() => {
            const loadingElement = document.getElementById('loading');
            if (loadingElement) {
                loadingElement.style.display = 'none';
            }
        }, 800);
    }
}
