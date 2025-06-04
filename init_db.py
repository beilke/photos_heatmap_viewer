import sqlite3
import os

def create_database(db_path='photo_library.db'):
    """Create the SQLite database with necessary tables and indexes."""
    # Check if the database already exists
    if os.path.exists(db_path):
        print(f"Database file '{db_path}' already exists. Skipping creation.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create photos table
    cursor.execute('''
    CREATE TABLE photos (
      id INTEGER PRIMARY KEY,
      filename TEXT,
      path TEXT,
      latitude REAL,
      longitude REAL,
      datetime TEXT,
      tags TEXT,
      hash TEXT
    )
    ''')
      # Create indexes for better query performance
    cursor.execute('CREATE INDEX idx_coords ON photos(latitude, longitude)')
    cursor.execute('CREATE INDEX idx_datetime ON photos(datetime)')
    cursor.execute('CREATE INDEX idx_filename ON photos(filename)')
    cursor.execute('CREATE INDEX idx_hash ON photos(hash)')
    cursor.execute('CREATE INDEX idx_path ON photos(path)')
    
    conn.commit()
    conn.close()
    print(f"Database created successfully at '{db_path}'")

if __name__ == "__main__":
    create_database()
