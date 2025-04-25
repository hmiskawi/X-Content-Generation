from flask import Flask, request, jsonify
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import os
import logging

app = Flask(__name__)

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load model and processor
model_name = "Salesforce/blip-image-captioning-base"
model = None
processor = None
device = "cpu"

try:
    logging.info(f"Loading model and processor: {model_name}")
    processor = BlipProcessor.from_pretrained(model_name)
    model = BlipForConditionalGeneration.from_pretrained(model_name)

    # Use GPU if available
    if torch.cuda.is_available():
        device = "cuda"
        logging.info("CUDA available. Moving model to GPU.")
    else:
        logging.info("CUDA not available. Using CPU.")
    model.to(device)
    model.eval() # Set model to evaluation mode
    logging.info(f"Model and processor loaded successfully on {device}.")

except Exception as e:
    logging.error(f"Error loading model or processor: {e}", exc_info=True)

@app.route('/describe_image', methods=['POST'])
def describe_image():
    """
    Generates a caption for an uploaded image using the BLIP model.
    Expects a POST request with a file part named 'image'.
    Optionally accepts 'strategy' form data ('greedy' or 'creative').
    """
    if model is None or processor is None:
         logging.error("Model or processor not loaded. Cannot process request.")
         return jsonify({"error": "Computer vision model is not available"}), 503

    if 'image' not in request.files:
        logging.warning("Request received without 'image' file part.")
        return jsonify({"error": "No image file provided in 'image' part"}), 400

    try:
        image_file = request.files['image']
        logging.info(f"Received image file: {image_file.filename}")
        # Open image and ensure it's RGB
        image = Image.open(image_file).convert("RGB")
    except Exception as e:
        logging.error(f"Failed to open or process image file: {e}", exc_info=True)
        return jsonify({"error": "Invalid or corrupted image file"}), 400

    # Default strategy is creative/beam search
    strategy = request.form.get('strategy', 'creative')
    logging.info(f"Captioning strategy: {strategy}")

    try:
        # Prepare inputs for the model
        inputs = processor(image, return_tensors="pt").to(device)

        # Generate caption based on strategy
        with torch.no_grad(): # Ensure gradients are not computed
            if strategy == 'greedy':
                # Use default settings for greedy search (often max_length=20)
                out = model.generate(**inputs, max_length=20)
            else:
                # Creative: use beam search with sampling parameters
                out = model.generate(
                    **inputs,
                    max_length=50,       # Longer captions allowed
                    num_beams=5,         # Beam search
                    do_sample=True,      # Enable sampling
                    temperature=1.0,     # Control randomness (1.0 is standard)
                    top_p=0.9,           # Nucleus sampling
                    repetition_penalty=1.2 # Penalize repeated words/phrases
                )

        # Decode the generated IDs to text
        caption = processor.decode(out[0], skip_special_tokens=True)
        logging.info(f"Generated caption: {caption}")

        return jsonify({"description": caption}) # Return key "description" to match orchestrator simulation

    except Exception as e:
        logging.error(f"Error during image captioning inference: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate caption due to internal server error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5021))
    app.run(host='0.0.0.0', port=port, debug=False)