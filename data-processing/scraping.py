# scraper.py (Corrected Version: 1 Snapshot/Day, UnboundLocalError Fix)
%%writefile scraper.py

import waybackpy
from waybackpy.exceptions import NoCDXRecordFound, WaybackError
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime, timezone, date # Ensure 'date' is imported
import logging
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import sys # For flushing output, important in Colab/notebooks
from typing import List, Dict, Optional, Set, Tuple


# --- Configuration ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 45  # Increased timeout
SLEEP_BETWEEN_SNAPSHOTS = 4 # Respectful delay between snapshot processing
SLEEP_BETWEEN_HANDLES = 8     # Slightly longer pause between different handles

# --- CSS Selectors (!!! CRITICAL: VERIFY AND UPDATE THESE MANUALLY !!!) ---
# Inspect recent archived pages on web.archive.org for the correct selectors.
TWEET_CONTAINER_SELECTOR = 'article[data-testid="tweet"]'
TEXT_SELECTOR = '[data-testid="tweetText"]'
TIMESTAMP_SELECTOR = 'time[datetime]'
REPLY_COUNT_SELECTOR = '[data-testid="reply"] span span span'       # Highly speculative
RETWEET_COUNT_SELECTOR = '[data-testid="retweet"] span span span'   # Highly speculative
LIKE_COUNT_SELECTOR = '[data-testid="like"] span span span'         # Highly speculative
MEDIA_SELECTOR = '[data-testid="tweetPhoto"], [data-testid="videoPlayer"]' # Check for images or videos
STATUS_LINK_SELECTOR = 'a[href*="/status/"]' # Used for tweet_id extraction

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Console handler for real-time feedback (especially in Colab)
log_console_handler = logging.StreamHandler(sys.stdout)
log_console_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Clear existing handlers from previous runs in interactive sessions
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(log_console_handler)
logger.propagate = False # Prevent duplicate logs if root logger is configured

# --- Helper Functions ---

def parse_engagement_number(text: Optional[str]) -> int:
    """Converts engagement strings like '1.2K', '5M', '100' into integers."""
    if not text: return 0
    text = text.strip().upper().replace(',', '')
    if not text: return 0
    try:
        if 'K' in text: return int(float(text.replace('K', '').strip()) * 1000)
        elif 'M' in text: return int(float(text.replace('M', '').strip()) * 1000000)
        elif text.isdigit(): return int(text)
        else:
            cleaned_text = re.sub(r'[^\d.]', '', text)
            if '.' in cleaned_text: return int(float(cleaned_text))
            elif cleaned_text: return int(cleaned_text)
            else: return 0
    except ValueError:
        logger.debug(f"Could not parse engagement number: '{text}'")
        return 0

def hash_tweet_content(text: str, timestamp_str: str) -> str:
    """Generates an MD5 hash for basic content deduplication."""
    return hashlib.md5(f"{text}-{timestamp_str}".encode('utf-8')).hexdigest()

def extract_tweet_id_from_url(url: Optional[str]) -> Optional[str]:
    """Extracts potential tweet ID from a status URL."""
    if not url or '/status/' not in url: return None
    try:
        tweet_id_part = url.split('/status/')[-1]
        tweet_id = tweet_id_part.split('?')[0].split('/')[0]
        if tweet_id.isdigit(): return tweet_id
        else:
            logger.debug(f"Extracted non-numeric potential tweet ID '{tweet_id}' from URL '{url}'")
            return None
    except Exception as e:
        logger.debug(f"Error extracting tweet ID from URL '{url}': {e}")
        return None

def parse_tweet_element(tweet_elem: BeautifulSoup, handle: str, snapshot_url: str) -> Optional[Dict]:
    """Parses a single tweet HTML element found within a snapshot."""
    tweet_data = {'author_id': handle, 'snapshot_url': snapshot_url}
    try:
        # Core info: Text and Timestamp
        text_elem = tweet_elem.select_one(TEXT_SELECTOR)
        tweet_data['text'] = text_elem.get_text(separator=' ', strip=True) if text_elem else None
        time_elem = tweet_elem.select_one(TIMESTAMP_SELECTOR)
        tweet_data['timestamp_str'] = time_elem['datetime'] if time_elem and time_elem.has_attr('datetime') else None

        # Skip if essential info is missing
        if not tweet_data.get('text') or not tweet_data.get('timestamp_str'):
            logger.debug(f"Skipping tweet element in {snapshot_url}: Missing text or timestamp.")
            return None

        # Engagement Metrics
        reply_elem = tweet_elem.select_one(REPLY_COUNT_SELECTOR)
        retweet_elem = tweet_elem.select_one(RETWEET_COUNT_SELECTOR)
        like_elem = tweet_elem.select_one(LIKE_COUNT_SELECTOR)
        tweet_data['replies'] = parse_engagement_number(reply_elem.get_text(strip=True)) if reply_elem else 0
        tweet_data['retweets'] = parse_engagement_number(retweet_elem.get_text(strip=True)) if retweet_elem else 0
        tweet_data['likes'] = parse_engagement_number(like_elem.get_text(strip=True)) if like_elem else 0

        # Media Presence
        img_elem = tweet_elem.select_one(MEDIA_SELECTOR)
        tweet_data['has_media'] = 1 if img_elem else 0

        # Tweet ID (Best identifier if available)
        status_link_elem = tweet_elem.select_one(STATUS_LINK_SELECTOR)
        tweet_data['tweet_id'] = extract_tweet_id_from_url(status_link_elem['href']) if status_link_elem and status_link_elem.has_attr('href') else None

        # Metadata
        tweet_data['scraped_at'] = datetime.now(timezone.utc).isoformat()
        return tweet_data

    except Exception as e:
        logger.error(f"    Error parsing individual tweet element in {snapshot_url}: {e}", exc_info=False)
        return None

# --- Main Scraping Logic ---

def scrape_profile(handle: str, start_timestamp: str, end_timestamp: str, session: requests.Session) -> List[Dict]:
    """
    Scrapes available snapshots for a given Twitter handle within a date range,
    processing AT MOST ONE snapshot per calendar week (ISO standard: Monday-Sunday).

    Args:
        handle: The Twitter handle (without '@') being scraped.
        start_timestamp: Start date string (YYYYMMDDHHMMSS).
        end_timestamp: End date string (YYYYMMDDHHMMSS).
        session: A requests.Session object.

    Returns:
        A list of dictionaries, each representing a unique tweet found.
    """
    logger.info(f"Starting scrape for @{handle} from {start_timestamp} to {end_timestamp} (max 1 snapshot/week)")
    target_url = f"https://twitter.com/{handle}"
    all_tweets_data = []
    seen_tweet_ids: Set[str] = set()
    seen_content_hashes: Set[str] = set()

    processed_snapshots = 0
    # --- Change: Track processed weeks using (year, week_number) tuples ---
    processed_weeks_for_handle: Set[Tuple[int, int]] = set()

    try:
        cdx = waybackpy.WaybackMachineCDXServerAPI(target_url, USER_AGENT,
                                                  start_timestamp=start_timestamp,
                                                  end_timestamp=end_timestamp)
        logger.info(f"Fetching snapshot list for @{handle}...")
        snapshot_generator = cdx.snapshots()

        for snapshot in snapshot_generator:
            snapshot_url = snapshot.archive_url
            iso_week_tuple: Optional[Tuple[int, int]] = None # Initialize

            # --- Weekly Snapshot Limit Check ---
            try:
                # 1. Robustly get datetime object
                snapshot_datetime = getattr(snapshot, 'timestamp', None)
                if not isinstance(snapshot_datetime, datetime):
                    if isinstance(snapshot_datetime, str) and len(snapshot_datetime) == 14 and snapshot_datetime.isdigit():
                        try:
                            snapshot_datetime = datetime.strptime(snapshot_datetime, "%Y%m%d%H%M%S")
                            logger.debug(f"  Parsed timestamp string '{snapshot.timestamp}' to datetime for {snapshot_url}")
                        except ValueError:
                            logger.warning(f"  Could not parse timestamp string '{snapshot.timestamp}' for snapshot {snapshot_url}. Skipping.")
                            continue
                    else:
                        logger.warning(f"  Invalid or missing timestamp object for snapshot {snapshot_url} (Value: {snapshot.timestamp}, Type: {type(snapshot.timestamp)}). Skipping.")
                        continue

                # 2. Get the ISO week tuple (year, week_number)
                iso_calendar = snapshot_datetime.isocalendar()
                iso_week_tuple = (iso_calendar[0], iso_calendar[1]) # Extract year and week number

                # 3. Check if this week has already been processed
                if iso_week_tuple in processed_weeks_for_handle:
                    logger.debug(f"  Skipping snapshot {snapshot_url} (Timestamp: {snapshot.timestamp}): Week {iso_week_tuple} already processed.")
                    continue # Move to the next snapshot

                # 4. If it's a new week, record it and proceed
                processed_weeks_for_handle.add(iso_week_tuple)
                logger.info(f"  Processing snapshot: {snapshot_url} (Timestamp: {snapshot.timestamp}, Week: {iso_week_tuple})") # Log week tuple
                processed_snapshots += 1

            except Exception as e:
                 logger.error(f"  Unexpected error during week handling for snapshot {snapshot_url}: {e}. Skipping.", exc_info=False) # exc_info=True for full trace
                 continue
            # --- End Weekly Snapshot Limit Check ---

            # --- Process the chosen snapshot (only runs if week check passed) ---
            try:
                response = session.get(snapshot_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    logger.warning(f"    Skipping non-HTML snapshot: {snapshot_url} (Content-Type: {content_type})")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                tweet_containers = soup.select(TWEET_CONTAINER_SELECTOR)

                if not tweet_containers:
                    logger.warning(f"    No tweets found using selector '{TWEET_CONTAINER_SELECTOR}' on {snapshot_url}")
                else:
                    logger.info(f"    Found {len(tweet_containers)} potential tweet elements.")

                found_in_snapshot = 0
                for tweet_elem in tweet_containers:
                    # Call parsing function (passing the handle of the profile being scraped)
                    tweet_data = parse_tweet_element(tweet_elem, handle, snapshot_url)

                    if tweet_data:
                        # --- Deduplication (remains the same) ---
                        is_duplicate = False
                        tweet_id = tweet_data.get('tweet_id')
                        text_for_hash = tweet_data.get('text', '')
                        timestamp_for_hash = tweet_data.get('timestamp_str', '')
                        content_hash = hash_tweet_content(text_for_hash, timestamp_for_hash)
                        if tweet_id and tweet_id.isdigit():
                            if tweet_id in seen_tweet_ids: is_duplicate = True
                            else: seen_tweet_ids.add(tweet_id)
                        else:
                            if content_hash in seen_content_hashes: is_duplicate = True
                            else:
                                seen_content_hashes.add(content_hash)
                                if tweet_id is not None:
                                     logger.debug(f"Using content hash for deduplication due to invalid tweet ID '{tweet_id}' for author {tweet_data.get('author_id')}")
                                elif not tweet_id:
                                     logger.debug(f"Using content hash for deduplication due to missing tweet ID for author {tweet_data.get('author_id')}")
                        if not is_duplicate:
                            all_tweets_data.append(tweet_data)
                            found_in_snapshot += 1
                        # --- End Deduplication ---

                logger.info(f"    Added {found_in_snapshot} new unique tweets from this snapshot.")
                sys.stdout.flush()
                time.sleep(SLEEP_BETWEEN_SNAPSHOTS) # Pause after successful processing

            # --- Error Handling for Snapshot Processing ---
            except requests.exceptions.Timeout:
                 logger.error(f"    Timeout fetching snapshot: {snapshot_url}")
                 time.sleep(SLEEP_BETWEEN_SNAPSHOTS * 2)
            except requests.exceptions.RequestException as e:
                logger.error(f"    HTTP error fetching snapshot {snapshot_url}: {e}")
            except Exception as e:
                logger.error(f"    Error processing snapshot {snapshot_url}: {e}", exc_info=False)
            sys.stdout.flush()

    # ... (rest of the exception handling and logging for the handle remains the same) ...
    except NoCDXRecordFound:
        logger.warning(f"No snapshots found for @{handle} in the specified range via CDX API.")
    except WaybackError as e:
         logger.error(f"Wayback Machine API error for @{handle}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during scraping for @{handle}: {e}", exc_info=True)

    logger.info(f"Finished scraping @{handle}. Found {len(all_tweets_data)} unique tweets across {processed_snapshots} processed weekly snapshots.") # Updated log message
    sys.stdout.flush()
    return all_tweets_data


# --- Main Execution Function (main) ---
# Keep the 'main' function exactly as it was in the previous correct version.
# It handles argument parsing, date conversion, looping through handles,
# calling scrape_profile, and saving the final DataFrame.

def main():
    parser = argparse.ArgumentParser(
        description="Scrape archived Twitter profiles from the Wayback Machine (max 1 snapshot/week).", # Updated description
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # ... (keep all argparse arguments: --handles, --start_date, --end_date, --output) ...
    parser.add_argument('--handles',nargs='+',required=True,help='List of Twitter handles (e.g., google openai microsoft)')
    parser.add_argument('--start_date',type=str,required=True,help='Start date for scraping (YYYY-MM-DD format)')
    parser.add_argument('--end_date',type=str,required=True,help='End date for scraping (YYYY-MM-DD format)')
    parser.add_argument('--output',type=str,required=True,help='Output CSV file path (e.g., data/raw/tweets_raw.csv)')

    args = parser.parse_args()

    output_path = Path(args.output)
    log_file_path = output_path.parent / 'scraper.log'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_file_handler = logging.FileHandler(log_file_path, mode='w')
    log_file_handler.setFormatter(log_formatter)
    logger.addHandler(log_file_handler)

    try:
        start_timestamp = datetime.strptime(args.start_date, "%Y-%m-%d").strftime("%Y%m%d") + "000000"
        end_timestamp = datetime.strptime(args.end_date, "%Y-%m-%d").strftime("%Y%m%d") + "235959"
    except ValueError:
        logger.error("Invalid date format. Please use YYYY-MM-DD.")
        if log_file_handler in logger.handlers:
            log_file_handler.close()
            logger.removeHandler(log_file_handler)
        return

    all_data = []

    with requests.Session() as session:
        session.headers.update({'User-Agent': USER_AGENT})
        for handle in args.handles:
            clean_handle = handle.strip().lstrip('@')
            if not clean_handle: continue
            # Call the profile scraper (which now uses weekly logic)
            tweets = scrape_profile(clean_handle, start_timestamp, end_timestamp, session)
            all_data.extend(tweets)
            if len(args.handles) > 1:
                logger.info(f"Pausing for {SLEEP_BETWEEN_HANDLES} seconds before next handle...")
                sys.stdout.flush()
                time.sleep(SLEEP_BETWEEN_HANDLES)

    if all_data:
        df = pd.DataFrame(all_data)
        # Define preferred column order (same as before)
        cols_order = ['tweet_id', 'author_id', 'timestamp_str', 'text', 'likes', 'retweets', 'replies',
                      'has_media', 'is_retweet_on_timeline', 'retweeted_by',
                      'snapshot_url', 'scraped_at']
        existing_cols = [col for col in cols_order if col in df.columns]
        remaining_cols = [col for col in df.columns if col not in existing_cols]
        final_cols = existing_cols + [col for col in df.columns if col not in existing_cols]
        df = df[final_cols]

        try:
            df.to_csv(output_path, index=False, encoding='utf-8')
            logger.info(f"Successfully saved {len(df)} total unique tweets to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save CSV to {output_path}: {e}")
    else:
        logger.warning("No data collected across all specified handles and dates.")

    handlers = logger.handlers[:]
    for handler in handlers:
        handler.close()
        logger.removeHandler(handler)
    logging.shutdown()
    sys.stdout.flush()


if __name__ == "__main__":
    main()
