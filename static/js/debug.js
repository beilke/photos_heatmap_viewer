/**
 * Debug logging functionality for Photo Heatmap Viewer
 */

// Detect if we're on mobile (defined early so we can use it everywhere)
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth < 768;

// Messages to filter out from debug logs
const filteredDebugMessages = [
    'library labels with update times',
    'Fetching library update times',
    'Library update times loaded successfully'
];

// Helper to check if a message should be filtered
function shouldFilterMessage(message) {
    return filteredDebugMessages.some(filter => message.includes(filter));
}

// Debug logging function - defined based on device type
let debugLog;
if (isMobile) {
    // Simpler logging for mobile (console only)
    debugLog = function(message, data) {
        // Skip filtered messages
        if (shouldFilterMessage(message)) return;
        
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] ${message}`, data || '');
    };
} else {
    // Full logging with UI panel for desktop
    debugLog = function(message, data) {
        // Skip filtered messages
        if (shouldFilterMessage(message)) return;
        
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] ${message}`, data || '');
        
        const panel = document.getElementById('debugPanel');
        if (panel) {
            let dataText = '';
            if (data) {
                try {
                    dataText = typeof data === 'object' ?
                        `<pre>${JSON.stringify(data, null, 2)}</pre>` :
                        `<pre>${data}</pre>`;
                } catch (e) {
                    dataText = '<pre>[Complex object]</pre>';
                }
            }
            panel.innerHTML += `<div><strong>[${timestamp}]</strong> ${message} ${dataText}</div>`;
            panel.scrollTop = panel.scrollHeight;
        }
    };
}
