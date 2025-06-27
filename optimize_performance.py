"""
Performance optimization module for Photo Heatmap Viewer
Contains functions to improve server performance and image processing
"""

import os
import io
import time
import logging
import threading
import queue
from PIL import Image
from functools import lru_cache

# Configure logging
logger = logging.getLogger(__name__)

# LRU Cache size for image metadata
METADATA_CACHE_SIZE = 1000

# Background processing queue
bg_queue = queue.Queue()
bg_thread_running = False
bg_thread = None

class ImageProcessor:
    """Class to handle image processing operations with optimizations"""
    
    def __init__(self, cache_dir=None, max_threads=2):
        """Initialize the image processor"""
        self.cache_dir = cache_dir or os.path.join('data', 'image_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.max_threads = max_threads
        self.processing_threads = []
        
    @lru_cache(maxsize=METADATA_CACHE_SIZE)
    def get_image_metadata(self, image_path):
        """
        Get basic metadata from an image file
        Uses LRU cache to avoid repeated file access
        """
        try:
            with Image.open(image_path) as img:
                return {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'width': img.width,
                    'height': img.height
                }
        except Exception as e:
            logger.error(f"Error getting metadata for {image_path}: {e}")
            return None
            
    def start_background_processing(self):
        """Start background processing thread if not already running"""
        global bg_thread_running, bg_thread
        
        if not bg_thread_running:
            bg_thread_running = True
            bg_thread = threading.Thread(target=self._background_processor)
            bg_thread.daemon = True
            bg_thread.start()
            logger.info("Started background image processing thread")
            
    def stop_background_processing(self):
        """Stop the background processing thread"""
        global bg_thread_running
        
        if bg_thread_running:
            bg_thread_running = False
            # Add a None task to unblock the queue
            bg_queue.put(None)
            logger.info("Stopping background image processing thread")
            
    def _background_processor(self):
        """Background thread for processing images"""
        global bg_thread_running
        
        logger.info("Background processor thread started")
        
        while bg_thread_running:
            try:
                # Get a task from the queue with a timeout
                task = bg_queue.get(timeout=1.0)
                
                # Check if we got a shutdown signal
                if task is None:
                    logger.debug("Background processor received shutdown signal")
                    break
                    
                # Process the task
                try:
                    task_type = task.get('type')
                    
                    if task_type == 'convert_heic':
                        self._process_heic_conversion(task)
                    elif task_type == 'preload_image':
                        self._process_image_preload(task)
                    else:
                        logger.warning(f"Unknown task type: {task_type}")
                        
                except Exception as e:
                    logger.error(f"Error processing background task: {e}")
                    
                finally:
                    # Mark task as done
                    bg_queue.task_done()
                    
            except queue.Empty:
                # No tasks available, just continue the loop
                pass
                
        logger.info("Background processor thread stopped")
        
    def _process_heic_conversion(self, task):
        """Process a HEIC conversion task"""
        image_path = task.get('image_path')
        cache_path = task.get('cache_path')
        quality = task.get('quality', 90)
        max_size = task.get('max_size', 1920)
        
        if not image_path or not cache_path:
            logger.error("Missing required parameters for HEIC conversion task")
            return
            
        # Skip if file already exists in cache
        if os.path.exists(cache_path):
            return
            
        try:
            start_time = time.time()
            
            # Import HEIC support if needed
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ImportError:
                logger.error("pillow-heif not found, cannot convert HEIC file")
                return
                
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                    
                # Resize if needed
                if max_size and (img.width > max_size or img.height > max_size):
                    if img.width > img.height:
                        new_width = max_size
                        new_height = int(img.height * (max_size / img.width))
                    else:
                        new_height = max_size
                        new_width = int(img.width * (max_size / img.height))
                    
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Save to cache
                img.save(cache_path, format='JPEG', quality=quality, optimize=True)
                
            elapsed = time.time() - start_time
            logger.info(f"Background HEIC conversion completed in {elapsed:.2f}s: {os.path.basename(image_path)}")
            
        except Exception as e:
            logger.error(f"Error in background HEIC conversion: {e}")
    
    def _process_image_preload(self, task):
        """Process an image preload task"""
        image_path = task.get('image_path')
        
        if not image_path:
            logger.error("Missing required parameters for image preload task")
            return
            
        try:
            # Just open and close the image to cache it in the OS file cache
            with Image.open(image_path) as img:
                # Get a thumbnail to force image processing
                img.thumbnail((100, 100))
                
            logger.debug(f"Preloaded image: {os.path.basename(image_path)}")
            
        except Exception as e:
            logger.error(f"Error in image preload: {e}")
            
    def schedule_heic_conversion(self, image_path, cache_path, quality=90, max_size=1920):
        """Schedule a HEIC conversion task for background processing"""
        # Add to queue
        bg_queue.put({
            'type': 'convert_heic',
            'image_path': image_path,
            'cache_path': cache_path,
            'quality': quality,
            'max_size': max_size
        })
        
        # Ensure background thread is running
        self.start_background_processing()
        
    def schedule_image_preload(self, image_path):
        """Schedule an image to be preloaded into memory"""
        # Add to queue
        bg_queue.put({
            'type': 'preload_image',
            'image_path': image_path
        })
        
        # Ensure background thread is running
        self.start_background_processing()

# Create a singleton instance
image_processor = ImageProcessor()

# Function to optimize the application startup
def optimize_startup():
    """Perform optimizations during application startup"""
    # Start the background processing thread
    image_processor.start_background_processing()
    
    # Return the processor instance for convenience
    return image_processor

# Function to optimize memory usage
def optimize_memory():
    """Perform memory optimizations"""
    import gc
    
    # Force garbage collection
    collected = gc.collect()
    logger.debug(f"Garbage collector: collected {collected} objects")
    
    return True
