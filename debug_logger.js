/**
 * Enhanced debug logger for photo heatmap viewer
 * Provides visual logging and console overrides for better debugging
 */

// Enhanced logging system
const Logger = {
    // Log levels
    LEVELS: {
        DEBUG: 0,
        INFO: 1,
        WARN: 2,
        ERROR: 3
    },
    
    // Current log level
    currentLevel: 0, // Default to DEBUG
    
    // Store original console methods
    originalConsole: {
        log: console.log,
        info: console.info,
        warn: console.warn,
        error: console.error,
        debug: console.debug
    },
    
    // Log to both console and visual log if available
    log: function(level, ...args) {
        const timestamp = new Date().toISOString();
        const prefix = `[${timestamp}] [${Object.keys(this.LEVELS).find(key => this.LEVELS[key] === level)}]`;
        
        // Only log if the level is at or above the current level
        if (level >= this.currentLevel) {
            // Log to console with original methods to avoid recursion
            switch(level) {
                case this.LEVELS.DEBUG:
                    this.originalConsole.debug(prefix, ...args);
                    break;
                case this.LEVELS.INFO:
                    this.originalConsole.info(prefix, ...args);
                    break;
                case this.LEVELS.WARN:
                    this.originalConsole.warn(prefix, ...args);
                    break;
                case this.LEVELS.ERROR:
                    this.originalConsole.error(prefix, ...args);
                    break;
            }
            
            // Log to visual log if available
            this.appendToVisualLog(level, prefix, args);
        }
    },
    
    // Helper methods for different log levels
    debug: function(...args) {
        this.log(this.LEVELS.DEBUG, ...args);
    },
    
    info: function(...args) {
        this.log(this.LEVELS.INFO, ...args);
    },
    
    warn: function(...args) {
        this.log(this.LEVELS.WARN, ...args);
    },
    
    error: function(...args) {
        this.log(this.LEVELS.ERROR, ...args);
    },
    
    // Append to visual log if available
    appendToVisualLog: function(level, prefix, args) {
        const logContainer = document.getElementById('debug-log');
        if (logContainer) {
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry log-${Object.keys(this.LEVELS).find(key => this.LEVELS[key] === level).toLowerCase()}`;
            
            const message = args.map(arg => {
                if (typeof arg === 'object') {
                    try {
                        return JSON.stringify(arg, null, 2);
                    } catch (e) {
                        return String(arg);
                    }
                }
                return String(arg);
            }).join(' ');
            
            logEntry.textContent = `${prefix} ${message}`;
            logContainer.appendChild(logEntry);
            
            // Auto-scroll to bottom
            logContainer.scrollTop = logContainer.scrollHeight;
            
            // Limit entries
            while (logContainer.children.length > 500) {
                logContainer.removeChild(logContainer.firstChild);
            }
        }
    },
    
    // Initialize the logger
    init: function() {
        // Override console methods
        console.debug = (...args) => this.debug(...args);
        console.log = (...args) => this.info(...args);
        console.info = (...args) => this.info(...args);
        console.warn = (...args) => this.warn(...args);
        console.error = (...args) => this.error(...args);
        
        // Setup error capturing
        window.addEventListener('error', (event) => {
            this.error('Uncaught error:', event.error || event.message);
            return false; // Let default handler run too
        });
        
        window.addEventListener('unhandledrejection', (event) => {
            this.error('Unhandled promise rejection:', event.reason);
        });
        
        this.info('Logger initialized');
    },
    
    // Set the current log level
    setLevel: function(level) {
        this.currentLevel = level;
        this.info(`Log level set to ${Object.keys(this.LEVELS).find(key => this.LEVELS[key] === level)}`);
    },
    
    // Toggle visual log display
    toggleVisualLog: function() {
        const logContainer = document.getElementById('debug-log-container');
        if (logContainer) {
            logContainer.style.display = logContainer.style.display === 'none' ? 'block' : 'none';
        }
    },
    
    // Clear visual log
    clearVisualLog: function() {
        const logContainer = document.getElementById('debug-log');
        if (logContainer) {
            logContainer.innerHTML = '';
            this.info('Debug log cleared');
        }
    },
    
    // Data analysis functions
    analyzePhotoData: function(data) {
        if (!data || !Array.isArray(data)) {
            this.error("Cannot analyze invalid data");
            return;
        }
        
        this.info(`Analyzing ${data.length} photos`);
        
        // Count photos with GPS data
        const gpsCount = data.filter(p => p.latitude && p.longitude).length;
        
        // Count photos with date
        const dateCount = data.filter(p => p.datetime).length;
        
        // Sample a photo
        const sample = data.length > 0 ? data[0] : null;
        
        this.info(`Analysis: ${gpsCount}/${data.length} have GPS, ${dateCount}/${data.length} have dates`);
        if (sample) {
            this.debug("Sample photo:", sample);
        }
        
        return {
            total: data.length,
            withGps: gpsCount,
            withDate: dateCount,
            sample: sample
        };
    }
};

// Initialize logger when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    Logger.init();
});
