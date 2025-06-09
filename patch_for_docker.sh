#!/bin/bash
# Patch script to add health check and last update display to server.py and index.html

# Function to add health check to server.py if not already present
add_health_check() {
  # Check if health check route already exists
  if grep -q "@app.route.*health" server.py || grep -q "@app.route('/health')" server.py; then
    echo "Health check endpoint already exists in server.py"
  else
    echo "Adding health check endpoint to server.py"
    # Add right before the if __name__ == "__main__" line
    sed -i '/if __name__ == "__main__":/i \
@app.route("/health")\
def health_check():\
    """Health check endpoint for Docker container"""\
    return "OK", 200\
' server.py
  fi
}

# Function to add last update times functionality
add_last_update_times() {
  # Check if the function already exists
  if grep -q "get_last_update_times" server.py; then
    echo "Last update times function already exists in server.py"
  else
    echo "Adding last update times functionality to server.py"
    # Add right before the if __name__ == "__main__" line
    sed -i '/if __name__ == "__main__":/i \
# Function to get last update times for libraries\
def get_last_update_times():\
    """Get the last update times for all libraries"""\
    updates = {}\
    data_dir = os.path.join(os.getcwd(), "data") if os.path.exists(os.path.join(os.getcwd(), "data")) else os.getcwd()\
    \
    for file in os.listdir(data_dir):\
        if file.startswith("last_update_") and file.endswith(".txt"):\
            library_name = file.replace("last_update_", "").replace(".txt", "")\
            try:\
                with open(os.path.join(data_dir, file), "r") as f:\
                    updates[library_name] = f.read().strip()\
            except Exception as e:\
                print(f"Error reading update time for {library_name}: {e}")\
    return updates\
\
# Make last update times available in template context\
@app.context_processor\
def inject_last_updates():\
    return {"last_updates": get_last_update_times()}\
' server.py
  fi
}

# Function to add update display to index.html
add_update_display() {
  # Get the list of HTML files
  HTML_FILES=$(find . -name "*.html" | grep -v "template_updates.html")
  
  for HTML_FILE in $HTML_FILES; do
    # Check if update info already exists
    if grep -q "library-updates" "$HTML_FILE"; then
      echo "Update display already exists in $HTML_FILE"
    else
      echo "Adding update display to $HTML_FILE"
      
      # Read the template update HTML
      if [ -f template_updates.html ]; then
        UPDATE_HTML=$(cat template_updates.html)
        
        # Find the closing body tag and insert before it
        sed -i "/<\/body>/i \\${UPDATE_HTML}" "$HTML_FILE"
      else
        echo "Warning: template_updates.html not found, skipping HTML update"
      fi
    fi
  done
}

# Run the functions
add_health_check
add_last_update_times
add_update_display

echo "Patch complete!"
