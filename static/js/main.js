/**
 * Main JavaScript file for Photo Heatmap Viewer
 */

// Global variables
let photoData = [];
let filteredData = [];
let heatLayer = null;
let markerGroup = null;

// Photo viewer variables
let currentClusterPhotos = [];
let currentPhotoIdx = 0;

// Track visibility states (helps with orientation changes)
let controlsPanelVisible = false;

// Initialize the application when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Apply mobile-specific settings immediately
    if (isMobile) {
        applyMobileSettings();
    }
    
    // Setup error handlers
    setupErrorHandlers();
    
    // Initialize the UI and map
    initializeUI();
    initializeMap();
    
    // First fetch library update times to ensure we have this data available
    // before loading photos
    fetchLibraryUpdateTimes();
    
    // Then load the photo data
    loadPhotoData();
    
    // Schedule regular updates for library update times
    setInterval(fetchLibraryUpdateTimes, 60000); // Update every minute
});

// Apply mobile-specific settings
function applyMobileSettings() {
    document.body.classList.add('mobile-device');
    
    // Set controls container position immediately
    const controlsContainer = document.querySelector('.controls-container');
    if (controlsContainer) {
        controlsContainer.style.position = 'fixed';
        controlsContainer.style.bottom = '0';
        controlsContainer.style.top = 'auto';
        controlsContainer.style.left = '0';
        controlsContainer.style.right = '0';
        controlsContainer.style.width = '100%';
        controlsContainer.style.zIndex = '1001';
    }
    
    // Hide debug panel and toggle on mobile devices
    const debugPanelContainer = document.querySelector('.debug-panel-container');
    if (debugPanelContainer) {
        debugPanelContainer.style.display = 'none';
    }
    
    // Improve touch handling
    // Fix map dragging issues by preventing unwanted touch event handling
    document.addEventListener('touchmove', function(e) {
        // Allow touch events inside controls and modals
        if (e.target.closest('.controls') || 
            e.target.closest('.debug-panel') || 
            e.target.closest('.photo-viewer-container')) {
            return; // Don't interfere with scrolling in controls
        }
        
        // Let map handle all its own touch events
        if (e.target.closest('#map') || e.target.closest('.leaflet-container')) {
            // Don't preventDefault - let Leaflet handle its own events
            return;
        }
    }, { passive: true });
    
    // Ensure map gets proper touch events
    const mapElement = document.getElementById('map');
    if (mapElement) {
        // Force map to handle touch events properly
        mapElement.style.touchAction = 'none';
    }
}

// Setup error handlers
function setupErrorHandlers() {
    // Catch all errors
    window.addEventListener('error', function (e) {
        debugLog('ERROR: ' + e.message);
        return false;
    });

    // Handle runtime.lastError in browsers
    // This is needed to suppress "Unchecked runtime.lastError" messages
    window.addEventListener('error', function(e) {
        // Check if it's a runtime.lastError
        if (e && e.message && e.message.includes('runtime.lastError')) {
            // Suppress the error
            e.stopPropagation();
            return true; // Prevents the error from showing in console
        }
    });
}

// Handle device orientation changes and resizing
function handleViewportChange() {
    // Add a small delay to allow the browser to complete the orientation change
    setTimeout(function() {
        map.invalidateSize();
        
        // Make sure our toggle is still visible after orientation change
        const controlsToggle = document.getElementById('controlsToggle');
        if (controlsToggle) {
            controlsToggle.style.display = 'flex'; // Ensure toggle is visible
        }
        
        // Update the controls panel display based on our tracking variable
        const controlsPanel = document.getElementById('controlsPanel');
        if (controlsPanel) {
            controlsPanel.style.display = controlsPanelVisible ? 'block' : 'none';
        }
        
        // Ensure controls container is at the bottom in mobile view
        if (isMobile) {
            const controlsContainer = document.querySelector('.controls-container');
            if (controlsContainer) {
                controlsContainer.style.bottom = '0';
                controlsContainer.style.top = 'auto';
            }
        }
        
        debugLog('Viewport changed, map and controls updated');
    }, 300);
}

// Listen for both orientation and resize changes
window.addEventListener('orientationchange', handleViewportChange);
window.addEventListener('resize', handleViewportChange);
