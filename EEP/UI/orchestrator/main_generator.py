# orchestrator/main_generator.py (Updated with Theme Handling)

import argparse
import logging
import requests # Keep for future implementation
import json
import random
from datetime import datetime
from pathlib import Path
import time
import os
from typing import Optional, List, Dict, Any, Tuple # Added Tuple

# --- Configuration ---
# Load from environment variables or use defaults
IEP_SERVICE_URLS = {
    "caption_generator": os.environ.get("CAPTION_GENERATOR_URL", "http://localhost:5011/generate/caption"),
    "computer_vision": os.environ.get("COMPUTER_VISION_URL", "http://localhost:5012/describe_image"),
    "engagement_prediction": os.environ.get("ENGAGEMENT_PREDICTOR_URL", "http://localhost:5010/predict"),
    "filter": os.environ.get("FILTER_URL", "http://localhost:5013/filter"),
    "hashtag_generator": os.environ.get("HASHTAG_GENERATOR_URL", "http://localhost:5014/generate/hashtags"),
    "image_generator": os.environ.get("IMAGE_GENERATOR_URL", "http://localhost:5015/generate/image"),
    "keyword_suggester": os.environ.get("KEYWORD_SUGGESTER_URL", "http://localhost:5016/generate/keywords"),
    "past_tweet_analyzer": os.environ.get("PAST_TWEET_ANALYZER_URL", "http://localhost:5017/analyze/past-tweets"),
    "trend_analyzer": os.environ.get("TREND_ANALYZER_URL", "http://localhost:5018/analyze/trends"),
}
# Define paths relative to *this* script file
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent # Assumes orchestrator is one level down from root
OUTPUT_DIR = PROJECT_ROOT / "generated_content"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
DEFAULT_USERNAME = "DefaultUser"
NUM_CAPTION_CANDIDATES = 3 # Keep default internal generation count

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

# --- API Call Simulation (Updated Filter Simulation) ---
def call_api(service_name: str, method: str = "POST", data: Optional[Dict] = None, files: Optional[Dict] = None, timeout: int = DEFAULT_API_TIMEOUT) -> Dict:
    """
    Calls an IEP API endpoint using the requests library.

    Args:
        service_name: The key corresponding to the service in IEP_SERVICE_URLS.
        method: HTTP method ('GET', 'POST'). Defaults to 'POST'.
        data: Dictionary payload (sent as JSON for POST, query params for GET).
        files: Dictionary for multipart/form-data file uploads (e.g., {'image': file_object}).
               Only used for POST requests.
        timeout: Request timeout in seconds.

    Returns:
        A dictionary containing the JSON response from the API,
        or a dictionary with an 'error' key if the call fails.
    """
    url = IEP_SERVICE_URLS.get(service_name)
    if not url:
        logging.error(f"Service URL for '{service_name}' not configured.")
        return {"error": f"Service '{service_name}' URL not configured", "status_code": None}

    # Prepare data (ensure None is handled gracefully)
    request_data = data if data is not None else {}
    request_files = files if files is not None else {}

    # Log the call details (mask sensitive data if necessary in production)
    logging.info(f"Making {method.upper()} request to {service_name} at {url} with data keys: {list(request_data.keys())}, files: {list(request_files.keys())}")

    headers = {
        "Accept": "application/json"
        # Content-Type is typically handled by requests based on 'json' or 'files' params
    }

    try:
        response = None
        if method.upper() == "POST":
            if request_files:
                # Send as multipart/form-data if files are present
                # 'data' here should contain non-file form fields
                response = requests.post(url, data=request_data, files=request_files, headers=headers, timeout=timeout)
            else:
                # Send as JSON payload if no files
                response = requests.post(url, json=request_data, headers=headers, timeout=timeout)
        elif method.upper() == "GET":
            response = requests.get(url, params=request_data, headers=headers, timeout=timeout)
        else:
            logging.error(f"Unsupported HTTP method '{method}' for service {service_name}")
            return {"error": f"Unsupported HTTP method: {method}", "status_code": None}

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # Attempt to parse the JSON response
        try:
            response_json = response.json()
            logging.info(f"Received successful response from {service_name} (Status: {response.status_code})")
            # logging.debug(f"Response JSON from {service_name}: {response_json}") # Be careful logging full responses
            return response_json
        except json.JSONDecodeError as json_err:
            logging.error(f"Failed to decode JSON response from {service_name} (Status: {response.status_code}). Response text: {response.text[:500]}...") # Log beginning of text
            return {"error": "Invalid JSON response from service", "status_code": response.status_code, "details": str(json_err)}

    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP errors (e.g., 404 Not Found, 500 Internal Server Error)
        error_details = f"HTTP Error: {http_err}"
        try:
            # Try to get more details from the response body if possible
            error_body = http_err.response.json()
            error_details += f" - Response: {error_body}"
        except json.JSONDecodeError:
            error_details += f" - Response Text: {http_err.response.text[:500]}..."
        except Exception: # Catch other potential issues with accessing response
             pass
        logging.error(f"API call failed for {service_name} (Status: {http_err.response.status_code}). {error_details}")
        return {"error": "HTTP error calling service", "status_code": http_err.response.status_code, "details": error_details}

    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"API call failed for {service_name}. Could not connect to {url}. Error: {conn_err}")
        return {"error": "Connection error calling service", "status_code": None, "details": str(conn_err)}

    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"API call timed out for {service_name} after {timeout}s. Error: {timeout_err}")
        return {"error": "Request timed out calling service", "status_code": None, "details": str(timeout_err)}

    except requests.exceptions.RequestException as req_err:
        # Catch other potential request errors
        logging.error(f"API call failed for {service_name}. Error: {req_err}", exc_info=True)
        return {"error": "General request error calling service", "status_code": None, "details": str(req_err)}

    except Exception as e:
        # Catch any other unexpected errors during the process
        logging.error(f"An unexpected error occurred when calling {service_name}: {e}", exc_info=True)
        return {"error": "An unexpected error occurred", "status_code": None, "details": str(e)}

# --- Main Orchestration Function ---
def generate_post_candidates(username: str,
                             keyword: Optional[str],
                             image_path: Optional[str],
                             theme: str = "casual") -> Tuple[List[Dict[str, Any]], Dict]: # Added theme parameter, default 'casual'
    """Generates multiple post candidates and returns them scored and filtered."""
    logging.info(f"--- Starting Candidate Generation Workflow for user: '{username}', Theme: '{theme}' ---") # Log theme
    if not username: username = DEFAULT_USERNAME; logging.warning(f"Using default username: {username}")

    candidates = []
    intermediate_results = {"input_theme": theme} # Store input theme

    # --- Phase 1: Context Gathering ---
    logging.info("--- Phase 1: Context Gathering ---")
    user_profile_info = call_api("past_tweet_analyzer", data={"username": username})
    intermediate_results["user_profile_analysis"] = user_profile_info.get('error', user_profile_info)
    trends_info = call_api("trend_analyzer", method="GET")
    intermediate_results["trend_analysis"] = trends_info.get('error', trends_info)
    user_style_summary = f"Style: {user_profile_info.get('tweeting_style', 'unknown')}. Tone: {user_profile_info.get('tone', 'unknown')}. Emojis: {user_profile_info.get('emoji_usage', 'unknown')}."
    user_topics = user_profile_info.get("common_themes", [])
    relevant_trends_list = trends_info.get("tech_trends", []) + trends_info.get("top_hashtags", [])


    # --- Phase 2: Keyword Processing ---
    logging.info("--- Phase 2: Keyword Processing ---")
    topic_keyword = keyword
    if not topic_keyword:
        available_keywords = user_topics + trends_info.get("tech_trends", [])
        topic_keyword = random.choice(available_keywords) if available_keywords else "innovation"
        logging.info(f"Derived keyword: '{topic_keyword}'")
    intermediate_results["selected_keyword"] = topic_keyword


    # --- Phase 3: Image Handling ---
    logging.info("--- Phase 3: Image Handling ---")
    base_image_ref = None
    base_image_description = None
    base_has_media = False
    if image_path:
        logging.info(f"Processing provided image: {image_path}")
        if Path(image_path).is_file():
            cv_result = call_api("computer_vision", data={}, files={"image_placeholder": True})
            intermediate_results["computer_vision_result"] = cv_result.get('error', cv_result)
            if "description" in cv_result: base_image_description = cv_result["description"]; logging.info(f"Image description: {base_image_description}")
            base_image_ref = image_path; base_has_media = True
        else: logging.error(f"Input image file not found: {image_path}")
    else:
        logging.info("No input image provided. Generating base image...")
        # Incorporate theme into image prompt
        img_prompt = f"Visually interesting graphic representing '{topic_keyword}', theme: {theme}, {user_profile_info.get('tone', 'professional')} tone, social media style."
        img_style_pref = "photorealistic" if theme=="serious" else ("cartoon" if theme=="memes" else "digital painting") # Example style mapping
        img_gen_result = call_api("image_generator", data={"prompt": img_prompt, "aspect_ratio": "16:9", "style_preference": img_style_pref, "theme": theme}) # Pass theme too
        intermediate_results["image_generation_result"] = img_gen_result.get('error', img_gen_result)
        if "image_url" in img_gen_result: base_image_ref = img_gen_result["image_url"]; base_has_media = True; logging.info(f"Generated base image URL: {base_image_ref}")
        else: logging.warning("Base image generation failed.")
    intermediate_results["base_image_reference"] = base_image_ref
    intermediate_results["base_has_media_flag"] = base_has_media


    # --- Phase 4: Generate and Evaluate Candidates ---
    logging.info(f"--- Phase 4: Generating & Evaluating {NUM_CAPTION_CANDIDATES} Caption Candidates ---")
    for i in range(NUM_CAPTION_CANDIDATES):
        logging.info(f"--- Generating Candidate Set {i+1}/{NUM_CAPTION_CANDIDATES} ---")

        # 4a. Generate Caption - pass theme preference
        caption_context_summary = f"Topic: {topic_keyword}."
        if base_has_media and base_image_description: caption_context_summary += f" Associated image: {base_image_description}"
        caption_tone_pref = "humorous" if theme == "memes" else ("professional" if theme == "serious" else user_profile_info.get('tone', 'informative'))
        caption_payload = { "context_summary": caption_context_summary, "user_profile_summary": user_style_summary,
                            "relevant_trends": relevant_trends_list, "tone_preference": caption_tone_pref,
                            "requested_theme": theme, "max_length": 260 } # Pass theme for context
        caption_result = call_api("caption_generator", data=caption_payload)
        if "caption" not in caption_result: logging.warning(f"Failed caption gen {i+1}. Skipping. Err: {caption_result.get('error')}"); continue
        generated_caption = caption_result["caption"]; logging.info(f"  Caption {i+1}: {generated_caption}")

        # 4b. Generate Hashtags - pass theme
        hashtag_payload = { "content_context": f"{topic_keyword} {generated_caption}", "user_topics": user_topics,
                            "trend_keywords": trends_info.get("top_hashtags", []), "theme": theme, "desired_count": 5 }
        hashtag_result = call_api("hashtag_generator", data=hashtag_payload)
        generated_hashtags = hashtag_result.get("hashtags", []); logging.info(f"  Hashtags {i+1}: {generated_hashtags}")

        # 4c. Text Variations
        text_variations = { "with_hashtags": f"{generated_caption} {' '.join(h for h in generated_hashtags if h)}",
                            "without_hashtags": generated_caption }
        # 4d. Media Variations
        media_variations = { "no_media": {"ref": None, "flag": False} }
        if base_has_media: media_variations["with_media"] = {"ref": base_image_ref, "flag": True}

        # 4e. Evaluate each combination
        for text_label, text_content in text_variations.items():
            for media_label, media_info in media_variations.items():
                candidate_id = f"cand_{i+1}_{text_label}_{media_label}"
                logging.info(f"    Evaluating {candidate_id}...")

                # Filter - Pass theme
                filter_payload = {"text": text_content, "theme": theme}
                filter_result = call_api("filter", data=filter_payload)
                filter_status = filter_result.get("status", "ERROR"); filter_reason = filter_result.get('reason', 'N/A')
                logging.info(f"      Filter Status: {filter_status} (Reason: {filter_reason})")

                predicted_engagement = None
                if filter_status != "NOT OK":
                    # Predict Engagement
                    prediction_payload = { "text": text_content, "has_media": 1 if media_info["flag"] else 0,
                                           "hour_of_day": datetime.now().hour, "weekday": datetime.now().weekday() }
                    engagement_result = call_api("engagement_prediction", data=prediction_payload)
                    predicted_engagement = engagement_result.get("predicted_relative_engagement")
                    if predicted_engagement is not None: logging.info(f"      Predicted Engagement: {predicted_engagement:.4f}")
                    else: logging.warning(f"      Engagement prediction failed: {engagement_result.get('error')}")
                else: logging.warning("      Skipping engagement prediction due to NOT OK filter status.")

                # Store candidate
                candidates.append({
                    "candidate_id": candidate_id, "username": username, "selected_keyword": topic_keyword,
                    "image_description": base_image_description if media_info["flag"] else None,
                    "generated_caption": generated_caption,
                    "generated_hashtags": generated_hashtags if text_label == "with_hashtags" else [],
                    "final_text": text_content, "image_reference": media_info["ref"], "has_media": media_info["flag"],
                    "filter_status": filter_status, "filter_reason": filter_reason,
                    "predicted_relative_engagement": predicted_engagement, "timestamp_generated": datetime.now().isoformat()
                })

    logging.info(f"--- Finished evaluating {len(candidates)} total candidates ---")
    return candidates, intermediate_results


# --- Post-Processing and Selection ---
def select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Selects the best candidate based on filter status and predicted engagement."""
    if not candidates: logging.warning("No candidates generated."); return None
    valid_candidates = [c for c in candidates if c.get("filter_status") in ["OK", "CAN BE CHANGED"] and c.get("predicted_relative_engagement") is not None]
    if not valid_candidates: logging.warning("No candidates passed filter or received an engagement score."); return None
    valid_candidates.sort(key=lambda x: x["predicted_relative_engagement"], reverse=True)
    best_candidate = valid_candidates[0]
    logging.info(f"Selected best candidate: {best_candidate.get('candidate_id')} (Score: {best_candidate.get('predicted_relative_engagement'):.4f}, Filter: {best_candidate.get('filter_status')})")
    return best_candidate


# --- Main Execution Block (for running as a script) ---
def run_orchestrator_cli():
    parser = argparse.ArgumentParser(description="EEP: Generate & Select High-Engagement Social Media Posts")
    parser.add_argument("username", help="The X.com username for context.")
    parser.add_argument("--keyword", help="Optional keyword.", default=None)
    parser.add_argument("--image_path", help="Optional path to input image.", default=None)
    parser.add_argument("--theme", help="Content theme.", default="casual", # Default to casual
                        choices=["casual", "serious", "promotional", "inspirational", "memes"]) # Use defined themes
    # Removed num_captions from CLI args

    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Call main functions, passing theme
    all_candidates, context_results = generate_post_candidates(
        args.username, args.keyword, args.image_path, args.theme
    )
    best_post_suggestion = select_best_candidate(all_candidates)

    # Save detailed results
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"generation_run_{run_timestamp}.json"
    full_run_details = {
        "run_args": vars(args), # Include theme here now
        "context_results": context_results,
        "evaluated_candidates": all_candidates,
        "selected_suggestion": best_post_suggestion
    }
    try:
        with open(output_file, 'w') as f: json.dump(full_run_details, f, indent=2)
        logging.info(f"Saved full generation run details to {output_file}")
    except Exception as e: logging.error(f"Failed to save full run details: {e}")

    # Print final suggestion
    if best_post_suggestion:
        print("\n======= Best Post Suggestion =======")
        # Add theme to the printed output for clarity
        best_post_suggestion_display = best_post_suggestion.copy()
        best_post_suggestion_display["requested_theme"] = args.theme
        print(json.dumps(best_post_suggestion_display, indent=2))
        print("==================================")
    else:
        print("\n--- No suitable post suggestion could be generated or selected ---")


if __name__ == "__main__":
    run_orchestrator_cli()
