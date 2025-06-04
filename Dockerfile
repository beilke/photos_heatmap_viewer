FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py .
COPY index.html .
COPY photo_library.db* ./
COPY photo_heatmap_data.json* ./

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "server.py", "--port", "8000"]
