import os
import logging
import re
from datetime import datetime, timedelta
from collections import Counter

from flask import Flask, jsonify
from pytrends.request import TrendReq
from newsapi import NewsApiClient
from cachelib import SimpleCache
from dotenv import load_dotenv
import regex

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# API Keys & Credentials
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# --- Caching Setup ---
cache = SimpleCache(default_timeout=3600) # 1 hour cache
CACHE_KEY = "trends_data_no_prompts" # Use a new key

# --- API Client Initialization ---
newsapi = None
if NEWS_API_KEY:
    try:
        newsapi = NewsApiClient(api_key=NEWS_API_KEY)
        logging.info("NewsAPI client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize NewsAPI client: {e}", exc_info=True)
else:
    logging.warning("NewsAPI Key not found. News trends will be unavailable.")

# --- Helper Functions ---

def clean_trend(text: str) -> str | None:
    """Basic cleaning for trend titles/keywords."""
    if not text: return None
    text = text.strip()
    text = re.sub(r"^\d+\.\s+", "", text)
    text = re.sub(r'\s+-\s+[\w\s]+$', '', text)
    if len(text) < 5 or len(text.split()) < 2:
        return None
    return text

def format_hashtag(term: str) -> str | None:
    """Cleans and formats a potential trend term into a hashtag."""
    if not term: return None
    words = term.split()[:3]
    term = "".join(word.capitalize() for word in words)
    # Allow letters and numbers only for hashtag part
    term = re.sub(r'[^\w\d]+', '', term) # Changed from \w to \w\d
    return f"#{term}" if term else None

def fetch_google_trends(max_items=7) -> list[str]:
    """Fetches trending searches from Google Trends using pytrends."""
    trends = []
    logging.info("Fetching Google Trends...")
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        # Attempt to get daily trending searches
        trending_searches_df = pytrends.trending_searches(pn='united_states') # Or 'daily_trending_searches' if available/desired
        if not trending_searches_df.empty:
            trends = [clean_trend(t) for t in trending_searches_df[0].tolist()[:max_items] if clean_trend(t)]
        logging.info(f"Fetched {len(trends)} trends from Google Trends.")
    except Exception as e:
        logging.error(f"Failed to fetch Google Trends: {e}", exc_info=True)
    return trends

def fetch_newsapi_trends(category=None, max_items=10) -> list[str]:
    """Fetches top headlines from NewsAPI."""
    if not newsapi: return []
    trends = []
    log_category = category if category else 'global'
    logging.info(f"Fetching NewsAPI headlines ({log_category})...")
    try:
        if category:
             top_headlines = newsapi.get_top_headlines(category=category, language='en', page_size=max_items*2)
        else:
             top_headlines = newsapi.get_top_headlines(language='en', page_size=max_items*2)

        if top_headlines.get('status') == 'ok':
            articles = top_headlines.get('articles', [])
            # Prioritize non-null descriptions or titles
            potential_trends = []
            for a in articles:
                cleaned = clean_trend(a['title']) # Clean title first
                # Optional: could use description too if title is poor
                # desc_cleaned = clean_trend(a.get('description'))
                # if cleaned: potential_trends.append(cleaned)
                # elif desc_cleaned: potential_trends.append(desc_cleaned)
                if cleaned: potential_trends.append(cleaned)

            trends = list(dict.fromkeys(potential_trends))[:max_items] # Deduplicate
        logging.info(f"Fetched {len(trends)} unique trends from NewsAPI ({log_category}).")
    except Exception as e:
        logging.error(f"Failed to fetch NewsAPI trends ({log_category}): {e}", exc_info=True)
    return trends

# --- Main Fetching & Processing Logic ---
def get_trends_data() -> dict:
    """Fetches, processes, and categorizes trends from Google Trends and NewsAPI."""
    MAX_PER_CATEGORY = 5
    HASHTAG_LIMIT = 7

    # Fetch data
    gt = fetch_google_trends(max_items=MAX_PER_CATEGORY + 2)
    ng = fetch_newsapi_trends(category=None, max_items=MAX_PER_CATEGORY * 2)
    nt = fetch_newsapi_trends(category='technology', max_items=MAX_PER_CATEGORY + 2)
    nc = fetch_newsapi_trends(category='entertainment', max_items=MAX_PER_CATEGORY + 2)

    # Combine and Categorize
    global_set = set(gt + ng)
    tech_set = set(nt) - global_set
    cultural_set = set(nc) - global_set - tech_set

    final_trends = {
        "global_trends": list(global_set)[:MAX_PER_CATEGORY],
        "tech_trends": list(tech_set)[:MAX_PER_CATEGORY],
        "cultural_trends": list(cultural_set)[:MAX_PER_CATEGORY],
    }

    # Generate Hashtags from combined top trends
    all_combined_trends = final_trends["global_trends"] + final_trends["tech_trends"] + final_trends["cultural_trends"]
    # Filter out None values before formatting hashtags
    valid_trends = [t for t in all_combined_trends if t]
    hashtags_set = set()
    for trend in valid_trends:
        ht = format_hashtag(trend)
        if ht:
            hashtags_set.add(ht)
    final_trends["top_hashtags"] = list(hashtags_set)[:HASHTAG_LIMIT]

    logging.info("Trend analysis and aggregation complete (no prompts).")
    return final_trends


# --- API Endpoint ---
@app.route('/analyze/trends', methods=['GET'])
def get_trends_endpoint():
    """Endpoint to get cached or freshly fetched trends (no prompts)."""
    cached_data = cache.get(CACHE_KEY)
    if cached_data:
        logging.info("Returning cached trends data.")
        return jsonify(cached_data), 200

    logging.info("Cache miss or expired. Fetching fresh trends data...")
    try:
        if not newsapi:
             return jsonify({"error": "NewsAPI service is not configured or unavailable."}), 503

        trends_data = get_trends_data()
        # Check if any *trend* lists are non-empty
        if not (trends_data.get("global_trends") or trends_data.get("tech_trends") or trends_data.get("cultural_trends")):
             logging.error("Failed to fetch sufficient data from trend sources.")
             return jsonify({"error": "Failed to retrieve significant trends from external sources."}), 500

        cache.set(CACHE_KEY, trends_data)
        return jsonify(trends_data), 200
    except Exception as e:
        logging.error(f"Error in get_trends_endpoint: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred while analyzing trends."}), 500

# --- Run the App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006, debug=False)
