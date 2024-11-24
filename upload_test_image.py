# upload_test_image.py

import os
import requests
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET", "production")
SANITY_WRITE_TOKEN = os.getenv("SANITY_WRITE_TOKEN")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_image_asset(image_filename):
    """
    Uploads the local image file to Sanity's Assets API.
    Returns the image asset document.
    """
    try:
        logger.info(f"Uploading image '{image_filename}' to Sanity's Assets API...")

        # Read the image data from the file
        try:
            with open(image_filename, 'rb') as img_file:
                image_data = img_file.read()
            logger.info("Image read successfully.")
        except Exception as e:
            logger.error(f"Image reading failed: {e}")
            raise ValueError("The provided image could not be read.")

        # Determine the content type based on file extension
        filename = os.path.basename(image_filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.png':
            content_type = 'image/png'
        elif ext == '.jpg' or ext == '.jpeg':
            content_type = 'image/jpeg'
        else:
            raise ValueError("Unsupported image file extension. Please use .png or .jpg/.jpeg.")

        # Prepare the upload URL and headers
        image_upload_url = f"https://{SANITY_PROJECT_ID}.api.sanity.io/v2021-06-07/assets/images/{SANITY_DATASET}?filename={filename}"
        headers = {
            "Authorization": f"Bearer {SANITY_WRITE_TOKEN}",
            "Content-Type": content_type
        }

        # Upload the image to Sanity
        response = requests.post(image_upload_url, data=image_data, headers=headers)
        logger.debug(f"Sanity Response: {response.status_code}, {response.text}")
        response.raise_for_status()

        # Extract and return the asset document from the response
        image_asset = response.json()
        if "document" in image_asset and "_id" in image_asset["document"]:
            logger.info(f"Image uploaded successfully with asset ID: {image_asset['document']['_id']}")
            return image_asset["document"]
        else:
            raise ValueError("Failed to retrieve asset ID from the uploaded image response.")

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        logger.error(f"Response content: {response.text}")
        raise
    except Exception as e:
        logger.error(f"An error occurred during image upload: {e}")
        raise

def main():
    image_filename = "test_image.png"  # Replace with the path to your test image
    try:
        upload_image_asset(image_filename)
    except Exception as e:
        logger.error(f"Failed to upload image: {e}")

if __name__ == "__main__":
    main()
