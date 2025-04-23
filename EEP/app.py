# orchestrator/main_generator.py (Multi-Candidate Version)

import argparse
import logging
import requests
import json
import random
from datetime import datetime
from pathlib import Path
import time
import os
from typing import Optional, List, Dict, Any # Added more typing

# --- Configuration (Same as before) ---
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
OUTPUT_DIR = Path("../generated_content")
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
DEFAULT_USERNAME = "DefaultUser"
NUM_CAPTION_CANDIDATES = 3 # How many captions to generate

# --- Logging Setup (Same as before) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

# --- API Call Simulation (Same simulation logic as before) ---
def call_api(service_name: str, method: str = "POST", data: dict = None, files: dict = None) -> dict:
    """Simulates calling an IEP API endpoint, respecting READMEs."""
    url = IEP_SERVICE_URLS.get(service_name)
    if not url:
        logging.error(f"Service URL for '{service_name}' not configured.")
        return {"error": f"Service '{service_name}' URL not configured."}

    log_data = data if data else {}
    logging.info(f"Simulating {method} call to {service_name} at {url} with data keys: {list(log_data.keys())}")

    try:
        time.sleep(random.uniform(0.1, 0.3)) # Simulate network latency

        # --- Mock Responses (Same as previous version) ---
        if service_name == "trend_analyzer":
             return {"global_trends": ["global event", "market news"], "tech_trends": ["AI release", "cloud update"], "cultural_trends": ["new movie", "music awards"], "top_hashtags": ["#News", "#AI", "#WebDev"]}
        elif service_name == "past_tweet_analyzer":
             user = data.get("username", DEFAULT_USERNAME); themes = ["AI updates", f"{user} product news"] if user != DEFAULT_USERNAME else ["general business", "tech trends"]
             return {"common_themes": themes, "tweeting_style": "informative, questions", "tone": "professional", "typical_hashtags": ["#AI", "#Tech", f"#{user}Update"], "emoji_usage": "moderate"}
        elif service_name == "keyword_suggester":
             original_kws = data.get("keywords", ["generic"]); return {"improved_keywords": original_kws + ["enhanced" + kw for kw in original_kws] + ["buzzword"]}
        elif service_name == "computer_vision":
             return {"description": f"Mock description: Graphic about {random.choice(['data', 'code', 'future'])}."}
        elif service_name == "image_generator":
             prompt = data.get("prompt", "default image"); ts = int(time.time()*1000); dummy_filename = f"generated_img_{ts}.png"; img_path = IMAGE_OUTPUT_DIR / dummy_filename; img_path.touch(); simulated_url = f"https://simulatedstorage.blob.core.windows.net/images/{dummy_filename}"; logging.info(f"Simulated image generation, file: {img_path}, URL: {simulated_url}"); return {"image_url": simulated_url, "prompt_used": prompt}
        elif service_name == "caption_generator":
            # Simulate variation by adding random number
            context = data.get('context_summary', 'our latest news'); style = data.get('user_profile_summary', 'standard'); rand_num = random.randint(1, 100)
            return {"caption": f"Caption #{rand_num}: Discover {context}! Aligned with {style}. #Generated"}
        elif service_name == "hashtag_generator":
            context = data.get("content_context", ""); kw = context.split()[1] if len(context.split()) > 1 else "topic"; count = data.get("desired_count", 4)
            # Simulate variation
            return {"hashtags": [f"#{kw}{random.randint(1,5)}"] + [f"#related{i+random.randint(1,10)}" for i in range(count - 1)]}
        elif service_name == "filter":
             text = data.get('text', '').lower()
             if any(word in text for word in ["badword", "controversial"]): return {"status": "NOT OK", "reason": "Problematic term."}
             if any(word in text for word in ["maybe", "review", "dumb"]): return {"status": "CAN BE CHANGED", "reason": "Suggest rephrasing."}
             return {"status": "OK"}
        elif service_name == "engagement_prediction":
             base = 0.7 + random.uniform(-0.2, 0.2); media_boost = 0.3 if data.get('has_media') == 1 else 0; length_boost = min(0.5, len(data.get('text','')) / 400.0)
             return {"predicted_relative_engagement": round(base + media_boost + length_boost, 4)}
        else:
            logging.error(f"No mock response defined for service: {service_name}")
            return {"error": f"Mock response for '{service_name}' not implemented."}

    except Exception as e:
        logging.error(f"Error during API call simulation for {service_name}: {e}", exc_info=True)
        return {"error": f"Simulation error: {e}"}


# --- Main Orchestration Function ---
def generate_post_candidates(username: str, keyword: Optional[str], image_path: Optional[str]) -> List[Dict[str, Any]]:
    """Generates multiple post candidates and returns them scored and filtered."""
    logging.info(f"--- Starting Candidate Generation Workflow for user: '{username}' ---")
    if not username: username = DEFAULT_USERNAME; logging.warning(f"Using default username: {username}")

    candidates = []
    intermediate_results = {} # Store results of context steps

    # --- Phase 1: Context Gathering (Run once) ---
    logging.info("--- Phase 1: Context Gathering ---")
    user_profile_info = call_api("past_tweet_analyzer", data={"username": username})
    intermediate_results["user_profile_analysis"] = user_profile_info.get('error', user_profile_info)
    trends_info = call_api("trend_analyzer", method="GET")
    intermediate_results["trend_analysis"] = trends_info.get('error', trends_info)
    user_style_summary = f"Style: {user_profile_info.get('tweeting_style', 'unknown')}. Tone: {user_profile_info.get('tone', 'unknown')}. Emojis: {user_profile_info.get('emoji_usage', 'unknown')}."
    user_topics = user_profile_info.get("common_themes", [])
    relevant_trends_list = trends_info.get("tech_trends", []) + trends_info.get("top_hashtags", [])

    # --- Phase 2: Keyword Processing (Run once) ---
    logging.info("--- Phase 2: Keyword Processing ---")
    topic_keyword = keyword
    if not topic_keyword:
        available_keywords = user_topics + trends_info.get("tech_trends", [])
        topic_keyword = random.choice(available_keywords) if available_keywords else "innovation"
        logging.info(f"Derived keyword: '{topic_keyword}'")
    intermediate_results["selected_keyword"] = topic_keyword

    # --- Phase 3: Image Handling (Determine base image, run once) ---
    logging.info("--- Phase 3: Image Handling ---")
    base_image_ref = None # This will be URL or Path
    base_image_description = None
    base_has_media = False
    if image_path:
        logging.info(f"Processing provided image: {image_path}")
        if Path(image_path).is_file():
            cv_result = call_api("computer_vision", data={}, files={"image_placeholder": True})
            intermediate_results["computer_vision_result"] = cv_result.get('error', cv_result)
            if "description" in cv_result: base_image_description = cv_result["description"]; logging.info(f"Image description: {base_image_description}")
            base_image_ref = image_path # Use the original path
            base_has_media = True
        else: logging.error(f"Input image file not found: {image_path}")
    else:
        logging.info("No input image provided. Generating base image...")
        img_prompt = f"Visually interesting abstract graphic representing '{topic_keyword}', {user_profile_info.get('tone', 'professional')} tone, social media."
        img_gen_result = call_api("image_generator", data={"prompt": img_prompt, "aspect_ratio": "16:9"})
        intermediate_results["image_generation_result"] = img_gen_result.get('error', img_gen_result)
        if "image_url" in img_gen_result:
            base_image_ref = img_gen_result["image_url"]; base_has_media = True
            logging.info(f"Generated base image URL: {base_image_ref}")
        else: logging.warning("Base image generation failed.")
    intermediate_results["base_image_reference"] = base_image_ref
    intermediate_results["base_has_media_flag"] = base_has_media

    # --- Phase 4: Generate and Evaluate Candidates ---
    logging.info(f"--- Phase 4: Generating & Evaluating {NUM_CAPTION_CANDIDATES} Caption Candidates ---")
    for i in range(NUM_CAPTION_CANDIDATES):
        logging.info(f"--- Generating Candidate Set {i+1}/{NUM_CAPTION_CANDIDATES} ---")

        # 4a. Generate Caption
        caption_context_summary = f"Topic: {topic_keyword}."
        if base_has_media and base_image_description: caption_context_summary += f" Associated image: {base_image_description}"
        caption_payload = { "context_summary": caption_context_summary, "user_profile_summary": user_style_summary,
                            "relevant_trends": relevant_trends_list, "tone_preference": user_profile_info.get('tone', 'informative'),
                            "max_length": 260 }
        caption_result = call_api("caption_generator", data=caption_payload)
        if "caption" not in caption_result:
            logging.warning(f"Failed to generate caption for candidate {i+1}. Skipping. Error: {caption_result.get('error')}")
            continue
        generated_caption = caption_result["caption"]
        logging.info(f"  Caption {i+1}: {generated_caption}")

        # 4b. Generate Hashtags
        hashtag_payload = { "content_context": f"{topic_keyword} {generated_caption}", "user_topics": user_topics,
                            "trend_keywords": trends_info.get("top_hashtags", []), "desired_count": 5 }
        hashtag_result = call_api("hashtag_generator", data=hashtag_payload)
        generated_hashtags = hashtag_result.get("hashtags", [])
        logging.info(f"  Hashtags {i+1}: {generated_hashtags}")

        # 4c. Create Text Variations (With/Without Hashtags)
        text_variations = {
            "with_hashtags": f"{generated_caption} {' '.join(h for h in generated_hashtags if h)}",
            "without_hashtags": generated_caption
        }

        # 4d. Create Media Variations (With/Without Image - if base image exists)
        media_variations = {
            "no_media": {"ref": None, "flag": False},
        }
        if base_has_media:
            media_variations["with_media"] = {"ref": base_image_ref, "flag": True}

        # 4e. Evaluate each combination
        for text_label, text_content in text_variations.items():
            for media_label, media_info in media_variations.items():
                candidate_id = f"cand_{i+1}_{text_label}_{media_label}"
                logging.info(f"    Evaluating {candidate_id}...")

                # Filter
                filter_payload = {"text": text_content}
                filter_result = call_api("filter", data=filter_payload)
                filter_status = filter_result.get("status", "ERROR")
                filter_reason = filter_result.get('reason', 'N/A')
                logging.info(f"      Filter Status: {filter_status} (Reason: {filter_reason})")

                predicted_engagement = None
                if filter_status != "NOT OK":
                    # Predict Engagement
                    prediction_payload = { "text": text_content, "has_media": 1 if media_info["flag"] else 0,
                                           "hour_of_day": datetime.now().hour, "weekday": datetime.now().weekday() }
                    engagement_result = call_api("engagement_prediction", data=prediction_payload)
                    predicted_engagement = engagement_result.get("predicted_relative_engagement")
                    if predicted_engagement is not None:
                        logging.info(f"      Predicted Engagement: {predicted_engagement:.4f}")
                    else:
                        logging.warning(f"      Engagement prediction failed: {engagement_result.get('error')}")
                else:
                    logging.warning("      Skipping engagement prediction due to NOT OK filter status.")


                # Store candidate details
                candidates.append({
                    "candidate_id": candidate_id,
                    "username": username,
                    "selected_keyword": topic_keyword,
                    "image_description": base_image_description if media_info["flag"] else None,
                    "generated_caption": generated_caption,
                    "generated_hashtags": generated_hashtags if text_label == "with_hashtags" else [],
                    "final_text": text_content,
                    "image_reference": media_info["ref"],
                    "has_media": media_info["flag"],
                    "filter_status": filter_status,
                    "filter_reason": filter_reason,
                    "predicted_relative_engagement": predicted_engagement, # Can be None
                    "timestamp_generated": datetime.now().isoformat()
                })

    logging.info(f"--- Finished evaluating {len(candidates)} candidates ---")
    return candidates, intermediate_results # Return all candidates and context

# --- Post-Processing and Selection ---
def select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Selects the best candidate based on filter status and predicted engagement."""
    if not candidates:
        logging.warning("No candidates were generated.")
        return None

    # Filter for valid candidates (OK or CAN BE CHANGED, and have a prediction score)
    valid_candidates = [
        c for c in candidates
        if c.get("filter_status") in ["OK", "CAN BE CHANGED"] and c.get("predicted_relative_engagement") is not None
    ]

    if not valid_candidates:
        logging.warning("No candidates passed filter or received an engagement score.")
        # Optionally return the 'best' of the failed ones for review?
        # For now, return None if no valid options.
        return None

    # Sort by predicted engagement (descending)
    valid_candidates.sort(key=lambda x: x["predicted_relative_engagement"], reverse=True)

    best_candidate = valid_candidates[0]
    logging.info(f"Selected best candidate: {best_candidate.get('candidate_id')} (Score: {best_candidate.get('predicted_relative_engagement'):.4f}, Filter: {best_candidate.get('filter_status')})")

    return best_candidate


# --- Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EEP: Generate & Select High-Engagement Social Media Posts")
    parser.add_argument("username", help="The X.com username for context.")
    parser.add_argument("--keyword", help="Optional keyword to guide generation.", default=None)
    parser.add_argument("--image_path", help="Optional path to an input image.", default=None)
    parser.add_argument("--num_captions", type=int, default=NUM_CAPTION_CANDIDATES, help="Number of caption candidates to generate.")

    args = parser.parse_args()

    # Update global var if needed
    NUM_CAPTION_CANDIDATES = args.num_captions

    # Ensure output dirs exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate candidates
    all_candidates, context_results = generate_post_candidates(args.username, args.keyword, args.image_path)

    # Select the best one
    best_post_suggestion = select_best_candidate(all_candidates)

    # --- Save detailed results ---
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"generation_run_{run_timestamp}.json"
    full_run_details = {
        "run_args": vars(args),
        "context_results": context_results,
        "evaluated_candidates": all_candidates,
        "selected_suggestion": best_post_suggestion
    }
    try:
        with open(output_file, 'w') as f:
            json.dump(full_run_details, f, indent=2)
        logging.info(f"Saved full generation run details to {output_file}")
    except Exception as e:
        logging.error(f"Failed to save full run details: {e}")


    # --- Print final suggestion ---
    if best_post_suggestion:
        print("\n======= Best Post Suggestion =======")
        print(json.dumps(best_post_suggestion, indent=2))
        print("==================================")
    else:
        print("\n--- No suitable post suggestion could be generated or selected ---")
        # Check logs and the saved JSON file for details on candidates
