# app/api.py

import os
import joblib
import pandas as pd
import numpy as np
import re
import logging
import traceback
from flask import Flask, request, jsonify
from pathlib import Path

# --- Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
# Model path relative to the 'app' directory (../models/)
DEFAULT_MODEL_PATH = SCRIPT_DIR.parent / "models" / "engagement_model_pipeline.pkl"
MODEL_PATH = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Model ---
pipeline = None
model_load_error = None
try:
    logger.info(f"Attempting to load model pipeline from: {MODEL_PATH}")
    if not Path(MODEL_PATH).is_file():
        model_load_error = f"Model file not found at {MODEL_PATH}"
        logger.error(model_load_error)
    else:
        pipeline = joblib.load(MODEL_PATH)
        logger.info("Model pipeline loaded successfully.")
except Exception as e:
    model_load_error = f"Failed to load model pipeline from {MODEL_PATH}. Error: {e}"
    logger.error(model_load_error, exc_info=True)

# --- Flask App ---
app = Flask(__name__)

# --- API Endpoints ---
@app.route('/')
def home():
    """Health check endpoint."""
    model_status = "LOADED" if pipeline is not None else f"ERROR: {model_load_error}"
    return jsonify({
        "message": "Engagement Prediction API",
        "model_status": model_status,
        "model_path_used": str(MODEL_PATH)
    })

@app.route('/predict', methods=['POST'])
def predict():
    """Prediction endpoint."""
    if pipeline is None:
        logger.error("Prediction request failed: Model pipeline is not loaded.")
        return jsonify({"error": "Model not available", "details": model_load_error}), 500

    try:
        json_data = request.get_json(force=True)
        if not json_data: raise ValueError("No input JSON data received.")
        logger.info(f"Received prediction request: {json_data}")
    except Exception as e:
        logger.warning(f"Failed to get/parse JSON input: {e}")
        return jsonify({"error": f"Invalid JSON input: {e}"}), 400

    # Validate required fields based on model training features
    required_input_fields = ["text", "has_media", "hour_of_day", "weekday"]
    missing_fields = [f for f in required_input_fields if f not in json_data]
    if missing_fields:
        msg = f"Missing required input fields: {', '.join(missing_fields)}"
        logger.warning(f"Prediction request failed: {msg}")
        return jsonify({"error": msg}), 400

    try:
        # Prepare DataFrame matching training structure
        input_text = str(json_data.get('text', ''))
        input_data = {
            'cleaned_text': [input_text], # Column expected by TF-IDF
            'has_media': [int(json_data.get('has_media', 0))],
            'hour_of_day': [int(json_data.get('hour_of_day', 12))],
            'weekday': [int(json_data.get('weekday', 0))],
            # Features calculated from text (as done during training preprocessing)
            'num_hashtags': [len(re.findall(r"#(\w+)", input_text))],
            'num_mentions': [len(re.findall(r"@(\w+)", input_text))],
            'num_urls': [len(re.findall(r"http[s]?://\S+", input_text))],
            'text_length': [len(input_text)]
        }
        input_df = pd.DataFrame(input_data)
        logger.debug(f"Input DataFrame for prediction:\n{input_df.to_string()}")

        # Make Prediction
        prediction = pipeline.predict(input_df)
        output_prediction = float(prediction[0])

        # Format Response
        response = { "predicted_relative_engagement": round(output_prediction, 4) }
        logger.info(f"Prediction successful: {response}")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error during prediction processing: {e}", exc_info=True)
        return jsonify({"error": "Internal error during prediction."}), 500

# This part is mainly for local execution, not used by Docker CMD/Waitress
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5020)) # Use 5020 as default
    # Use Waitress for local testing as well to mimic production better
    try:
        from waitress import serve
        logger.info(f"Starting Waitress server locally on http://0.0.0.0:{port}")
        serve(app, host='0.0.0.0', port=port)
    except ImportError:
        logger.warning("Waitress not found. Falling back to Flask development server (not recommended for production testing).")
        app.run(debug=False, host='0.0.0.0', port=port)