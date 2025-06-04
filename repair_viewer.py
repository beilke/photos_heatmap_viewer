#!/usr/bin/env python3
"""
Repair tool for Photo Heatmap Viewer
This script helps diagnose and fix common issues with the photo heatmap viewer.
"""

import os
import json
import sys
import sqlite3
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the specified file"""
    if not os.path.exists(filepath):
        print(f"Cannot backup {filepath} - file doesn't exist")
        return False
        
    backup_path = f"{filepath}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(filepath, backup_path)
        print(f"Created backup: {backup_path}")
        return True
    except Exception as e:
        print(f"Error creating backup: {e}")
        return False

def check_json_file(filename='photo_heatmap_data.json'):
    """Check JSON data file for issues and attempt repair if needed"""
    print(f"\n=== Checking {filename} ===")
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        choice = input("Create an empty JSON file? (y/n): ")
        if choice.lower() == 'y':
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                print(f"Created empty JSON file: {filename}")
                return True
            except Exception as e:
                print(f"Error creating file: {e}")
                return False
        return False
    
    # Check if file is empty
    if os.path.getsize(filename) == 0:
        print(f"Error: {filename} is empty")
        choice = input("Create a valid empty JSON array? (y/n): ")
        if choice.lower() == 'y':
            backup_file(filename)
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                print(f"Fixed: Wrote empty JSON array to {filename}")
                return True
            except Exception as e:
                print(f"Error writing file: {e}")
                return False
        return False
    
    # Check if file contains valid JSON
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Check if root is array
        if not isinstance(data, list):
            print(f"Error: {filename} does not contain a JSON array")
            choice = input("Convert to empty array? THIS WILL CLEAR ALL DATA! (y/n): ")
            if choice.lower() == 'y':
                backup_file(filename)
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    print(f"Fixed: Converted {filename} to empty JSON array")
                    return True
                except Exception as e:
                    print(f"Error writing file: {e}")
                    return False
            return False
            
        # All checks passed
        count = len(data)
        gps_count = sum(1 for item in data if 'latitude' in item and 'longitude' in item 
                      and item['latitude'] is not None and item['longitude'] is not None)
        
        print(f"JSON file valid: Contains {count} items, {gps_count} with GPS coordinates")
        return True
        
    except json.JSONDecodeError as e:
        print(f"Error: {filename} contains invalid JSON: {e}")
        choice = input("Reset to empty JSON array? THIS WILL CLEAR ALL DATA! (y/n): ")
        if choice.lower() == 'y':
            backup_file(filename)
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump([], f)
                print(f"Fixed: Reset {filename} to empty JSON array")
                return True
            except Exception as e:
                print(f"Error writing file: {e}")
                return False
        return False
    except Exception as e:
        print(f"Error checking JSON: {e}")
        return False

def check_db_file(filename='photo_library.db'):
    """Check database file for issues"""
    print(f"\n=== Checking {filename} ===")
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found")
        print("You need to run init_db.py to create the database")
        return False
    
    try:
        # Check if it's a valid SQLite database
        conn = sqlite3.connect(filename)
        cursor = conn.cursor()
        
        # Check if the photos table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'")
        if not cursor.fetchone():
            print(f"Error: {filename} does not contain a 'photos' table")
            print("You need to run init_db.py to initialize the database structure")
            conn.close()
            return False
        
        # Count photos in database
        cursor.execute("SELECT COUNT(*) FROM photos")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM photos WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        gps_count = cursor.fetchone()[0]
        
        print(f"Database valid: Contains {total_count} photos, {gps_count} with GPS coordinates")
        
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error checking database: {e}")
        return False

def check_html_files():
    """Check HTML files"""
    print("\n=== Checking HTML files ===")
    
    html_files = ['index.html']
    for filename in html_files:
        if not os.path.exists(filename):
            print(f"Error: {filename} not found")
            continue
            
        print(f"Found {filename} - {os.path.getsize(filename)} bytes")

def run_diagnosis():
    """Run full diagnosis"""
    print("=== Photo Heatmap Viewer Diagnostics ===")
    print("Checking files...")
    
    json_ok = check_json_file()
    db_ok = check_db_file()
    html_ok = check_html_files()
    
    print("\n=== Diagnostics Summary ===")
    print(f"JSON data file: {'OK' if json_ok else 'Issues found'}")
    print(f"Database file: {'OK' if db_ok else 'Issues found'}")
    
    # Instructions for next steps
    print("\n=== Recommended Actions ===")
    if not json_ok or not db_ok:
        print("1. If database is missing or empty: Run init_db.py to create the database")
        print("2. If JSON file has issues: Run process_photos.py to rebuild the JSON data")
        print("3. Open diagnostic.html in your browser to test the map loading")
    else:
        print("All files appear to be valid. If you're still having issues:")
        print("1. Open diagnostic.html in your browser to test the map loading")
        print("2. Check server.log for any errors")
        print("3. Try restarting the server with: python debug_server.py")

if __name__ == "__main__":
    run_diagnosis()
