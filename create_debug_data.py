# Simple debugging script to create a minimal valid JSON file
import json
import os

print("Creating a minimal valid JSON file for testing...")

# Create a simple JSON file with one sample photo
sample_data = [
    {
        "id": 1,
        "filename": "test_photo.jpg",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "datetime": "2024-06-04T12:00:00",
        "path": "D:\\Photos\\test_photo.jpg"
    }
]

# Write to the JSON file
with open('photo_heatmap_data.json', 'w') as f:
    json.dump(sample_data, f)

print(f"Created photo_heatmap_data.json with sample data")
print("File size:", os.path.getsize('photo_heatmap_data.json'), "bytes")

# Also write to a diagnostic file
print("Writing diagnostic info...")
with open('debug_info.txt', 'w') as f:
    f.write("Debug information for photo heatmap viewer\n")
    f.write("-----------------------------------------\n")
    f.write(f"Current directory: {os.getcwd()}\n")
    f.write(f"JSON file path: {os.path.abspath('photo_heatmap_data.json')}\n")
    f.write(f"JSON file exists: {os.path.exists('photo_heatmap_data.json')}\n")
    f.write(f"JSON file size: {os.path.getsize('photo_heatmap_data.json')} bytes\n")
    
    # List files in the current directory
    f.write("\nFiles in current directory:\n")
    for file in os.listdir():
        f.write(f"  - {file} ({os.path.getsize(file)} bytes)\n")

print("Done. Created debug_info.txt with diagnostic information.")
print("\nNow restart the server with: python server.py")
