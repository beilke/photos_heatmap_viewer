"""
Performance Helper Functions for Photo Heatmap Viewer

This module provides performance helpers that don't require optional dependencies like psutil.
"""
import os
import hashlib
import logging
import time
import multiprocessing
import sqlite3
from functools import lru_cache

logger = logging.getLogger(__name__)

def fast_file_hash(file_path, sample_size=65536):
    """Create a quick hash of a file by reading only the beginning and end.
    
    Much faster than hashing the entire file, while still providing good uniqueness.
    """
    try:
        file_size = os.path.getsize(file_path)
        
        if file_size < sample_size * 2:
            # For small files, just hash the entire file
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        
        hash_obj = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read first chunk
            hash_obj.update(f.read(sample_size))
            
            # Seek to the end and read last chunk
            f.seek(-sample_size, os.SEEK_END)
            hash_obj.update(f.read(sample_size))
            
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"Error creating fast hash for {file_path}: {e}")
        # Fall back to full file hash if needed
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return None

# Use LRU cache to avoid rehashing the same file multiple times
fast_file_hash_cached = lru_cache(maxsize=10000)(fast_file_hash)

def get_optimal_worker_count(task_type='cpu'):
    """Calculate optimal number of worker processes/threads based on system resources"""
    cpu_count = multiprocessing.cpu_count()
    
    if task_type == 'cpu':
        # CPU-bound tasks typically work best with N or N-1 workers
        # where N is the number of physical CPU cores
        return max(1, cpu_count - 1)
    else:  # I/O-bound tasks
        # I/O-bound tasks can benefit from more workers
        return max(2, cpu_count * 2)

def optimize_batch_processing(batch_size=100):
    """Calculate optimal batch sizes for processing and database operations"""
    # Try to use system info if available
    try:
        import psutil
        available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
        
        # Scale batch sizes based on available memory
        if available_memory > 8000:  # More than 8GB available
            db_batch = 500
        elif available_memory > 4000:  # More than 4GB available
            db_batch = 250
        elif available_memory > 2000:  # More than 2GB available
            db_batch = 150
        else:  # Limited memory
            db_batch = 100
            
        logger.info(f"Auto-configured batch size: {db_batch}")
        return db_batch
        
    except ImportError:
        # psutil not available, use default value
        logger.info(f"Using default batch size: {batch_size}")
        return batch_size

def optimize_sqlite_connection(conn):
    """Apply SQLite optimizations for better performance"""
    settings = {}
    try:
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        settings["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        
        # Try to get optimal cache size
        try:
            import psutil
            available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
            
            # Use up to 25% of available memory for cache
            cache_mb = int(available_memory_mb * 0.25)
            cache_pages = int(cache_mb * 1024 / 4)  # Convert MB to 4KB pages
            cache_pages = max(10000, min(100000, cache_pages))  # Reasonable limits
            
            conn.execute(f"PRAGMA cache_size={cache_pages}")
            
        except ImportError:
            # psutil not available, use fixed values
            conn.execute("PRAGMA cache_size=20000")  # About 80MB
            
        settings["cache_size"] = conn.execute("PRAGMA cache_size").fetchone()[0]
        
        # Other performance settings
        conn.execute("PRAGMA synchronous=NORMAL")  # Less durable but faster
        settings["synchronous"] = conn.execute("PRAGMA synchronous").fetchone()[0]
        
        conn.execute("PRAGMA temp_store=MEMORY")
        settings["temp_store"] = conn.execute("PRAGMA temp_store").fetchone()[0]
        
        # Increase mmap size if possible
        try:
            import psutil
            available_memory = psutil.virtual_memory().available
            mmap_size = min(available_memory // 4, 1024 * 1024 * 1024)  # Up to 1GB
            conn.execute(f"PRAGMA mmap_size={mmap_size}")
        except ImportError:
            conn.execute("PRAGMA mmap_size=536870912")  # 512MB
            
        settings["mmap_size"] = conn.execute("PRAGMA mmap_size").fetchone()[0]
        
        # Additional optimizations
        conn.execute("PRAGMA page_size=4096")      # Larger page size for better performance
        conn.execute("PRAGMA count_changes=OFF")   # Disable count_changes for better performance
        conn.execute("PRAGMA case_sensitive_like=OFF")
        
        # Improved transaction handling
        conn.isolation_level = 'DEFERRED'
        
        return settings
        
    except Exception as e:
        logger.error(f"Error optimizing SQLite connection: {e}")
        return settings

class PerformanceMonitor:
    """Simple class to monitor performance metrics during processing"""
    
    def __init__(self, name="operation"):
        self.name = name
        self.start_time = None
        self.last_update = None
        self.items_processed = 0
        self.update_interval = 5.0  # Update log every 5 seconds
        
    def start(self):
        """Start monitoring"""
        self.start_time = time.time()
        self.last_update = self.start_time
        self.items_processed = 0
        return self
        
    def update(self, count=1, force=False):
        """Update item count and log progress if interval exceeded"""
        self.items_processed += count
        
        current_time = time.time()
        elapsed = current_time - self.last_update
        
        if force or elapsed >= self.update_interval:
            total_elapsed = current_time - self.start_time
            if total_elapsed > 0:
                rate = self.items_processed / total_elapsed
                logger.info(f"{self.name}: Processed {self.items_processed} items "
                           f"({rate:.1f} items/sec)")
            self.last_update = current_time
            
    def stop(self):
        """Stop monitoring and report final statistics"""
        total_elapsed = time.time() - self.start_time
        if total_elapsed > 0 and self.items_processed > 0:
            rate = self.items_processed / total_elapsed
            logger.info(f"{self.name} completed: {self.items_processed} items "
                       f"in {total_elapsed:.1f} seconds ({rate:.1f} items/sec)")
        return self.items_processed, total_elapsed
