#!/usr/bin/env python3
"""
Docker debug script for the photo heatmap viewer.
This fixes common issues in the Docker environment.
"""

import os
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_docker_environment():
    """Fix common issues with files and directories in the Docker environment."""
    
    logger.info("Starting Docker environment diagnostic and fix")
    
    # Check if index.html exists in the current directory
    if os.path.exists("index.html"):
        logger.info("index.html found in current directory")
    else:
        logger.info("index.html NOT found in current directory")
        
        # Check if it's in templates directory
        if os.path.exists("templates/index.html"):
            logger.info("index.html found in templates directory")
            # Copy it to current directory
            logger.info("Copying index.html to current directory")
            shutil.copy("templates/index.html", "./index.html")
        else:
            logger.error("index.html not found in templates directory either!")
    
    # Check for CSS file
    if os.path.exists("style.css"):
        logger.info("style.css found in current directory")
    else:
        logger.info("style.css NOT found in current directory")
        
        # Check if it's in static directory
        if os.path.exists("static/style.css"):
            logger.info("style.css found in static directory")
            # Copy it to current directory
            logger.info("Copying style.css to current directory")
            shutil.copy("static/style.css", "./style.css")
        else:
            logger.error("style.css not found in static directory either!")
    
    # Check if database directory exists
    data_dir = "data"
    if not os.path.exists(data_dir):
        logger.info(f"Creating data directory: {data_dir}")
        os.makedirs(data_dir, exist_ok=True)
    
    # Print directory structure for verification
    logger.info("\nCurrent directory structure:")
    for root, dirs, files in os.walk("."):
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        sub_indent = " " * 4 * (level + 1)
        for file in files:
            logger.info(f"{sub_indent}{file}")

if __name__ == "__main__":
    fix_docker_environment()
