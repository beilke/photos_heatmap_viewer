from flask import Flask, render_template, jsonify, request
import os
import datetime
import time

app = Flask(__name__, static_folder='.', static_url_path='')

def get_data_dir():
    """Get the path to the data directory, create it if it doesn't exist"""
    data_dir = os.path.join(os.getcwd(), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_last_update_times():
    """Get the last update times for all libraries"""
    updates = {}
    data_dir = get_data_dir()
    
    for file in os.listdir(data_dir):
        if file.startswith("last_update_") and file.endswith(".txt"):
            library_name = file.replace("last_update_", "").replace(".txt", "")
            try:
                with open(os.path.join(data_dir, file), "r") as f:
                    updates[library_name] = f.read().strip()
            except Exception as e:
                print(f"Error reading update time for {library_name}: {e}")
    return updates

@app.route('/')
def index():
    """Serve the update times test HTML file"""
    return app.send_static_file('update_times_test.html')

@app.route('/list-update-files')
def list_update_files():
    """API endpoint to list all update files"""
    updates = get_last_update_times()
    files = [{"library": lib, "time": time} for lib, time in updates.items()]
    return jsonify({"files": files})

@app.route('/create-update-file', methods=['POST'])
def create_update_file():
    """API endpoint to create a test update file"""
    data = request.json
    library = data.get('library', 'Test_Library')
    
    # Create a timestamp file
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = os.path.join(get_data_dir(), f"last_update_{library}.txt")
    
    with open(file_path, "w") as f:
        f.write(current_time)
    
    return jsonify({"library": library, "time": current_time})

@app.route('/index.html')
def render_index():
    """Render the main index.html template with update times"""
    return render_template('index.html', last_updates=get_last_update_times())

if __name__ == '__main__':
    port = 8080
    print(f"Starting test server at http://localhost:{port}")
    print(f"- Visit / to see the update files test page")
    print(f"- Visit /index.html to see the main index page with update times")
    app.run(debug=True, port=port)
