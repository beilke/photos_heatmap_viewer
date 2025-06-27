/**
 * Map functionality for Photo Heatmap Viewer
 */

// Global map variable
let map;

// Initialize map
function initializeMap() {
    debugLog('Initializing map');
    
    // Create a map with proper handling of world bounds
    map = L.map('map', {
        minZoom: 2,
        maxZoom: 19,
        // Use standard Mercator projection bounds
        maxBounds: [
            [-85.06, -180],  // Southwest corner - precise limit for Mercator projection
            [85.06, 180]     // Northeast corner
        ],
        worldCopyJump: true,  // Enable smoother panning across date line
        maxBoundsViscosity: 1.0,  // Keep the user within bounds
        tap: true, // Always enable tap handler
        dragging: true, // Enable dragging for all devices
        touchZoom: true, // Enable touch zoom
        tapTolerance: 15, // Increased tap tolerance for mobile
        bounceAtZoomLimits: false // Prevent bounce when hitting zoom limits
    }).setView([0, 0], isMobile ? 2 : 2); // Start with a zoomed-out world view

    // Custom wrapper for OpenStreetMap tiles that handles coordinate wrapping properly
    const tileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        subdomains: 'abc',
        minZoom: 2,
        maxZoom: 19,
        noWrap: false,  // Allow wrapping for better UX
        // Custom tile error handler
        errorTileUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
    }).addTo(map);

    // Add event listener to catch and handle tile loading errors
    tileLayer.on('tileerror', function(e) {
        // Prevent console errors for out-of-range tiles
        debugLog(`Tile error suppressed: z=${e.coords.z}, x=${e.coords.x}, y=${e.coords.y}`);
        return true; // Suppress error
    });
}

// Update map visualization with progressive loading
function updateVisualization() {
    debugLog('Updating visualization');

    const loadingStatus = document.createElement('div');
    loadingStatus.className = 'loading-status';
    loadingStatus.style.cssText = `
        position: absolute;
        bottom: 10px;
        right: 10px;
        background-color: rgba(255,255,255,0.9);
        padding: 10px;
        border-radius: 4px;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(loadingStatus);

    try {
        // Use the filterAndUpdateMap function which handles active libraries
        filterAndUpdateMap();
    } catch (err) {
        debugLog('Error updating visualization: ' + err.message);
    } finally {
        // Remove loading status
        if (loadingStatus.parentNode) {
            setTimeout(() => {
                document.body.removeChild(loadingStatus);
            }, 500); // Give some time to see the status
        }
    }
}

// Update heatmap
function updateHeatmap(photos) {
    debugLog('Updating heatmap');

    // Remove existing heatmap if present
    if (heatLayer) {
        map.removeLayer(heatLayer);
    }

    // Create heatmap points with varying intensity based on the slider
    const intensityValue = parseInt(document.getElementById('intensity').value);
    // Use slider value as weight multiplier for each point
    const points = photos.map(photo => [
        photo.latitude,
        photo.longitude,
        intensityValue / 10  // Use intensity slider to affect point weights
    ]);

    debugLog(`Setting heatmap with point weight: ${intensityValue / 10} (from intensity value: ${intensityValue})`);
    
    heatLayer = L.heatLayer(points, {
        radius: parseInt(document.getElementById('radius').value),
        blur: 15,
        maxZoom: 10,
        gradient: { 0.4: 'blue', 0.65: 'lime', 1: 'red' }
        // Note: Leaflet.heat doesn't use an "intensity" param directly, 
        // instead we modify the point weights above
    }).addTo(map);

    debugLog(`Heatmap created with ${points.length} points`);
}

// Function to update only the heatmap without touching markers
function updateHeatmapOnly() {
    debugLog('Updating only heatmap with new settings');
    
    // Get the current filtered data based on active libraries
    const filteredPhotos = filterPhotosByActiveLibraries();
    
    // Update just the heatmap with new intensity/radius
    updateHeatmap(filteredPhotos);
    
    debugLog(`Heatmap updated with intensity=${document.getElementById('intensity').value}, radius=${document.getElementById('radius').value}`);
}

// Function to update only markers without touching heatmap
function updateMarkersOnly() {
    debugLog('Updating only markers');
    
    // Get the current filtered data based on active libraries
    const filteredPhotos = filterPhotosByActiveLibraries();
    
    // Update just the markers
    const showMarkersCheckbox = document.getElementById('showMarkers');
    if (showMarkersCheckbox.checked) {
        // If we already have a marker group, just add it back to the map
        // instead of recreating all markers
        if (markerGroup) {
            if (!map.hasLayer(markerGroup)) {
                debugLog('Showing existing marker group');
                map.addLayer(markerGroup);
                
                // Show feedback to user
                showFeedbackToast('Showing photo markers...');
            }
        } else {
            // Only create new markers if we don't have them already
            updateMarkers(filteredPhotos);
        }
    } else {
        // If markers are turned off, just remove them from the map
        // but keep the marker group in memory
        if (markerGroup && map.hasLayer(markerGroup)) {
            debugLog('Hiding markers');
            map.removeLayer(markerGroup);
            
            // Show feedback to user
            showFeedbackToast('Hiding photo markers...');
        }
    }
}
