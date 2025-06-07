"""
Performance Optimization Module for Photo Heatmap Viewer

This module contains utility functions for optimizing the performance of
the photo processing pipeline, especially for very large photo libraries.
"""
import os
import hashlib
import sqlite3
import logging
import time
import multiprocessing
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

def fast_file_hash(file_path, sample_size=65536):
    """Create a quick hash of a file by reading only the beginning and end.
    
    Much faster than hashing the entire file, while still providing good uniqueness.
    
    Args:
        file_path: Path to the file
        sample_size: Number of bytes to read from start and end of file
        
    Returns:
        MD5 hash string
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

# Use LRU cache for the fast hash function to avoid rehashing the same file
fast_file_hash_cached = lru_cache(maxsize=10000)(fast_file_hash)

def optimize_batch_processing(batch_size=250, max_in_memory=1000):
    """Calculate optimal batch sizes for processing and database operations
    
    Returns:
        Tuple of (processing_batch_size, db_batch_size)
    """
    # Adjust based on available memory
    try:
        import psutil
        available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
        
        # Scale batch sizes based on available memory
        if available_memory > 8000:  # More than 8GB available
            processing_batch = min(500, max_in_memory)
            db_batch = 500
        elif available_memory > 4000:  # More than 4GB available
            processing_batch = min(250, max_in_memory)
            db_batch = 250
        elif available_memory > 2000:  # More than 2GB available
            processing_batch = min(100, max_in_memory)
            db_batch = 200
        else:  # Limited memory
            processing_batch = min(50, max_in_memory)
            db_batch = 100
            
        logger.info(f"Auto-configured batch sizes: processing={processing_batch}, db={db_batch}")
        return processing_batch, db_batch
        
    except ImportError:
        # psutil not available, use default values
        logger.info(f"Using default batch sizes: processing={batch_size}, db={batch_size}")
        return batch_size, batch_size

def optimize_sqlite_connection(conn, file_size_mb=None):
    """Apply comprehensive SQLite optimizations based on database size and available memory
    
    Args:
        conn: SQLite connection object
        file_size_mb: Size of the database file in MB (optional)
    
    Returns:
        Dictionary of applied settings
    """
    settings = {}
    
    try:
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        settings["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        
        # Calculate optimal cache size based on database size and available memory
        try:
            import psutil
            available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
            
            # Get database file size if not provided
            if not file_size_mb and hasattr(conn, 'filename'):
                try:
                    file_size_mb = os.path.getsize(conn.filename) / (1024 * 1024)
                except (AttributeError, OSError):
                    file_size_mb = 100  # Default assumption
            
            # Calculate cache size (in pages, where each page is typically 4KB)
            # Use up to 25% of available memory or 2x database size, whichever is smaller
            max_cache_mb = min(available_memory_mb * 0.25, file_size_mb * 2)
            cache_pages = int(max_cache_mb * 1024 / 4)  # Convert MB to 4KB pages
            cache_pages = max(2000, min(100000, cache_pages))  # Reasonable limits
            
            conn.execute(f"PRAGMA cache_size={cache_pages}")
            settings["cache_size"] = conn.execute("PRAGMA cache_size").fetchone()[0]
            
            # Memory mapping size (use up to 10% of available memory or 1GB, whichever is smaller)
            mmap_size = min(int(available_memory_mb * 1024 * 0.1), 1024 * 1024 * 1024)
            conn.execute(f"PRAGMA mmap_size={mmap_size}")
            settings["mmap_size"] = conn.execute("PRAGMA mmap_size").fetchone()[0]
            
        except ImportError:
            # psutil not available, use fixed values
            conn.execute("PRAGMA cache_size=10000")  # About 40MB
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB
            settings["cache_size"] = conn.execute("PRAGMA cache_size").fetchone()[0]
            settings["mmap_size"] = conn.execute("PRAGMA mmap_size").fetchone()[0]
        
        # Other performance settings
        conn.execute("PRAGMA synchronous=NORMAL")  # Less durable but faster
        settings["synchronous"] = conn.execute("PRAGMA synchronous").fetchone()[0]
        
        conn.execute("PRAGMA temp_store=MEMORY")
        settings["temp_store"] = conn.execute("PRAGMA temp_store").fetchone()[0]
        
        # Increase page size for larger databases (default is 4096)
        if file_size_mb and file_size_mb > 1000:  # For databases > 1GB
            # Note: page_size can only be set when database is empty
            try:
                conn.execute("PRAGMA page_size=8192")
                settings["page_size"] = conn.execute("PRAGMA page_size").fetchone()[0]
            except:
                settings["page_size"] = "(unchanged - can only be set on empty database)"
        
        # Other useful optimizations
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")  # Better for single-process access
        settings["locking_mode"] = conn.execute("PRAGMA locking_mode").fetchone()[0]
        
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

def get_optimal_worker_count(task_type='cpu'):
    """Calculate optimal number of worker processes/threads based on system resources
    
    Args:
        task_type: 'cpu' for CPU-bound tasks, 'io' for I/O-bound tasks
        
    Returns:
        Recommended number of workers
    """
    cpu_count = multiprocessing.cpu_count()
    
    if task_type == 'cpu':
        # CPU-bound tasks typically work best with N or N-1 workers
        # where N is the number of physical CPU cores
        return max(1, cpu_count - 1)
    else:  # I/O-bound tasks
        # I/O-bound tasks can benefit from more workers
        return max(2, cpu_count * 2)
