import sys
import os
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger.info("HEIF/HEIC support enabled")
    HEIC_SUPPORT = True
except ImportError:
    logger.warning("pillow-heif not installed. HEIC files will not be processed.")
    HEIC_SUPPORT = False

def get_exif_data(img):
    """Get EXIF data from an image, handling different image types"""
    if hasattr(img, 'getexif'):  # Newer versions of PIL or regular image formats
        return img.getexif()
    elif hasattr(img, '_getexif'):  # Older versions of PIL
        return img._getexif()
    else:
        return None

def get_decimal_from_dms(dms, ref):
    """Convert GPS DMS (Degrees, Minutes, Seconds) to decimal format"""
    try:
        # Handle different formats of DMS data
        if isinstance(dms, tuple) or isinstance(dms, list):
            # Standard format: [degrees, minutes, seconds]
            if len(dms) >= 3:
                degrees = float(dms[0])
                minutes = float(dms[1]) / 60.0
                seconds = float(dms[2]) / 3600.0
                decimal = degrees + minutes + seconds
            elif len(dms) == 2:
                # Some formats only provide degrees and minutes
                degrees = float(dms[0])
                minutes = float(dms[1]) / 60.0
                decimal = degrees + minutes
            else:
                # If we only have degrees
                decimal = float(dms[0])
        elif isinstance(dms, (int, float)):
            # Some formats might already provide decimal degrees
            decimal = float(dms)
        else:
            # Unsupported format
            logger.error(f"Unsupported GPS data format: {type(dms)} - {dms}")
            return None
        
        # Apply the reference direction (N/S/E/W)
        if ref and ref in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    except Exception as e:
        logger.error(f"Error converting GPS coordinates: {e}, data: {dms}, ref: {ref}")
        return None

def extract_gps(image_path):
    """Extract GPS coordinates from image EXIF data"""
    # Check if the file is a HEIC file and we don't have HEIC support
    if image_path.lower().endswith('.heic') and not HEIC_SUPPORT:
        logger.warning(f"Skipping GPS extraction for {image_path}: HEIC support not enabled")
        return None, None
        
    try:
        with Image.open(image_path) as img:
            # Get EXIF data using our helper function
            exif_data = get_exif_data(img)
            
            if not exif_data:
                logger.debug(f"No EXIF data found in {image_path}")
                return None, None
                
            gps_info = {}
            
            # Debug output all EXIF data
            print("All EXIF tags:")
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                print(f"  {tag_id} ({tag_name}): {value}")
            
            # Extract GPS info
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'GPSInfo':
                    print(f"\nFound GPSInfo tag: {tag_id}")
                    print(f"GPS value type: {type(value)}")
                    
                    try:
                        # Try to print the GPS data contents
                        if isinstance(value, dict):
                            print("Direct dictionary format")
                            for k, v in value.items():
                                print(f"  {k} ({GPSTAGS.get(k, k) if isinstance(k, int) else k}): {v}")
                            gps_info = value
                        else:
                            print("Standard format")
                            for gps_tag in value:
                                gps_tag_name = GPSTAGS.get(gps_tag, gps_tag)
                                print(f"  {gps_tag} ({gps_tag_name}): {value[gps_tag]}")
                                gps_info[gps_tag_name] = value[gps_tag]
                    except Exception as e:
                        print(f"Error inspecting GPS data: {e}")
            
            print("\nExtracted GPS info:")
            for k, v in gps_info.items():
                print(f"  {k}: {v}")
            
            if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
                lat_ref = gps_info.get('GPSLatitudeRef', 'N')
                lon_ref = gps_info.get('GPSLongitudeRef', 'E')
                
                print(f"\nGPSLatitude: {gps_info['GPSLatitude']}, Ref: {lat_ref}")
                print(f"GPSLongitude: {gps_info['GPSLongitude']}, Ref: {lon_ref}")
                
                try:
                    lat = get_decimal_from_dms(gps_info['GPSLatitude'], lat_ref)
                    lon = get_decimal_from_dms(gps_info['GPSLongitude'], lon_ref)
                    
                    print(f"\nDecimal coordinates: {lat}, {lon}")
                    return lat, lon
                except Exception as e:
                    print(f"Error converting GPS coordinates: {e}")
                    return None, None
            else:
                print("\nNo GPS latitude/longitude found in EXIF")
    except Exception as e:
        print(f"Error extracting GPS data from {image_path}: {e}")
    
    return None, None

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_gps_extraction.py <image_path>")
        return
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: File does not exist: {image_path}")
        return
    
    print(f"Checking GPS data for: {image_path}")
    lat, lon = extract_gps(image_path)
    
    if lat is not None and lon is not None:
        print(f"\nSUCCESS: GPS coordinates found: {lat}, {lon}")
        print("These coordinates can be used in your map visualization.")
    else:
        print("\nNo valid GPS coordinates found in this image.")
        print("Verify that the image contains GPS data in its EXIF information.")

if __name__ == "__main__":
    main()
