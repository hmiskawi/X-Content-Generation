import os
import logging
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions # Import Google API exceptions
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()  # Load environment variables from .env for local development

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)

# Configure Google Generative AI Client
google_api_key = os.getenv("GOOGLE_API_KEY") # <<< CHANGED
if not google_api_key:
    logging.error("FATAL: GOOGLE_API_KEY environment variable not set.") # <<< CHANGED
    # Decide how to handle this - exit or let it fail later?
    # For now, we allow startup but API calls will fail.
else:
    try:
        genai.configure(api_key=google_api_key)
        logging.info("Google Generative AI client configured successfully.")
    except Exception as e:
        # Catch potential configuration errors (though less common than client calls)
        logging.error(f"Failed to configure Google Generative AI: {e}", exc_info=True)
        google_api_key = None # Ensure we know configuration failed

# Default values
DEFAULT_TONE = "informative"
DEFAULT_MAX_LENGTH = 280
DEFAULT_MODEL = "gemini-2.0-flash"

# --- Helper Functions ---

def construct_gemini_prompt(context_summary, user_profile_summary, relevant_trends, tone_preference, max_length):
    """Constructs a refined prompt for the Gemini model to generate tweet-style captions."""

    prompt_parts = [
        "You are a professional social media content creator specializing in viral, engaging, and concise tweets for X.com.",
        "Your task is to craft a tweet that captures attention, sparks interest, and aligns with the provided context.",
        "",
        "## Guidelines:",
        f"- Tone: {tone_preference}. Match the tone naturally.",
        f"- Keep it within {max_length} characters. Be punchy, bold, or witty depending on the context.",
        "- Do NOT include hashtags or URLs in the tweet.",
        "- Avoid introductions like 'Here is your tweet:' or quotes around the text.",
        "- Output ONLY the tweet, exactly as it should appear.",
    ]

    prompt_parts.extend([
        "",
        "## Post Context:",
        context_summary
    ])

    if user_profile_summary:
        prompt_parts.extend([
            "",
            "## User Style & Audience Insights:",
            user_profile_summary
        ])

    if relevant_trends:
        trends_str = ", ".join(relevant_trends)
        prompt_parts.extend([
            "",
            "## Relevant Trends to Consider (optional, subtle use encouraged):",
            trends_str
        ])

    prompt_parts.append("")
    prompt_parts.append("Now, generate a tweet that fits the above context and tone.")

    final_prompt = "\n".join(prompt_parts)
    logging.info(f"Constructed Gemini Prompt: {final_prompt[:500]}...")
    return final_prompt


# --- API Endpoint ---

@app.route('/generate/caption', methods=['POST'])
def generate_caption():
    """
    Generates an X.com caption based on input context using Google Gemini Pro.
    Expects JSON input with 'context_summary' and optional fields.
    Returns JSON output with the generated 'caption'.
    """
    if not google_api_key: # Check if configuration failed earlier
        logging.error("Google Generative AI client not configured. Check API key.")
        return jsonify({"error": "Google AI client configuration error"}), 500

    if not request.is_json:
        logging.warning("Request received is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    logging.info(f"Received request data: {data}")

    # --- Input Validation ---
    context_summary = data.get('context_summary')
    if not context_summary:
        logging.warning("Missing 'context_summary' in request")
        return jsonify({"error": "Missing required field: context_summary"}), 400

    # --- Get Optional Parameters ---
    user_profile_summary = data.get('user_profile_summary', None)
    relevant_trends = data.get('relevant_trends', []) # Expecting a list
    tone_preference = data.get('tone_preference', DEFAULT_TONE)
    max_length = data.get('max_length', DEFAULT_MAX_LENGTH)

    try:
        max_length = int(max_length)
    except (ValueError, TypeError):
        logging.warning(f"Invalid max_length value: {max_length}. Using default.")
        max_length = DEFAULT_MAX_LENGTH

    # --- Core Logic: Call Google Gemini API ---
    try:
        # Initialize the specific model
        model = genai.GenerativeModel(DEFAULT_MODEL)

        # Construct the prompt
        prompt = construct_gemini_prompt(
            context_summary,
            user_profile_summary,
            relevant_trends,
            tone_preference,
            max_length
        )

        logging.info(f"Calling Google Gemini API with model: {DEFAULT_MODEL}")

        # --- Generate content ---
        # Add safety settings (adjust levels as needed - see Gemini docs)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = model.generate_content(prompt, safety_settings=safety_settings)

        # --- Handle Potential Blocks ---
        # Check if the response was blocked due to safety settings or other reasons
        if not response.candidates:
             # Find the block reason if available
             block_reason = "Unknown"
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason.name
             logging.warning(f"Gemini response was blocked. Reason: {block_reason}")
             # You might want to return a specific error or a generic placeholder
             return jsonify({"error": f"Content generation blocked by safety filter ({block_reason}). Please revise input."}), 400

        # --- Extract Text ---
        # Access the generated text - use response.text for simple cases
        generated_caption = response.text.strip()
        logging.info(f"Successfully received caption from Gemini: {generated_caption}")

        # Optional: Add alternative generation logic here if needed

        return jsonify({
            "caption": generated_caption,
            # "alternatives": [] # Add alternatives if implemented
            }), 200

    # --- Specific Google API Error Handling ---
    except google_exceptions.PermissionDenied as e:
        logging.error(f"Google API Permission Denied (check API key?): {e}", exc_info=True)
        return jsonify({"error": f"Google API Permission Denied: {str(e)}"}), 500 # Or 403?
    except google_exceptions.ResourceExhausted as e:
         logging.error(f"Google API Quota Exceeded: {e}", exc_info=True)
         return jsonify({"error": f"Google API Quota Exceeded: {str(e)}"}), 429 # 429 Too Many Requests
    except google_exceptions.InvalidArgument as e:
         logging.error(f"Google API Invalid Argument (check prompt/params?): {e}", exc_info=True)
         return jsonify({"error": f"Google API Invalid Argument: {str(e)}"}), 400
    except google_exceptions.GoogleAPICallError as e:
         logging.error(f"Google API Call Error: {e}", exc_info=True)
         return jsonify({"error": f"Google API Call Error: {str(e)}"}), 500
    except Exception as e:
        # General catch-all
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred"}), 500

# --- Run the App ---
if __name__ == '__main__':
    # Host '0.0.0.0' makes it accessible within the Docker network
    # Port 5001 is an example, choose a unique port for this IEP
    app.run(host='0.0.0.0', port=5011, debug=False)
