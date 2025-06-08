import os
import datetime
import sys

def create_test_update_times():
    """Create test update time files for testing tooltips"""
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Libraries we want to create update times for
    libraries = ["Vacation", "Family", "Work", "Events", "Nature", "Travel"]
    
    now = datetime.datetime.now()
    
    # Create update time files with different times
    for i, lib in enumerate(libraries):
        # Create different times (now, 1 hour ago, 1 day ago, etc.)
        if i == 0:
            time = now
        elif i == 1:
            time = now - datetime.timedelta(hours=1)
        elif i == 2:
            time = now - datetime.timedelta(days=1)
        elif i == 3:
            time = now - datetime.timedelta(days=2)
        elif i == 4:
            time = now - datetime.timedelta(weeks=1)
        else:
            time = now - datetime.timedelta(weeks=2)
            
        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Write the update time to a file
        with open(os.path.join(data_dir, f"last_update_{lib}.txt"), "w") as f:
            f.write(time_str)
            
        print(f"Created update time for {lib}: {time_str}")
        
if __name__ == "__main__":
    create_test_update_times()
    print("\nTest update time files created.")
    print("Now run the Flask server with: python server.py")
