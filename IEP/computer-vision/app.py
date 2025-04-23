from flask import Flask, request, jsonify
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import os

app = Flask(__name__)

# Load model and processor
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base").eval()

# Use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

@app.route('/caption', methods=['POST'])
def caption_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = Image.open(request.files['image']).convert("RGB")
    strategy = request.form.get('strategy', 'creative')

    inputs = processor(image, return_tensors="pt").to(device)

    if strategy == 'greedy':
        out = model.generate(**inputs)
    else:
        out = model.generate(
            **inputs,
            max_length=50,
            num_beams=5,
            do_sample=True,
            temperature=1.0,
            top_p=0.9,
            repetition_penalty=1.2
        )

    caption = processor.decode(out[0], skip_special_tokens=True)
    return jsonify({"caption": caption})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5021))
    app.run(host='0.0.0.0', port=port)
