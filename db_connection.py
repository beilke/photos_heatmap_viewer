"""
Database connection manager for the Photo Heatmap Viewer project.
Provides robust database connection handling with automatic reconnection capabilities.
"""
import sqlite3
import logging
import time
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseConnectionManager:
    """Database connection manager with reconnection capabilities"""
    
    def __init__(self, db_path, max_retries=3, retry_delay=1):
        self.db_path = db_path
        self.conn = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.optimize_func = None

    def set_optimizer(self, optimize_func):
        """Set the function to optimize the database connection"""
        self.optimize_func = optimize_func
        
    def connect(self):
        """Connect to the database with retry mechanism"""
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                if attempts > 0:
                    logger.info(f"Reconnection attempt {attempts}/{self.max_retries}...")
                    time.sleep(self.retry_delay)
                
                # Make sure the directory exists
                db_dir = os.path.dirname(self.db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir)
                
                # Connect with optimized settings
                self.conn = sqlite3.connect(self.db_path, isolation_level="DEFERRED", check_same_thread=False, timeout=20.0)
                
                # Apply optimizations if available
                if self.optimize_func:
                    try:
                        self.optimize_func(self.conn)
                    except Exception as e:
                        logger.error(f"Error optimizing database: {e}")
                        
                # Test the connection
                self.conn.execute("SELECT 1")
                logger.debug("Database connection established successfully")
                return self.conn
                
            except Exception as e:
                attempts += 1
                last_error = e
                logger.warning(f"Database connection attempt {attempts} failed: {e}")
        
        # All retries failed
        logger.error(f"Failed to connect to database after {self.max_retries} attempts. Last error: {last_error}")
        raise last_error or sqlite3.Error("Failed to connect to database")
    
    def close(self):
        """Close the database connection safely"""
        if self.conn:
            try:
                self.conn.close()
                self.conn = None
                logger.debug("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
    
    def execute_with_retry(self, cursor_method, *args, **kwargs):
        """Execute a cursor method with automatic reconnection if needed"""
        if not self.conn:
            self.connect()
            
        cursor = self.conn.cursor()
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                # Call the requested cursor method
                method = getattr(cursor, cursor_method)
                result = method(*args, **kwargs)
                return result
            
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                # Check if it's a connection error
                if "database is locked" in str(e) or "disk I/O error" in str(e) or "not a database" in str(e):
                    attempts += 1
                    last_error = e
                    logger.warning(f"Database error on {cursor_method}, attempt {attempts}: {e}")
                    
                    # Try to reconnect
                    self.close()
                    time.sleep(self.retry_delay * attempts)  # Increasing delay for each retry
                    self.connect()
                    cursor = self.conn.cursor()
                else:
                    # For other types of errors, re-raise immediately
                    raise
            except Exception as e:
                # For non-database errors, re-raise immediately
                raise
        
        # All retries failed
        logger.error(f"Failed to execute {cursor_method} after {self.max_retries} attempts. Last error: {last_error}")
        raise last_error or sqlite3.Error(f"Failed to execute {cursor_method}")
    
    def commit_with_retry(self):
        """Commit transaction with retry mechanism"""
        if not self.conn:
            return
            
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                self.conn.commit()
                return
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                attempts += 1
                last_error = e
                logger.warning(f"Commit failed, attempt {attempts}: {e}")
                
                if attempts < self.max_retries:
                    # Try to reconnect
                    self.close()
                    time.sleep(self.retry_delay)
                    self.connect()
            except Exception as e:
                # For non-database errors, re-raise immediately
                raise
        
        # All retries failed
        logger.error(f"Failed to commit transaction after {self.max_retries} attempts. Last error: {last_error}")
        raise last_error or sqlite3.Error("Failed to commit transaction")
    
    @contextmanager
    def get_cursor(self):
        """Get a cursor with reconnection capability"""
        if not self.conn:
            self.connect()
            
        cursor = self.conn.cursor()
        try:
            yield cursor
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            # Check if it's a connection error
            if "database is locked" in str(e) or "disk I/O error" in str(e) or "not a database" in str(e):
                # Try to reconnect
                logger.warning(f"Database error in cursor operation: {e}, reconnecting...")
                self.close()
                self.connect()
                # Re-raise to let caller handle the retry
                raise
            else:
                # For other types of errors, re-raise
                raise
        except Exception:
            # Re-raise other exceptions
            raise

@contextmanager
def get_db_connection(db_path, optimize_func=None):
    """Context manager for database connections with automatic reconnection"""
    db_manager = DatabaseConnectionManager(db_path)
    if optimize_func:
        db_manager.set_optimizer(optimize_func)
    
    try:
        conn = db_manager.connect()
        yield conn
    finally:
        db_manager.close()
