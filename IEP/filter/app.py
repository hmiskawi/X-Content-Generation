from flask import Flask, request, jsonify
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F

app = Flask(__name__)

# Load model and tokenizer
model_name = "/app/filtering_model"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
model.eval()
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

LABELS = ["NOT OK", "CAN BE FILTERED", "OK"]

@app.route('/filter', methods=['POST'])
def filter_text():
    data = request.get_json()
    text = data.get("text")
    theme = data.get("theme", "").lower()

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    # Add theme to context if provided
    input_text = f"[THEME: {theme}] {text}" if theme else text
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True).to(device)
    
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = F.softmax(logits, dim=-1)
        pred = torch.argmax(probs, dim=-1).item()

    return jsonify({
        "result": LABELS[pred],
        "probabilities": {label: float(prob) for label, prob in zip(LABELS, probs[0])}
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5022)
