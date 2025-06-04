"""
Simple script to create an empty JSON file if none exists.
This helps prevent loading errors when no photos have been processed yet.
"""

import os
import json

def create_empty_json(file_path='photo_heatmap_data.json'):
    """Create an empty JSON array file if the file doesn't exist."""
    if not os.path.exists(file_path):
        print(f"Creating empty JSON file at {file_path}")
        with open(file_path, 'w') as f:
            json.dump([], f)
        print("Done. Empty JSON file created.")
    else:
        # Check if the file is empty or invalid
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    print(f"File exists but is empty. Creating a valid JSON array.")
                    with open(file_path, 'w') as f:
                        json.dump([], f)
                    print("Done. Valid empty JSON array created.")
                else:
                    # Try parsing it
                    try:
                        json.loads(content)
                        print(f"File {file_path} exists and appears to be valid JSON.")
                    except json.JSONDecodeError:
                        print(f"File {file_path} exists but contains invalid JSON. Creating a valid JSON array.")
                        with open(file_path, 'w') as f:
                            json.dump([], f)
                        print("Done. Valid empty JSON array created.")
        except Exception as e:
            print(f"Error checking JSON file: {e}")

if __name__ == "__main__":
    create_empty_json()
