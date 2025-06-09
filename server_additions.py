import os
import flask
from flask import Flask, request, jsonify, send_from_directory, render_template

# Setup Flask app
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for Docker container"""
    return "OK", 200

# Function to get last update times for libraries
def get_last_update_times():
    """Get the last update times for all libraries"""
    updates = {}
    data_dir = os.path.join(os.getcwd(), 'data') if os.path.exists(os.path.join(os.getcwd(), 'data')) else os.getcwd()
    
    for file in os.listdir(data_dir):
        if file.startswith("last_update_") and file.endswith(".txt"):
            library_name = file.replace("last_update_", "").replace(".txt", "")
            try:
                with open(os.path.join(data_dir, file), "r") as f:
                    updates[library_name] = f.read().strip()
            except:
                pass
    return updates

# Make last update times available to all templates
@app.context_processor
def inject_last_updates():
    return {"last_updates": get_last_update_times()}
