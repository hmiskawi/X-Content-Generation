import os
import logging
import re
from flask import Flask, request, jsonify
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import nltk
from nltk.corpus import wordnet
from dotenv import load_dotenv

# --- NLTK Download Check (For safety, although Dockerfile should handle it) ---
try:
    # Check if wordnet is available, download if missing (might fail in restricted envs)
    nltk.data.find('corpora/wordnet.zip')
except nltk.downloader.DownloadError:
    logging.warning("NLTK 'wordnet' data not found. Attempting download...")
    try:
        nltk.download('wordnet', quiet=True)
        nltk.download('punkt', quiet=True) # Often needed alongside wordnet
        logging.info("NLTK data downloaded successfully.")
    except Exception as download_e:
        logging.error(f"Failed to download NLTK data: {download_e}. Enrichment may fail.")
except Exception as find_e:
     logging.error(f"Error checking NLTK data: {find_e}")


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
        google_api_key = None

# Default values
LLM_REFINEMENT_MODEL = "gemini-1.5-flash-latest" # Fast and capable model
DEFAULT_SUGGESTION_COUNT = 7 # Target ~5-10, aiming for 7

# --- Helper Functions ---

def enrich_keywords_wordnet(keywords: list[str]) -> set[str]:
    """Enriches keywords using WordNet synonyms."""
    enriched = set()
    if not keywords:
        return enriched

    for keyword in keywords:
        processed_keyword = keyword.lower().replace(" ", "_") # Format for wordnet lookup
        synsets = wordnet.synsets(processed_keyword)
        if not synsets:
             # If no synset for multi-word, try splitting
             if "_" in processed_keyword:
                  for part in processed_keyword.split("_"):
                       for syn in wordnet.synsets(part):
                            for lemma in syn.lemmas():
                                enriched.add(lemma.name().replace("_", " ").lower())
             else:
                  enriched.add(keyword.lower()) # Keep original if no synset found
             continue

        for syn in synsets:
            for lemma in syn.lemmas():
                # Add synonyms, replacing underscores with spaces
                enriched.add(lemma.name().replace("_", " ").lower())

    # Also add the original keywords back (lowercased)
    enriched.update([k.lower() for k in keywords])
    logging.info(f"WordNet enrichment produced: {list(enriched)[:15]}...") # Log some results
    return enriched

def clean_keyword(keyword: str) -> str | None:
    """Cleans a keyword: lowercase, removes non-alphanumeric (keeps spaces)."""
    if not keyword:
        return None
    # Remove leading/trailing whitespace
    cleaned = keyword.strip().lower()
    # Allow letters, numbers, and spaces. Remove other punctuation.
    cleaned = re.sub(r'[^\w\s]+', '', cleaned)
    # Remove extra internal spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else None

def construct_refinement_prompt(original_keywords, enriched_keywords, image_context, username, desired_count):
    """Constructs an enhanced prompt for the LLM refinement step to generate engaging, high-performance keywords."""

    enriched_str = ", ".join(list(enriched_keywords)[:30])  # Limit to 30 terms for token efficiency

    prompt = f"""
You are a top-tier social media strategist, with a deep understanding of what makes keywords drive high engagement and visibility on X.com (Twitter).

### Goal:
Refine and enhance the provided keywords into a final list of **exactly {desired_count} high-performance keywords**. These keywords should be optimized for discoverability, relevance, and emotional appeal, suitable for a viral social media post.

### Context:
- **User:** {username if username else 'Anonymous'}
- **Original Keywords:** {', '.join(original_keywords)}
- **Related Keyword Suggestions:** {enriched_str}
"""

    if image_context:
        prompt += f"- **Image Context:** {image_context}\n"

    prompt += f"""
### Instructions:
1. Analyze the original and enriched keywords and the image context.
2. Refine or generate **{desired_count} keywords** that:
   - Are **highly relevant** to the topic.
   - Reflect **current trends**, buzzwords, or cultural hooks.
   - Evoke curiosity, excitement, or emotional engagement.
   - Are **succinct**, impactful, and **easy to search**.
   - Mix **specific niche terms** with broader popular terms.
3. If the provided keywords are weak, replace them with better alternatives.
4. **Do not include** hashtags (#) or special characters.
5. Format the final output as a **comma-separated list**: keyword 1, keyword 2, keyword 3, ...

### Example Output:
creativity tools, future of ai, tech innovation, productivity hacks, digital art trends

### Final Optimized Keywords:
"""

    logging.info(f"Constructed Enhanced Refinement Prompt: {prompt[:500]}...")
    return prompt


# --- API Endpoint ---

@app.route('/generate/keywords', methods=['POST'])
def suggest_keywords():
    """Suggests improved keywords based on initial input, enrichment, and LLM refinement."""
    if not google_api_key:
        logging.error("Google Generative AI client not configured. Check API key.")
        return jsonify({"error": "Keyword suggestion service not configured (LLM)"}), 500

    if not request.is_json:
        logging.warning("Request received is not JSON")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    logging.info(f"Received request data: {data}")

    # --- Input Validation ---
    initial_keywords = data.get('keywords')
    if not initial_keywords or not isinstance(initial_keywords, list) or len(initial_keywords) == 0:
        logging.warning("Missing or invalid 'keywords' list in request")
        return jsonify({"error": "Missing or invalid required field: keywords (must be a non-empty list)"}), 400

    # --- Get Optional Parameters ---
    username = data.get('username') # Optional context, used in prompt
    image_context = data.get('image_context') # Optional context
    desired_count = DEFAULT_SUGGESTION_COUNT # Fixed for now, could be input later

    # --- 1. Keyword Enrichment ---
    logging.info("Starting keyword enrichment using WordNet...")
    enriched_terms = enrich_keywords_wordnet(initial_keywords)
    if not enriched_terms:
         # If enrichment fails completely, at least use originals
         enriched_terms = set(k.lower() for k in initial_keywords)

    # --- 2. LLM-Based Refinement ---
    try:
        model = genai.GenerativeModel(LLM_REFINEMENT_MODEL)
        prompt = construct_refinement_prompt(
            initial_keywords,
            enriched_terms,
            image_context,
            username,
            desired_count
        )

        logging.info(f"Calling Google Gemini API ({LLM_REFINEMENT_MODEL}) for keyword refinement...")

        safety_settings = [ # Standard safety settings
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
             logging.warning(f"Gemini keyword refinement response was blocked. Reason: {block_reason}")
             return jsonify({"error": f"Keyword generation blocked by safety filter ({block_reason})."}), 400

        # Parse the LLM response
        llm_output = response.text.strip()
        logging.info(f"Received raw refinement from Gemini: {llm_output}")

        # Split, clean, deduplicate
        raw_suggestions = [tag.strip() for tag in llm_output.split(',')]
        final_keywords_set = set()
        for k in raw_suggestions:
            cleaned = clean_keyword(k)
            if cleaned:
                final_keywords_set.add(cleaned)

        final_keywords_list = list(final_keywords_set)
        # Optional: Trim if LLM gave too many, though prompt requests exact count
        final_keywords_list = final_keywords_list[:desired_count]

        logging.info(f"Final refined keywords: {final_keywords_list}")

        if not final_keywords_list:
             logging.warning("LLM refinement resulted in an empty keyword list.")
             final_keywords_list = [cleaned_k for k in initial_keywords if (cleaned_k := clean_keyword(k))]


        return jsonify({"improved_keywords": final_keywords_list}), 200

    # --- Error Handling (Similar to other IEPs) ---
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
        logging.error(f"An unexpected error occurred during keyword suggestion: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred during keyword suggestion"}), 500


# --- Run the App ---
if __name__ == '__main__':
    # Use port 5004 (different from other IEPs)
    app.run(host='0.0.0.0', port=5004, debug=False)