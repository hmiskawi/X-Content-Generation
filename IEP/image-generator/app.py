import os
import logging
import requests
import base64
import uuid
import io # For handling byte streams
from math import gcd # For aspect ratio calculation

from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from dotenv import load_dotenv
# from PIL import Image # PIL can be used for more advanced validation if needed

# --- Configuration ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Stability AI Configuration ---
STABILITY_API_HOST = os.getenv('STABILITY_API_HOST', 'https://api.stability.ai')
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
# Define the engine ID. Change this to use different models.
# e.g., "stable-diffusion-xl-1024-v1-0", "stable-diffusion-v1-6" etc.
DEFAULT_ENGINE_ID = "stable-diffusion-v1-6"

# --- Azure Blob Storage Configuration ---
AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.getenv("AZURE_BLOB_CONTAINER_NAME")

# Initialize Azure Blob Service Client (do basic checks)
blob_service_client = None
if AZURE_CONNECTION_STRING and AZURE_CONTAINER_NAME:
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        # Optional: Check if container exists on startup (can slow down startup)
        # try:
        #     container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
        #     container_client.get_container_properties()
        #     logging.info(f"Confirmed Azure container '{AZURE_CONTAINER_NAME}' exists.")
        # except ResourceNotFoundError:
        #     logging.error(f"Azure container '{AZURE_CONTAINER_NAME}' not found!")
        #     blob_service_client = None # Mark as unusable
    except Exception as e:
        logging.error(f"Failed to initialize Azure Blob Service Client: {e}", exc_info=True)
        blob_service_client = None
else:
    logging.error("Azure Blob Storage Connection String or Container Name missing.")

# --- Helper Functions ---

def get_dimensions_from_ratio(ratio_str: str, base_size: int = 1024) -> tuple | None:
    """
    Calculates width and height from an aspect ratio string (e.g., "16:9")
    aiming for a total area close to base_size * base_size,
    and ensuring dimensions are multiples of 64 (common SD requirement).
    """
    try:
        w_ratio, h_ratio = map(int, ratio_str.split(':'))
        if w_ratio <= 0 or h_ratio <= 0:
            raise ValueError("Ratios must be positive")

        # Simplify ratio
        common_divisor = gcd(w_ratio, h_ratio)
        w_ratio //= common_divisor
        h_ratio //= common_divisor

        # Calculate dimensions based on area (approximating base_size * base_size)
        # area = base_size * base_size
        # factor = (area / (w_ratio * h_ratio))**0.5
        # width = int(factor * w_ratio)
        # height = int(factor * h_ratio)

        # Alternative: Calculate based on matching one side closer to base_size
        # Determine if width or height ratio is larger
        if w_ratio >= h_ratio:
            # Landscape or square
            width = base_size
            height = int(base_size * h_ratio / w_ratio)
        else:
            # Portrait
            height = base_size
            width = int(base_size * w_ratio / h_ratio)


        # Adjust to be multiples of 64 (important for many SD models)
        width = max(64, (width // 64) * 64)
        height = max(64, (height // 64) * 64)

        logging.info(f"Aspect ratio '{ratio_str}' ({w_ratio}:{h_ratio}) -> Dimensions: {width}x{height}")
        return width, height

    except Exception as e:
        logging.warning(f"Invalid aspect ratio format '{ratio_str}': {e}. Using default.")
        # Default to base_size x base_size (square)
        default_dim = max(64, (base_size // 64) * 64)
        return default_dim, default_dim


def upload_to_azure(image_bytes: bytes, filename: str) -> str | None:
    """Uploads image bytes to Azure Blob Storage and returns the public URL."""
    if not blob_service_client:
        logging.error("Azure Blob Service Client not initialized. Cannot upload.")
        return None

    try:
        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=filename)

        # Create ContentSettings to specify the content type
        content_settings = ContentSettings(content_type='image/png') # Assuming PNG output

        # Upload the image bytes
        blob_client.upload_blob(image_bytes, overwrite=True, content_settings=content_settings)
        logging.info(f"Successfully uploaded image to Azure Blob Storage: {filename}")

        # Return the public URL
        return blob_client.url
    except Exception as e:
        logging.error(f"Failed to upload image to Azure: {e}", exc_info=True)
        return None

# --- API Endpoint ---

@app.route('/generate/image', methods=['POST'])
def generate_image():
    """Generates an image using Stability AI based on a prompt and uploads it."""

    # --- Initial Checks ---
    if not STABILITY_API_KEY:
        logging.error("Stability API key not configured.")
        return jsonify({"error": "Image generation service not configured (API Key Missing)"}), 500
    if not blob_service_client:
        logging.error("Azure Blob Storage not configured.")
        return jsonify({"error": "Image storage service not configured"}), 500

    if not request.is_json:
        logging.warning("Request received is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    logging.info(f"Received request data: {data}")

    # --- Input Validation ---
    prompt = data.get('prompt')
    if not prompt:
        logging.warning("Missing 'prompt' in request")
        return jsonify({"error": "Missing required field: prompt"}), 400

    style_preference = data.get('style_preference') # Optional style string
    aspect_ratio = data.get('aspect_ratio', "1:1")  # Default to 1:1
    negative_prompt = data.get('negative_prompt')   # Optional

    # --- Prepare for Stability API ---
    width, height = get_dimensions_from_ratio(aspect_ratio) # Use default size 1024 for SDXL

    # Construct the text prompts payload for the API
    text_prompts = [{"text": prompt, "weight": 1.0}]
    if style_preference:
        # Append style to the main prompt or use style_preset if API supports it
        # Simple append:
        prompt_with_style = f"{prompt}, {style_preference} style"
        text_prompts[0]["text"] = prompt_with_style
        # OR if using SDXL, use the 'style_preset' parameter (check Stability docs)
        # style_preset = style_preference.lower().replace(" ", "-") # Example formatting
    else:
        prompt_with_style = prompt # Keep track for final output
        # style_preset = None

    if negative_prompt:
        text_prompts.append({"text": negative_prompt, "weight": -1.0})

    final_prompt_used = prompt_with_style # Store for the response

    logging.info(f"Requesting {width}x{height} image from Stability AI.")
    logging.info(f"Using text_prompts: {text_prompts}")

    # --- Call Stability AI API ---
    api_url = f"{STABILITY_API_HOST}/v1/generation/{DEFAULT_ENGINE_ID}/text-to-image"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {STABILITY_API_KEY}",
    }

    payload = {
        "text_prompts": text_prompts,
        "cfg_scale": 7, # Default guidance scale
        "height": height,
        "width": width,
        "samples": 1, # Number of images to generate
        "steps": 30,  # Number of diffusion steps (30-50 is common)
        # "style_preset": style_preset, # Add if using SDXL presets
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=120) # Generous timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()

        # --- Process Response ---
        if not response_data.get("artifacts"):
            logging.error("No artifacts found in Stability AI response.")
            return jsonify({"error": "Image generation failed (no artifacts returned)"}), 500

        # Assuming PNG output, get base64 data
        base64_image = response_data["artifacts"][0].get("base64")
        if not base64_image:
            logging.error("No base64 image data found in artifact.")
            return jsonify({"error": "Image generation failed (missing image data)"}), 500

        # Decode base64 string to bytes
        image_bytes = base64.b64decode(base64_image)

        # Optional: Validate image data using Pillow
        # try:
        #     img = Image.open(io.BytesIO(image_bytes))
        #     img.verify() # Verify image integrity
        #     logging.info("Image data verified successfully.")
        # except Exception as img_err:
        #     logging.error(f"Generated image data is invalid: {img_err}")
        #     return jsonify({"error": "Generated image data is invalid"}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"Stability AI API request failed: {e}", exc_info=True)
        # Try to parse Stability's error message if available
        error_detail = str(e)
        try:
            if e.response is not None:
                error_detail = e.response.json().get('message', e.response.text)
        except Exception:
            pass # Keep original error if parsing fails
        return jsonify({"error": f"Image generation API request failed: {error_detail}"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during image generation: {e}", exc_info=True)
        return jsonify({"error": "Internal server error during image generation"}), 500

    # --- Upload to Azure ---
    unique_filename = f"{uuid.uuid4()}.png" # Generate unique filename
    image_url = upload_to_azure(image_bytes, unique_filename)

    if not image_url:
        # Error already logged in helper function
        return jsonify({"error": "Failed to upload generated image to storage"}), 500

    # --- Success ---
    logging.info(f"Successfully generated and uploaded image: {image_url}")
    return jsonify({
        "image_url": image_url,
        "prompt_used": final_prompt_used
        }), 200


# --- Run the App ---
if __name__ == '__main__':
    # Use port 5003 (different from other IEPs)
    app.run(host='0.0.0.0', port=5003, debug=False)