# EEP/UI/orchestrator/main_generator.py

import argparse
import logging
import requests
import json
import random
from datetime import datetime
from pathlib import Path
import time
import os
from typing import Optional, List, Dict, Any
import sys

# --- Configuration (Unchanged) ---
IEP_SERVICE_URLS = {
    "caption_generator": os.environ.get("CAPTION_GENERATOR_URL", "http://caption_generator:5001/generate/caption"),
    "computer_vision": os.environ.get("COMPUTER_VISION_URL", "http://computer_vision:5021/describe_image"),
    "engagement_prediction": os.environ.get("ENGAGEMENT_PREDICTOR_URL", "http://engagement_prediction:5010/predict"),
    "filter": os.environ.get("FILTER_URL", "http://filter:5022/filter"),
    "hashtag_generator": os.environ.get("HASHTAG_GENERATOR_URL", "http://hashtag_generator:5002/generate/hashtags"),
    "image_generator": os.environ.get("IMAGE_GENERATOR_URL", "http://image_generator:5003/generate/image"),
    "keyword_suggester": os.environ.get("KEYWORD_SUGGESTER_URL", "http://keyword_suggester:5004/generate/keywords"),
    "past_tweet_analyzer": os.environ.get("PAST_TWEET_ANALYZER_URL", "http://past_tweet_analyzer:5005/analyze/past-tweets"),
    "trend_analyzer": os.environ.get("TREND_ANALYZER_URL", "http://trend_analyzer:5006/analyze/trends"),
}
OUTPUT_DIR = Path("/app/output")
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
DEFAULT_USERNAME = "DefaultUser"
NUM_CAPTION_CANDIDATES = 3
REQUEST_TIMEOUT = 45

# --- Logging Setup (Unchanged) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

# --- REAL API Call Function (Unchanged) ---
def call_api(service_name: str, method: str = "POST", data: dict = None, files: dict = None) -> dict:
    # ... (previous implementation using requests) ...
    url = IEP_SERVICE_URLS.get(service_name)
    if not url:
        logging.error(f"Service URL for '{service_name}' not configured.")
        return {"error": f"Service '{service_name}' URL not configured."}

    log_data = data if data else {}
    log_files = list(files.keys()) if files else "None"
    logging.info(f"Calling {method} {service_name} at {url} with data keys: {list(log_data.keys())}, files: {log_files}")

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=data, files=files, timeout=REQUEST_TIMEOUT)
        elif method.upper() == "GET":
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        else:
            logging.error(f"Unsupported HTTP method '{method}' for {service_name}.")
            return {"error": f"Unsupported HTTP method: {method}"}

        response.raise_for_status()

        try:
            result = response.json()
            logging.info(f"Success response from {service_name}. Keys: {list(result.keys()) if isinstance(result, dict) else 'Non-dict response'}")
            return result
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON response from {service_name}. Status: {response.status_code}, Response text: {response.text[:200]}...")
            return {"error": "Invalid JSON response from service."}

    except requests.exceptions.ConnectionError:
        logging.error(f"Connection error calling {service_name} at {url}.")
        return {"error": f"Could not connect to service: {service_name}"}
    except requests.exceptions.Timeout:
        logging.error(f"Timeout error calling {service_name} at {url}.")
        return {"error": f"Request timed out for service: {service_name}"}
    except requests.exceptions.HTTPError as e:
        error_body = ""
        try: error_body = e.response.json()
        except json.JSONDecodeError: error_body = e.response.text[:200]
        logging.error(f"HTTP error calling {service_name}: {e.response.status_code} {e.response.reason}. Response: {error_body}")
        return {"error": f"Service {service_name} returned status {e.response.status_code}", "details": error_body}
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during API call to {service_name}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred calling {service_name}: {e}"}
    except Exception as e:
        logging.error(f"Unexpected error in call_api for {service_name}: {e}", exc_info=True)
        return {"error": f"Internal error calling {service_name}: {e}"}

# --- Helper: Predict Engagement for a Single Candidate Dict ---
def predict_engagement_for_candidate(candidate: dict) -> Optional[float]:
    """Calls engagement prediction for a single candidate dictionary. Modifies dict in place."""
    text_content = candidate.get("final_text")
    has_media_flag = candidate.get("has_media", False)
    candidate_id = candidate.get("candidate_id", "unknown") # For logging

    if not text_content:
        logging.warning(f"Skipping prediction for {candidate_id}: Missing final_text.")
        return None

    logging.info(f"      Attempting engagement prediction for {candidate_id}...")
    prediction_payload = {
        "text": text_content,
        "has_media": 1 if has_media_flag else 0,
        "hour_of_day": datetime.now().hour,
        "weekday": datetime.now().weekday()
    }
    engagement_result = call_api("engagement_prediction", data=prediction_payload)

    predicted_engagement = None # Default to None
    if "error" in engagement_result:
        logging.warning(f"      Engagement prediction failed for {candidate_id}. Details: {engagement_result['error']}")
    elif "predicted_relative_engagement" in engagement_result:
        predicted_engagement = engagement_result.get("predicted_relative_engagement")
        if predicted_engagement is not None:
            logging.info(f"      Predicted Engagement for {candidate_id}: {predicted_engagement:.4f}")
        else: # Handle case where key exists but value is null
             logging.warning(f"      Engagement prediction returned null score for {candidate_id}.")
    else:
         logging.warning(f"      Engagement prediction succeeded but key 'predicted_relative_engagement' missing for {candidate_id}.")

    # Modify the candidate dictionary directly
    candidate["predicted_relative_engagement"] = predicted_engagement
    return predicted_engagement


# --- Main Orchestration Function (Modified Candidate Evaluation) ---
def generate_post_candidates(username: str, keyword: Optional[str], image_path: Optional[str]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generates multiple post candidates and returns them scored and filtered.
    Handles failure of past_tweet_analyzer gracefully.
    If all candidates initially fail filter, forces first one to 'CAN BE CHANGED' and retries prediction.
    Returns: Tuple (list_of_candidates, dictionary_of_context_results)
    """
    # --- Start: Context Gathering & Image Handling (largely unchanged) ---
    logging.info(f"--- Starting Candidate Generation Workflow for user: '{username}' ---")
    if not username: username = DEFAULT_USERNAME; logging.warning(f"Using default username: {username}")

    all_generated_candidates = [] # Store ALL candidates initially
    intermediate_results = {}

    # Phase 1: Context Gathering
    logging.info("--- Phase 1: Context Gathering ---")
    user_profile_info = call_api("past_tweet_analyzer", data={"username": username})
    intermediate_results["user_profile_analysis"] = user_profile_info
    if "error" in user_profile_info:
        logging.warning(f"Past tweet analysis failed for '{username}', proceeding with defaults. Error: {user_profile_info['error']}")
        user_style_summary = "Style: generic. Tone: neutral. Emojis: unknown."
        user_topics = []; user_profile_info = {}
    else:
        logging.info(f"Past tweet analysis successful for '{username}'.")
        user_style_summary = f"Style: {user_profile_info.get('tweeting_style', 'unknown')}. Tone: {user_profile_info.get('tone', 'unknown')}. Emojis: {user_profile_info.get('emoji_usage', 'unknown')}."
        user_topics = user_profile_info.get("common_themes", [])

    trends_info = call_api("trend_analyzer", method="GET")
    intermediate_results["trend_analysis"] = trends_info
    if "error" in trends_info:
        logging.error(f"CRITICAL FAILURE: Could not analyze trends. Stopping generation. Error: {trends_info['error']}")
        return [], intermediate_results
    logging.info("Trend analysis successful.")
    relevant_trends_list = trends_info.get("tech_trends", []) + trends_info.get("top_hashtags", [])

    # Phase 2: Keyword Processing
    logging.info("--- Phase 2: Keyword Processing ---")
    topic_keyword = keyword
    if not topic_keyword:
        available_keywords = user_topics + trends_info.get("tech_trends", [])
        topic_keyword = random.choice(available_keywords) if available_keywords else "innovation"
        logging.info(f"Derived keyword: '{topic_keyword}'")
    intermediate_results["selected_keyword"] = topic_keyword

    # Phase 3: Image Handling
    logging.info("--- Phase 3: Image Handling ---")
    # ... (Existing image handling logic remains the same) ...
    # ... (It should set base_image_ref, base_image_description, base_has_media) ...
    # --- Assume variables are set correctly by the end of this phase ---
    base_image_ref = intermediate_results.get("base_image_reference")
    base_image_description = intermediate_results.get("base_image_description")
    base_has_media = intermediate_results.get("base_has_media_flag", False)
    # --- End of Phase 3 ----

    # --- Phase 4: Generate and Evaluate Candidates ---
    logging.info(f"--- Phase 4: Generating & Evaluating {NUM_CAPTION_CANDIDATES} Caption Candidates ---")
    for i in range(NUM_CAPTION_CANDIDATES):
        logging.info(f"--- Generating Candidate Set {i+1}/{NUM_CAPTION_CANDIDATES} ---")

        # 4a. Generate Caption (handle potential errors)
        # ... (existing caption generation logic) ...
        caption_tone = user_profile_info.get('tone', 'informative')
        caption_context_summary = f"Topic: {topic_keyword}."
        if base_has_media and base_image_description: caption_context_summary += f" Associated image content: {base_image_description}"
        caption_payload = { "context_summary": caption_context_summary, "user_profile_summary": user_style_summary,
                            "relevant_trends": relevant_trends_list, "tone_preference": caption_tone,
                            "max_length": 260 }
        caption_result = call_api("caption_generator", data=caption_payload)
        if "error" in caption_result or "caption" not in caption_result:
             logging.warning(f"Failed to generate caption for candidate set {i+1}. Skipping set.")
             continue # Skip this whole caption set if generation fails
        generated_caption = caption_result["caption"]
        logging.info(f"  Caption {i+1}: {generated_caption}")


        # 4b. Generate Hashtags (handle potential errors)
        # ... (existing hashtag generation logic) ...
        hashtag_payload = { "content_context": f"{topic_keyword} {generated_caption}", "user_topics": user_topics,
                            "trend_keywords": trends_info.get("top_hashtags", []), "desired_count": 5 }
        hashtag_result = call_api("hashtag_generator", data=hashtag_payload)
        generated_hashtags = hashtag_result.get("hashtags", [])
        if "error" in hashtag_result:
             logging.warning(f"Failed to generate hashtags for candidate set {i+1}. Using empty list.")
             generated_hashtags = []
        logging.info(f"  Hashtags {i+1}: {generated_hashtags}")


        # 4c/4d. Create Text/Media Variations
        # ... (existing variation logic) ...
        text_variations = {
            "with_hashtags": f"{generated_caption} {' '.join(h for h in generated_hashtags if h)}".strip(),
            "without_hashtags": generated_caption
        }
        media_variations = { "no_media": {"ref": None, "flag": False, "desc": None} }
        if base_has_media: media_variations["with_media"] = {"ref": base_image_ref, "flag": True, "desc": base_image_description}

        # 4e. Initial Evaluation (Filter ONLY)
        for text_label, text_content in text_variations.items():
            for media_label, media_info in media_variations.items():
                candidate_id = f"cand_{i+1}_{text_label}_{media_label}"
                logging.info(f"    Initial evaluation (Filter) {candidate_id}...")

                # Filter Call
                filter_payload = {"text": text_content}
                filter_result = call_api("filter", data=filter_payload)

                filter_status = "ERROR"; filter_reason = "N/A"
                if "error" in filter_result:
                     filter_reason = filter_result['error']
                     logging.warning(f"      Filter API call failed for {candidate_id}. Status: ERROR. Details: {filter_reason}")
                elif "result" in filter_result:
                     filter_status = filter_result["result"]
                     # Optionally derive reason
                else:
                     filter_reason = "Filter response format unexpected."
                     logging.warning(f"      Filter API call succeeded but key 'result' missing: {filter_result}")

                logging.info(f"      Filter Status: {filter_status} (Reason: {filter_reason})")

                # Store candidate with filter status, NO prediction yet
                all_generated_candidates.append({
                    "candidate_id": candidate_id, "username": username, "selected_keyword": topic_keyword,
                    "image_description": media_info["desc"], "generated_caption": generated_caption,
                    "generated_hashtags": generated_hashtags if text_label == "with_hashtags" else [],
                    "final_text": text_content, "image_reference": media_info["ref"], "has_media": media_info["flag"],
                    "filter_status": filter_status, "filter_reason": filter_reason,
                    "predicted_relative_engagement": None, # Initialize as None
                    "timestamp_generated": datetime.now().isoformat()
                })

    logging.info(f"--- Finished initial generation of {len(all_generated_candidates)} candidates ---")

    # --- Phase 5: Post-Generation Processing (Prediction & Fallback) ---

    # 5a. Check if ALL candidates failed the filter initially
    all_failed_filter = False
    if all_generated_candidates: # Only check if we actually generated candidates
        all_failed_filter = all(c.get("filter_status") in ["NOT OK", "ERROR"] for c in all_generated_candidates)

    # 5b. If all failed, force first candidate to "CAN BE CHANGED"
    if all_failed_filter:
        logging.warning("All initially generated candidates failed filter check (NOT OK or ERROR).")
        first_candidate = all_generated_candidates[0]
        logging.warning(f"Forcing status of first candidate '{first_candidate['candidate_id']}' to 'CAN BE CHANGED' for prediction attempt.")
        first_candidate['filter_status'] = "CAN BE CHANGED"
        first_candidate['filter_reason'] = "Forced status due to all others failing filter." # Add note

    # 5c. Predict engagement ONLY for candidates that passed filter (or the forced one)
    logging.info("--- Predicting engagement for eligible candidates ---")
    for candidate in all_generated_candidates:
        # Predict if status is OK or CAN BE CHANGED (includes the potentially forced one)
        if candidate.get("filter_status") in ["OK", "CAN BE CHANGED"]:
            predict_engagement_for_candidate(candidate) # Modifies candidate dict in place
        else:
            logging.info(f"      Skipping prediction for {candidate['candidate_id']} due to Filter Status: {candidate.get('filter_status')}")

    logging.info("--- Finished final evaluation ---")
    # Return the list of *all* candidates (now with predictions populated where applicable)
    # and the context results
    return all_generated_candidates, intermediate_results


# --- Post-Processing and Selection (Fallback Option 1 - Unchanged from previous) ---
def select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Selects the best candidate with fallback logic:
    1. Prefers candidates with OK/CAN BE CHANGED status and a score.
    2. Falls back to OK/CAN BE CHANGED candidates without a score.
    3. Falls back to the *first* generated candidate if none meet criteria 1 or 2.
    """
    # ... (Implementation of Fallback Option 1 remains the same as previous answer) ...
    if not candidates:
        logging.warning("No candidates were generated.")
        return None

    # 1. Try ideal candidates: Scored and filter status OK or CAN BE CHANGED
    ideal_candidates = sorted(
        [c for c in candidates if c.get("filter_status") in ["OK", "CAN BE CHANGED"] and c.get("predicted_relative_engagement") is not None],
        key=lambda x: x["predicted_relative_engagement"],
        reverse=True
    )
    if ideal_candidates:
        best_candidate = ideal_candidates[0]
        logging.info(f"Selected best candidate (Ideal): {best_candidate.get('candidate_id')} (Score: {best_candidate.get('predicted_relative_engagement'):.4f}, Filter: {best_candidate.get('filter_status')})")
        return best_candidate

    logging.warning("No ideal candidates found (scored and OK/Changeable filter status). Looking for fallbacks...")

    # 2. Fallback: Unscored but filter status OK or CAN BE CHANGED
    fallback_candidates_ok = sorted(
        [c for c in candidates if c.get("filter_status") == "OK" and c.get("predicted_relative_engagement") is None],
        key=lambda x: len(x.get("final_text", "")), # Example sort: by length
        reverse=True
    )
    if fallback_candidates_ok:
        best_candidate = fallback_candidates_ok[0]
        logging.warning(f"Selected fallback candidate (Filter OK, No Score): {best_candidate.get('candidate_id')} (Filter: {best_candidate.get('filter_status')})")
        return best_candidate

    fallback_candidates_changeable = sorted(
        [c for c in candidates if c.get("filter_status") == "CAN BE CHANGED" and c.get("predicted_relative_engagement") is None],
        key=lambda x: len(x.get("final_text", "")), # Example sort
        reverse=True
    )
    if fallback_candidates_changeable:
        best_candidate = fallback_candidates_changeable[0]
        # Check if this was the one we forced earlier
        if best_candidate.get("filter_reason") == "Forced status due to all others failing filter.":
             logging.warning(f"Selected fallback candidate (Forced Status, No Score): {best_candidate.get('candidate_id')} (Filter: {best_candidate.get('filter_status')})")
             best_candidate['status_note'] = "Returned via filter override fallback - review carefully."
        else:
             logging.warning(f"Selected fallback candidate (Filter Changeable, No Score): {best_candidate.get('candidate_id')} (Filter: {best_candidate.get('filter_status')})")

        return best_candidate

    logging.warning("No candidates with OK/Changeable filter status found, even unscored ones.")

    # 3. Last Resort Fallback: Return the very first candidate generated
    if candidates:
         first_candidate = candidates[0]
         logging.error(f"CRITICAL FALLBACK: Returning first generated candidate ({first_candidate.get('candidate_id')}) due to lack of better options. STATUS WAS: {first_candidate.get('filter_status')}, SCORE: {first_candidate.get('predicted_relative_engagement')}")
         first_candidate['status_note'] = "Returned as last resort fallback - review carefully."
         return first_candidate

    logging.error("Could not select any candidate, even as a last resort.")
    return None

# --- NO if __name__ == "__main__": block needed here ---