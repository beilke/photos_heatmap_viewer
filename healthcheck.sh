#!/bin/bash

# Health check script for photo heatmap viewer
# Checks if the Flask server is responding on the /health endpoint

curl -sSf http://localhost:8000/health || exit 1

exit 0
