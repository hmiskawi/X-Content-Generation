import os
import logging
import re
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import yake # Import YAKE!
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Configure Google Generative AI Client
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    logging.error("FATAL: GOOGLE_API_KEY environment variable not set.")
else:
    try:
        genai.configure(api_key=google_api_key)
        logging.info("Google Generative AI client configured successfully.")
    except Exception as e:
        logging.error(f"Failed to configure Google Generative AI: {e}", exc_info=True)
        google_api_key = None # Ensure we know configuration failed

# Default values
DEFAULT_HASHTAG_COUNT = 4
# Use a fast, capable model like gemini-1.5-flash for this refinement task
LLM_REFINEMENT_MODEL = "gemini-1.5-flash-latest" # Or "gemini-1.0-pro" if flash isn't available/needed

# YAKE! configuration
YAKE_LANGUAGE = "en"
YAKE_MAX_NGRAM_SIZE = 2 # Consider 1 or 2 for hashtags
YAKE_DEDUPLICATION_THRESHOLD = 0.9 # How similar words should be to be considered duplicates
YAKE_NUM_KEYWORDS = 20 # Extract more candidates initially

# --- Helper Functions ---

def extract_keywords_yake(text):
    """Extracts candidate keywords using YAKE!"""
    try:
        kw_extractor = yake.KeywordExtractor(
            lan=YAKE_LANGUAGE,
            n=YAKE_MAX_NGRAM_SIZE,
            dedupLim=YAKE_DEDUPLICATION_THRESHOLD,
            top=YAKE_NUM_KEYWORDS,
            features=None
        )
        keywords = kw_extractor.extract_keywords(text)
        # Return just the keyword strings
        return [kw[0] for kw in keywords]
    except Exception as e:
        logging.error(f"YAKE keyword extraction failed: {e}", exc_info=True)
        return []

def format_as_hashtag(term):
    """Cleans a term and formats it as a hashtag."""
    # Remove leading/trailing whitespace
    term = term.strip()
    # Remove existing '#' if present
    term = term.lstrip('#')
    # Remove characters not suitable for hashtags (allow letters, numbers)
    term = re.sub(r'[^\w]+', '', term) # \w includes letters, numbers, underscore
    # Convert to lowercase (optional, but common for hashtags)
    term = term.lower()
    # Add hashtag prefix if term is not empty
    return f"#{term}" if term else None

def construct_refinement_prompt(content_context, candidate_hashtags, desired_count):
    """Constructs an enhanced prompt for LLM refinement to generate highly engaging hashtags."""

    candidates_str = ", ".join(candidate_hashtags)
    prompt = f"""
You are an expert social media strategist, known for crafting viral hashtags on X.com (Twitter). Your goal is to select or create {desired_count} highly effective hashtags that are relevant, engaging, and likely to trend based on the provided content.

### Content Summary:
\"\"\"
{content_context}
\"\"\"

### Candidate Hashtags:
[{candidates_str}]

### Your Task:
1. Analyze the content and candidate hashtags.
2. Choose or generate the BEST {desired_count} hashtags that:
   - Are tightly connected to the content.
   - Balance **broad appeal** with **niche relevance**.
   - Are emotionally engaging or thought-provoking.
   - Include **simple**, **clear**, and **impactful words**.
   - Reflect current **social trends**, culture, or hot topics (if applicable).
3. You MAY improve candidate hashtags by simplifying, merging, or rephrasing them for better engagement.
4. If the candidate list is weak, suggest better hashtags using the content context.
5. Output ONLY a **comma-separated list** of the final hashtags (no additional text or formatting).

### Example Format:
#innovation,#futureofwork,#techtrends,#ai

### Final Hashtags:
"""
    logging.info(f"Constructed Enhanced Refinement Prompt: {prompt[:500]}...")
    return prompt


# --- API Endpoint ---

@app.route('/generate/hashtags', methods=['POST'])
def generate_hashtags():
    """
    Generates X.com hashtags using keyword extraction and LLM refinement.
    """
    if not google_api_key:
        logging.error("Google Generative AI client not configured. Check API key.")
        return jsonify({"error": "Google AI client configuration error"}), 500

    if not request.is_json:
        logging.warning("Request received is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    logging.info(f"Received request data: {data}")

    # --- Input Validation ---
    content_context = data.get('content_context')
    if not content_context:
        logging.warning("Missing 'content_context' in request")
        return jsonify({"error": "Missing required field: content_context"}), 400

    # --- Get Optional Parameters ---
    user_topics = data.get('user_topics', [])
    trend_keywords = data.get('trend_keywords', [])
    desired_count = data.get('desired_count', DEFAULT_HASHTAG_COUNT)

    try:
        desired_count = int(desired_count)
        if desired_count <= 0:
            desired_count = DEFAULT_HASHTAG_COUNT
    except (ValueError, TypeError):
        logging.warning(f"Invalid desired_count value: {desired_count}. Using default.")
        desired_count = DEFAULT_HASHTAG_COUNT

    # --- 1. Keyword Extraction ---
    logging.info("Starting keyword extraction...")
    extracted_keywords = extract_keywords_yake(content_context)
    logging.info(f"Extracted keywords: {extracted_keywords}")

    # Combine all potential terms (use set for deduplication)
    combined_terms = set(extracted_keywords) | set(user_topics) | set(trend_keywords)

    # Format initial candidates as hashtags (filtering out None results)
    candidate_hashtags = [ht for term in combined_terms if (ht := format_as_hashtag(term)) is not None]

    if not candidate_hashtags:
        logging.warning("No valid candidate hashtags found after extraction and formatting.")
        # Option 1: Return empty list
        # return jsonify({"hashtags": []}), 200
        # Option 2: Rely solely on LLM based on context (adjust prompt if needed)
        # For now, proceed to LLM but inform it candidates were empty/poor
        candidate_hashtags = ["#pleasereviewcontext"] # Signal to LLM

    logging.info(f"Initial candidate hashtags: {candidate_hashtags}")

    # --- 2. LLM-Based Refinement ---
    try:
        model = genai.GenerativeModel(LLM_REFINEMENT_MODEL)
        prompt = construct_refinement_prompt(content_context, candidate_hashtags, desired_count)

        logging.info(f"Calling Google Gemini API ({LLM_REFINEMENT_MODEL}) for refinement...")

        safety_settings = [ # Re-use safety settings from Caption Gen or adjust
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]
        response = model.generate_content(prompt, safety_settings=safety_settings)

        # Check for blocks
        if not response.candidates:
             block_reason = "Unknown"
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason.name
             logging.warning(f"Gemini refinement response was blocked. Reason: {block_reason}")
             return jsonify({"error": f"Content refinement blocked by safety filter ({block_reason})."}), 400

        # Parse the LLM response (expecting comma-separated list)
        llm_output = response.text.strip()
        logging.info(f"Received raw refinement from Gemini: {llm_output}")

        # Split, clean, format, and limit count
        refined_hashtags_raw = [tag.strip() for tag in llm_output.split(',')]
        final_hashtags = [ht for tag in refined_hashtags_raw if (ht := format_as_hashtag(tag)) is not None]
        final_hashtags = final_hashtags[:desired_count] # Ensure we don't exceed desired count

        logging.info(f"Final refined hashtags: {final_hashtags}")

        return jsonify({"hashtags": final_hashtags}), 200

    # --- Error Handling (Copy relevant blocks from Caption Gen) ---
    except google_exceptions.PermissionDenied as e:
        logging.error(f"Google API Permission Denied: {e}", exc_info=True)
        return jsonify({"error": f"Google API Permission Denied: {str(e)}"}), 500
    except google_exceptions.ResourceExhausted as e:
         logging.error(f"Google API Quota Exceeded: {e}", exc_info=True)
         return jsonify({"error": f"Google API Quota Exceeded: {str(e)}"}), 429
    except google_exceptions.InvalidArgument as e:
         logging.error(f"Google API Invalid Argument: {e}", exc_info=True)
         return jsonify({"error": f"Google API Invalid Argument: {str(e)}"}), 400
    except google_exceptions.GoogleAPICallError as e:
         logging.error(f"Google API Call Error: {e}", exc_info=True)
         return jsonify({"error": f"Google API Call Error: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during refinement: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during hashtag refinement"}), 500


# --- Run the App ---
if __name__ == '__main__':
    # Use port 5002 (different from Caption Generator)
    app.run(host='0.0.0.0', port=5002, debug=False)
