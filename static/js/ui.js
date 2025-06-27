/**
 * UI helper functions for Photo Heatmap Viewer
 */

// Initialize UI components
function initializeUI() {
    // Debug panel toggle - only setup for desktop, on mobile it's hidden
    if (!isMobile) {
        const debugPanelToggle = document.getElementById('debugPanelToggle');
        if (debugPanelToggle) {
            debugPanelToggle.addEventListener('click', function () {
                const debugPanel = document.getElementById('debugPanel');
                const toggleIcon = this.querySelector('.toggle-icon');

                if (debugPanel.style.display === 'block') {
                    toggleIcon.textContent = '▲';
                    debugPanel.style.display = 'none';
                } else {
                    toggleIcon.textContent = '▼';
                    debugPanel.style.display = 'block';
                }
            });
        }
    }
    
    // Controls panel toggle
    const controlsToggle = document.getElementById('controlsToggle');
    if (controlsToggle) {
        // Initialize the toggle text based on initial state
        const controlsPanel = document.getElementById('controlsPanel');
        const toggleIcon = controlsToggle.querySelector('.toggle-icon');
        
        // Always ensure toggle is visible
        controlsToggle.style.display = 'flex';
        
        // On mobile, start with panel hidden and update toggle icon
        if (isMobile) {
            controlsPanel.classList.add('hidden');
            toggleIcon.textContent = '▲';
            controlsToggle.setAttribute('aria-expanded', 'false');
            controlsPanelVisible = false;
        }
        
        // Use touchend for mobile and click for desktop
        const toggleEvent = isMobile ? 'touchend' : 'click';
        controlsToggle.addEventListener(toggleEvent, function (e) {
            if (isMobile) {
                e.preventDefault();
                e.stopPropagation(); // Prevent event bubbling
            }
            
            if (controlsPanel.classList.contains('hidden')) {
                controlsPanel.classList.remove('hidden');
                toggleIcon.textContent = '▼';
                this.setAttribute('aria-expanded', 'true');
                controlsPanelVisible = true;
                
                // Adjust panel height based on content
                if (isMobile) {
                    setTimeout(() => {
                        const maxAllowed = window.innerHeight * 0.7;
                        controlsPanel.style.maxHeight = maxAllowed + 'px';
                    }, 50);
                }
            } else {
                controlsPanel.classList.add('hidden');
                toggleIcon.textContent = '▲';
                this.setAttribute('aria-expanded', 'false');
                controlsPanelVisible = false;
            }
        });
    }
    
    // Event listeners
    setupEventListeners();
}

// Setup event listeners for controls
function setupEventListeners() {
    const intensitySlider = document.getElementById('intensity');
    const intensityValueDisplay = document.getElementById('intensityValue');
    const radiusSlider = document.getElementById('radius');
    const radiusValueDisplay = document.getElementById('radiusValue');
    const showMarkersCheckbox = document.getElementById('showMarkers');
    
    // Photo viewer DOM elements
    const closePhotoViewerBtn = document.getElementById('closePhotoViewer');
    
    // Automatically update on intensity change (with debounce to prevent too frequent updates)
    let intensityDebounceTimer;
    
    intensitySlider.addEventListener('input', function() {
        // Update the display value immediately for better user feedback
        intensityValueDisplay.textContent = this.value;
        
        // Debounce the actual map update to avoid performance issues
        clearTimeout(intensityDebounceTimer);
        intensityDebounceTimer = setTimeout(() => {
            debugLog(`Intensity changed to: ${this.value}`);
            // Only update the heatmap, not the markers
            updateHeatmapOnly();
        }, 300);
    });
    
    // Automatically update on radius change (with debounce)
    let radiusDebounceTimer;
    
    radiusSlider.addEventListener('input', function() {
        // Update the display value immediately
        radiusValueDisplay.textContent = this.value;
        
        // Debounce the map update
        clearTimeout(radiusDebounceTimer);
        radiusDebounceTimer = setTimeout(() => {
            debugLog(`Radius changed to: ${this.value}`);
            // Only update the heatmap, not the markers
            updateHeatmapOnly();
        }, 300);
    });

    // Immediately update when "Show Photos Count" checkbox is changed
    showMarkersCheckbox.addEventListener('change', function () {
        debugLog(`Show markers changed: ${this.checked}`);
        
        // Only update markers, not the heatmap
        updateMarkersOnly();
    });
    
    // Photo viewer event listeners
    // Use the appropriate event (touchend for mobile, click for desktop)
    const eventType = isMobile ? 'touchend' : 'click';
    
    closePhotoViewerBtn.addEventListener(eventType, function(e) {
        if (isMobile) e.preventDefault();
        closePhotoViewer();
    });
    
    // Navigation buttons will be created dynamically when the photo viewer is opened
    
    // Keyboard navigation in photo viewer
    document.addEventListener('keydown', function (e) {
        const photoViewerOverlay = document.getElementById('photoViewerOverlay');
        if (photoViewerOverlay.style.display === 'flex') {
            if (e.key === 'Escape') {
                closePhotoViewer();
            } else if (e.key === 'ArrowRight') {
                showNextPhoto();
            } else if (e.key === 'ArrowLeft') {
                showPreviousPhoto();
            }
        }
    });
}

// Helper function to show feedback toast
function showFeedbackToast(message, duration = 1500, isError = false) {
    const feedback = document.createElement('div');
    feedback.className = 'feedback-toast';
    feedback.textContent = message;
    feedback.style.cssText = `
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        background: ${isError ? 'rgba(220,53,69,0.9)' : 'rgba(0,0,0,0.7)'};
        color: white;
        padding: 8px 15px;
        border-radius: 4px;
        font-size: 14px;
        z-index: 1500;
    `;
    document.body.appendChild(feedback);
    
    // Remove feedback after a short delay
    setTimeout(() => feedback.remove(), duration);
}
