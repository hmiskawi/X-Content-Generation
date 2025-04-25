import os
import joblib
import pandas as pd
import numpy as np
import re
import logging
import traceback
from flask import Flask, request, jsonify
from pathlib import Path
# Import necessary libraries used during training/preprocessing
import lightgbm as lgb # Good practice, though joblib loads it
from sentence_transformers import SentenceTransformer

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
# Default paths relative to the 'app' directory
DEFAULT_LGBM_MODEL_PATH = SCRIPT_DIR.parent / "models" / "engagement_model.pkl"
DEFAULT_ENCODER_PATH = SCRIPT_DIR.parent / "text_encoder" # Directory

# Get paths from environment or use defaults
LGBM_MODEL_PATH = Path(os.environ.get("LGBM_MODEL_PATH", DEFAULT_LGBM_MODEL_PATH))
ENCODER_PATH = Path(os.environ.get("ENCODER_PATH", DEFAULT_ENCODER_PATH))

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Models ---
lgbm_model = None
text_encoder = None
model_load_error = "" # Accumulate errors

# Load LGBM Model
try:
    logger.info(f"Attempting to load LGBM model from: {LGBM_MODEL_PATH}")
    if not LGBM_MODEL_PATH.is_file():
        error_msg = f"LGBM Model file not found at {LGBM_MODEL_PATH}."
        model_load_error += error_msg + " "
        logger.error(error_msg)
    else:
        lgbm_model = joblib.load(LGBM_MODEL_PATH)
        logger.info("LGBM model loaded successfully.")
except Exception as e:
    error_msg = f"Failed to load LGBM model from {LGBM_MODEL_PATH}. Error: {e}"
    model_load_error += error_msg + " "
    logger.error(error_msg, exc_info=True)

# Load Sentence Transformer
try:
    logger.info(f"Attempting to load Sentence Transformer from: {ENCODER_PATH}")
    # Check if it's a directory and contains a typical config file
    if not ENCODER_PATH.is_dir() or not (ENCODER_PATH / "config.json").is_file():
         error_msg = f"Text encoder directory or essential files not found at {ENCODER_PATH}."
         model_load_error += error_msg + " "
         logger.error(error_msg)
    else:
        text_encoder = SentenceTransformer(str(ENCODER_PATH)) # Load from directory path
        logger.info("Sentence Transformer loaded successfully.")
except Exception as e:
    error_msg = f"Failed to load Sentence Transformer from {ENCODER_PATH}. Error: {e}"
    model_load_error += error_msg + " "
    logger.error(error_msg, exc_info=True)

model_load_error = model_load_error.strip() if model_load_error else None


# --- Flask App ---
app = Flask(__name__)

# --- API Endpoints ---
@app.route('/')
def home():
    """Health check endpoint."""
    lgbm_status = "LOADED" if lgbm_model is not None else "ERROR"
    encoder_status = "LOADED" if text_encoder is not None else "ERROR"
    model_status = f"LGBM: {lgbm_status}, Encoder: {encoder_status}"
    if model_load_error:
        model_status += f" | Errors: {model_load_error}"

    return jsonify({
        "message": "Engagement Prediction API",
        "model_status": model_status,
        "lgbm_model_path_used": str(LGBM_MODEL_PATH),
        "encoder_path_used": str(ENCODER_PATH)
    })

@app.route('/predict', methods=['POST'])
def predict():
    """Prediction endpoint."""
    # Check if both models are loaded
    if lgbm_model is None or text_encoder is None:
        error_msg = "Prediction request failed: One or more models are not loaded."
        logger.error(f"{error_msg} Details: {model_load_error}")
        return jsonify({"error": error_msg, "details": model_load_error}), 500

    try:
        json_data = request.get_json(force=True)
        if not json_data: raise ValueError("No input JSON data received.")
        logger.info(f"Received prediction request: {json_data}")
    except Exception as e:
        logger.warning(f"Failed to get/parse JSON input: {e}")
        return jsonify({"error": f"Invalid JSON input: {e}"}), 400

    # Validate required fields from the API perspective
    required_input_fields = ["text", "has_media", "hour_of_day", "weekday"]
    missing_fields = [f for f in required_input_fields if f not in json_data]
    if missing_fields:
        msg = f"Missing required input fields: {', '.join(missing_fields)}"
        logger.warning(f"Prediction request failed: {msg}")
        return jsonify({"error": msg}), 400

    try:
        # --- Replicate Training Preprocessing ---
        input_text = str(json_data.get('text', ''))

        # 1. Get Text Embedding using loaded SentenceTransformer
        # Pass text as a list, get NumPy array of shape (1, 384)
        text_embedding = text_encoder.encode([input_text], normalize_embeddings=True)
        logger.debug(f"Text embedding shape: {text_embedding.shape}")

        # 2. Prepare Metadata Features (ensure type and order match training)
        # Training used: ["text_length", "has_media", "hour", "weekday"]
        text_length = len(input_text)
        has_media = int(json_data.get('has_media', 0))
        # Map API input 'hour_of_day' to training feature 'hour'
        hour = int(json_data.get('hour_of_day', 12))
        weekday = int(json_data.get('weekday', 0)) # Name matches training

        # Create the metadata array in the exact order used for hstack during training
        meta_features = np.array([[text_length, has_media, hour, weekday]]) # Shape (1, 4)
        logger.debug(f"Meta features shape: {meta_features.shape}")
        logger.debug(f"Meta features values: {meta_features}")

        # 3. Combine features using hstack (ensure order matches training)
        # Training used: np.hstack((X_text, X_meta))
        final_features = np.hstack((text_embedding, meta_features)) # Shape (1, 384 + 4 = 388)
        logger.debug(f"Final features shape for prediction: {final_features.shape}")

        # --- Make Prediction using loaded LGBM model ---
        # lgbm_model.predict expects a NumPy array
        prediction = lgbm_model.predict(final_features)

        # prediction is likely array([value]), extract the scalar
        output_prediction = float(prediction[0])

        # Format Response
        response = { "predicted_relative_engagement": round(output_prediction, 4) }
        logger.info(f"Prediction successful: {response}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error during prediction processing: {e}", exc_info=True)
        # Optionally include traceback in development/debug mode
        # error_details = traceback.format_exc()
        return jsonify({"error": "Internal error during prediction.", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5010))
    logger.info(f"Starting Flask development server locally on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)