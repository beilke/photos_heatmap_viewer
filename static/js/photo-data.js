/**
 * Photo data processing for Photo Heatmap Viewer
 */

// Global variable to store library update times
window.libraryUpdateTimes = {};

// Load photo data
function loadPhotoData() {
    debugLog('Loading photo data');

    // Show loading indicator with progress bar
    const loadingElement = document.getElementById('loading');
    loadingElement.style.display = 'flex';
    const loadingMessage = document.getElementById('loadingMessage');
    const progressBar = document.getElementById('progressBar');
    
    // Initialize loading state
    loadingMessage.textContent = 'Fetching photo data...';
    progressBar.style.width = '10%';
    // Use the new API endpoint for markers
    fetch('/api/markers')
        .then(response => {
            debugLog(`Response status: ${response.status}`);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.text().then(text => {
                try {
                    return JSON.parse(text);
                } catch (e) {
                    debugLog(`JSON parse error: ${e.message}`);
                    debugLog(`JSON content (first 200 chars): ${text.substring(0, 200)}`);
                    throw new Error(`JSON parse error: ${e.message}`);
                }
            });
        }).then(data => {
            // Handle both new and legacy JSON formats
            let photos = [];
            let libraries = [];

            if (Array.isArray(data)) {
                // Legacy format (just an array of photos)
                photos = data;
                debugLog(`Loaded ${photos.length} photos (legacy format)`);
            } else {
                // New format with photos and libraries
                photos = data.photos || [];
                libraries = data.libraries || [];
                debugLog(`Loaded ${photos.length} photos from ${libraries.length} libraries`);

                // Log libraries if available
                if (libraries.length > 0) {
                    debugLog(`Available libraries: ${libraries.map(lib => lib.name).join(', ')}`);
                }
            }

            // Store data globally
            photoData = {
                photos: photos,
                libraries: libraries,
                activeLibraries: libraries.map(lib => lib.id) // Start with all libraries active
            };

            // Create library filter controls
            createLibraryFilters(libraries);

            // Count photos with GPS coords
            const withGPS = photos.filter(photo =>
                photo.latitude != null && photo.longitude != null);
            debugLog(`Photos with GPS: ${withGPS.length}/${photos.length}`);

            // Update photo count display
            const photoCountElement = document.getElementById('photoCount');
            photoCountElement.textContent = `${withGPS.length} photos with location`;

            // Unified loading sequence with progress updates
            // Update loading state (30% progress)
            progressBar.style.width = '30%';
            loadingMessage.textContent = 'Processing photo data...';
            
            setTimeout(() => {
                // Step 1: Create heatmap (50% progress)
                loadingMessage.textContent = 'Creating heatmap...';
                progressBar.style.width = '50%';
                
                updateHeatmap(withGPS);
                if (withGPS.length > 0) {
                    try {
                        // Group points by which side of the antimeridian they fall on
                        const western = [];
                        const eastern = [];
                        
                        withGPS.forEach(photo => {
                            // Clamp latitude to Mercator projection limits
                            const lat = Math.max(-85.06, Math.min(85.06, photo.latitude));
                            // Normalize longitude 
                            const lng = ((photo.longitude + 180) % 360) - 180;
                            
                            // Group points by hemisphere to detect antimeridian crossings
                            if (lng < 0) {
                                western.push([lat, lng]);
                            } else {
                                eastern.push([lat, lng]);
                            }
                        });
                        
                        // Handle antimeridian crossing (points on both sides of the world)
                        // If we have significant numbers of points in both hemispheres, zoom out to global view
                        const hasAntimeridianCrossing = 
                            western.length > withGPS.length * 0.1 && 
                            eastern.length > withGPS.length * 0.1;
                        
                        if (hasAntimeridianCrossing) {
                            map.setView([0, 0], 2);
                        } else {
                            const points = withGPS.map(photo => [
                                photo.latitude,
                                ((photo.longitude + 180) % 360) - 180
                            ]);
                            
                            // Calculate bounds
                            const bounds = L.latLngBounds(points);
                            
                            // Ensure bounds are valid and not too small
                            if (bounds.isValid() && bounds.getNorth() - bounds.getSouth() > 0.01) {
                                debugLog(`Fitting map to bounds: ${bounds.toBBoxString()}`);
                                // Add safety check for very wide bounds
                                const isVeryWide = (bounds.getEast() - bounds.getWest()) > 270;
                                
                                // If bounds are too wide (nearly global), use a global view
                                if (isVeryWide) {
                                    debugLog('Bounds too wide, using global view');
                                    map.setView([0, 0], 2);
                                } else {
                                    // Otherwise fit to the calculated bounds
                                    map.fitBounds(bounds, { 
                                        padding: [50, 50],
                                        maxZoom: 12, // Prevent zooming in too far on small clusters
                                        animate: true,
                                        duration: 1 // quick animation
                                    });
                                }
                            } else {
                                // Fallback to default view if bounds are invalid or too small
                                debugLog('Invalid or too small bounds, using default view');
                                map.setView([0, 0], 2);
                            }
                        }
                    } catch (e) {
                        debugLog(`Error fitting bounds: ${e.message}`);
                        // Fallback to a safe default view
                        map.setView([0, 0], 2);
                    }
                }
                
                // Step 2: Add markers (70% progress)
                setTimeout(() => {
                    loadingMessage.textContent = 'Adding photo markers...';
                    progressBar.style.width = '70%';
                    
                    if (document.getElementById('showMarkers').checked) {
                        // The updateMarkers function will handle the rest of the loading process
                        updateMarkers(withGPS);
                    } else {
                        // If markers not shown, complete loading
                        progressBar.style.width = '95%';
                        loadingMessage.textContent = 'Finalizing...';
                        
                        // Finish loading after a brief delay to show progress
                        setTimeout(() => {
                            progressBar.style.width = '100%';
                            loadingMessage.textContent = 'Complete!';
                            
                            // Hide the loading screen after a small delay
                            setTimeout(() => {
                                loadingElement.style.display = 'none';
                            }, 500);
                        }, 300);
                    }
                }, 100);
            }, 100);
        })
        .catch(error => {
            debugLog(`Error loading photo data: ${error.message}`);
            loadingElement.innerHTML = `
                <h2>Error Loading Data</h2>
                <p>${error.message}</p>
                <p class="error-hint">Press F5 to refresh the page</p>
            `;
        });
}

// Filter photos by currently active libraries
function filterPhotosByActiveLibraries() {
    if (!photoData || !photoData.photos || photoData.photos.length === 0) {
        debugLog('No photo data available to filter');
        return [];
    }
    
    // If we don't have library info, just return all photos
    if (!photoData.libraries || !photoData.activeLibraries) {
        return photoData.photos.filter(photo => 
            photo.latitude != null && photo.longitude != null
        );
    }
    
    // Filter by active libraries
    return photoData.photos.filter(photo => {
        // Filter out photos without GPS
        if (photo.latitude == null || photo.longitude == null) {
            return false;
        }
        
        // If no library_id, include it if we don't have library filters
        if (photo.library_id == null) {
            return true;
        }
        
        // Otherwise, check if photo's library is active
        return photoData.activeLibraries.includes(photo.library_id);
    });
}

// Create library filters
function createLibraryFilters(libraries) {
    const container = document.getElementById('libraryFilterContainer');
    const selectAllCheckbox = document.getElementById('selectAllLibraries');

    // Clear any existing filters
    container.innerHTML = '';

    if (!libraries || libraries.length === 0) {
        container.innerHTML = '<p>No libraries available</p>';
        return;
    }

    // Add individual library checkboxes
    libraries.forEach(library => {
        const libraryPhotos = photoData.photos.filter(photo => photo.library_id === library.id);
        const geotaggedCount = libraryPhotos.filter(photo =>
            photo.latitude != null && photo.longitude != null).length;

        const div = document.createElement('div');
        div.className = 'library-checkbox checkbox-container';
        div.style.marginLeft = '0';
        div.style.paddingLeft = '0';

        // Create checkbox input
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'library-filter';
        checkbox.id = `library-${library.id}`;
        checkbox.checked = true; // All libraries start checked
        checkbox.dataset.libraryId = library.id;

        // Create label with library name and count
        const label = document.createElement('label');
        label.htmlFor = checkbox.id;
        label.className = 'library-label';

        // Add library name text node
        const nameText = document.createTextNode(`${library.name} `);

        // Add count in parentheses
        const countSpan = document.createElement('span');
        countSpan.className = 'library-count';
        countSpan.textContent = `(${geotaggedCount} photos)`;

        // Build the label structure
        label.appendChild(nameText);
        label.appendChild(countSpan);

        // Build the checkbox div
        div.appendChild(checkbox);
        div.appendChild(label);

        // Add to container
        container.appendChild(div);

        // Add event listener
        checkbox.addEventListener('change', updateLibrarySelection);
    });

    // Add "Select All" functionality
    selectAllCheckbox.addEventListener('change', function() {
        const isChecked = selectAllCheckbox.checked;
        document.querySelectorAll('.library-filter').forEach(cb => {
            cb.checked = isChecked;
        });
        updateLibrarySelection();
    });

    // Initial update
    updateLibrarySelection();

    // Apply tooltips to library labels if we have update times available
    if (window.libraryUpdateTimes && Object.keys(window.libraryUpdateTimes).length > 0) {
        updateLibraryLabelsWithTooltips();
    } else {
        // Schedule tooltip update for when library times become available
        debugLog('Library update times not yet available, will apply tooltips later');
        setTimeout(updateLibraryLabelsWithTooltips, 2000); // Try again in 2 seconds
    }
}

// Update library selection
function updateLibrarySelection() {
    // Update which libraries are selected
    const selectedLibraries = [];
    document.querySelectorAll('.library-filter:checked').forEach(checkbox => {
        selectedLibraries.push(parseInt(checkbox.dataset.libraryId));
    });

    photoData.activeLibraries = selectedLibraries;

    // Update the "Select All" checkbox state
    const allLibrariesCheckbox = document.getElementById('selectAllLibraries');
    const allLibraries = document.querySelectorAll('.library-filter');
    const selectedCount = document.querySelectorAll('.library-filter:checked').length;

    if (selectedCount === 0) {
        allLibrariesCheckbox.checked = false;
        allLibrariesCheckbox.indeterminate = false;
    } else if (selectedCount === allLibraries.length) {
        allLibrariesCheckbox.checked = true;
        allLibrariesCheckbox.indeterminate = false;
    } else {
        allLibrariesCheckbox.indeterminate = true;
    }

    // Show the main loading indicator when updating library selection
    // because this is a substantial operation that recreates markers
    const loadingElement = document.getElementById('loading');
    const loadingMessage = document.getElementById('loadingMessage');
    const progressBar = document.getElementById('progressBar');
    
    if (loadingElement && loadingMessage && progressBar) {
        loadingElement.style.display = 'flex';
        loadingMessage.textContent = 'Updating library selection...';
        progressBar.style.width = '30%';
        
        // Use setTimeout to allow the UI to update before heavy processing
        setTimeout(() => {
            // Update progress to show we're working on the heatmap
            progressBar.style.width = '50%';
            loadingMessage.textContent = 'Updating heatmap...';
            
            setTimeout(() => {
                // Force recreation of markers for library changes
                if (markerGroup) {
                    debugLog('Clearing existing markers for library selection change');
                    map.removeLayer(markerGroup);
                    markerGroup = null; // Force recreation of markers
                }
                
                // For library selection we need to update all visualizations
                // because it changes the underlying dataset
                // Set a flag to indicate we're processing library selection
                window._processingLibrarySelection = true;
                filterAndUpdateMap();
                
                // We don't complete the progress here because filterAndUpdateMap 
                // will trigger updateMarkers which will handle progress completion
                // The progress completion is now managed by the marker loading process
            }, 50);
        }, 50);
    } else {
        // Fallback if progress elements aren't found
        debugLog(`Library selection changed, updating map...`);
        filterAndUpdateMap();
    }
}

// Filter and update the map based on selected libraries
function filterAndUpdateMap() {
    if (!photoData || !photoData.photos) return;

    const loadingElement = document.getElementById('loading');
    const progressBar = document.getElementById('progressBar');
    const loadingMessage = document.getElementById('loadingMessage');
    
    // Check if progress is already showing (called from updateLibrarySelection)
    const progressAlreadyShowing = loadingElement && loadingElement.style.display === 'flex';
    
    // Show progress if not already showing
    if (!progressAlreadyShowing && loadingElement) {
        loadingElement.style.display = 'flex';
        if (progressBar) progressBar.style.width = '20%';
        if (loadingMessage) loadingMessage.textContent = 'Filtering photos...';
    }

    // Get all photos from active libraries
    let filteredPhotos = photoData.photos.filter(photo =>
        photoData.activeLibraries.includes(photo.library_id) &&
        photo.latitude != null && photo.longitude != null
    );

    debugLog(`Filtered to ${filteredPhotos.length} photos from ${photoData.activeLibraries.length} libraries`);
    
    // Update photo count display
    const photoCountElement = document.getElementById('photoCount');
    photoCountElement.textContent = `${filteredPhotos.length} photos with location`;

    // Update progress - heatmap step
    if (!progressAlreadyShowing && progressBar) {
        progressBar.style.width = '50%';
        if (loadingMessage) loadingMessage.textContent = 'Updating heatmap...';
    }

    // Update heatmap
    updateHeatmap(filteredPhotos);
    
    // Update progress - marker step
    if (!progressAlreadyShowing && progressBar) {
        progressBar.style.width = '70%';
        if (loadingMessage) loadingMessage.textContent = 'Updating markers...';
    }
    
    // Handle markers differently depending on context
    const showMarkersCheckbox = document.getElementById('showMarkers');
    if (showMarkersCheckbox.checked) {
        // When updating from library selection, we need to recreate markers 
        // to reflect the new filtered dataset
        const fromLibrarySelection = 
            document.getElementById('loadingMessage') && 
            document.getElementById('loadingMessage').textContent && 
            document.getElementById('loadingMessage').textContent.includes('library');
        
        if (fromLibrarySelection || !markerGroup) {
            // If coming from library selection or no marker group exists yet,
            // create new markers with filtered data
            debugLog('Recreating markers for library selection change');
            
            // First remove existing markers if any
            if (markerGroup && map.hasLayer(markerGroup)) {
                map.removeLayer(markerGroup);
                markerGroup = null; // Force recreation
            }
            
            // Then create new markers with the filtered data
            updateMarkers(filteredPhotos);
        } else if (markerGroup) {
            // For other updates, just add the existing marker group if needed
            if (!map.hasLayer(markerGroup)) {
                debugLog('Showing existing marker group');
                map.addLayer(markerGroup);
            }
        }
    } else if (markerGroup && map.hasLayer(markerGroup)) {
        // Just hide markers if they're toggled off
        debugLog('Removing markers during complete refresh');
        map.removeLayer(markerGroup);
    }
    
    // Only complete progress if we're not going to load markers
    // (which has its own progress handling)
    if (!showMarkersCheckbox.checked && !progressAlreadyShowing && loadingElement) {
        progressBar.style.width = '100%';
        loadingMessage.textContent = 'Complete!';
        
        // Hide after a short delay
        setTimeout(() => {
            loadingElement.style.display = 'none';
        }, 500);
    }
    // Otherwise, let the marker loading handle the progress completion
}

// Function to fetch library update times
function fetchLibraryUpdateTimes() {
    debugLog('Fetching library update times');
    fetch('/library_updates')
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            if (data && data.updates) {
                window.libraryUpdateTimes = data.updates;
                debugLog('Library update times loaded successfully');
                
                // Only update tooltips if libraries have already been loaded
                if (photoData && photoData.libraries && photoData.libraries.length > 0) {
                    updateLibraryLabelsWithTooltips();
                } else {
                    debugLog('Libraries not yet loaded, will apply tooltips later');
                }
            }
        })
        .catch(error => {
            debugLog(`Error loading library update times: ${error.message}`);
            // Schedule a retry in 30 seconds if this was the initial load
            if (!window._libraryTimesRetried) {
                window._libraryTimesRetried = true;
                setTimeout(fetchLibraryUpdateTimes, 30000);
            }
        });
}

// Function to update library labels with tooltips
// Helper function to format date time for tooltips
function formatDateTime(dateTimeStr) {
    try {
        const date = new Date(dateTimeStr);
        // Check if we have a valid date
        if (isNaN(date.getTime())) {
            return dateTimeStr; // Return as-is if invalid
        }
        
        return date.toLocaleString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        debugLog(`Error formatting date: ${e.message}`);
        return dateTimeStr; // Return original string on error
    }
}

function updateLibraryLabelsWithTooltips() {
    if (!window.libraryUpdateTimes || Object.keys(window.libraryUpdateTimes).length === 0) {
        debugLog('No library update times available for tooltips');
        return; 
    }

    let updateCount = 0;
    // Find all library labels and update them with tooltip data
    document.querySelectorAll('.library-label').forEach(label => {
        // Extract library name more carefully - handle cases with spaces in names
        const fullText = label.textContent.trim();
        const matches = fullText.match(/^(.*?)\s+\(\d+\s+photos\)$/);
        const libraryName = matches ? matches[1].trim() : fullText.split(' ')[0];
        
        if (window.libraryUpdateTimes && window.libraryUpdateTimes[libraryName]) {
            const updateTime = window.libraryUpdateTimes[libraryName];
            label.setAttribute('data-update-time', updateTime);
            label.setAttribute('title', `Last updated: ${formatDateTime(updateTime)}`);
            updateCount++;
        }
    });
    
    if (updateCount > 0) {
        debugLog(`Updated ${updateCount} library labels with update times`);
    }
}
