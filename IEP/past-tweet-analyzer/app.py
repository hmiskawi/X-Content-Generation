import os
import logging
import re
import string
from collections import Counter

import tweepy # Use tweepy for X API v2
import nltk
# Ensure NLTK data is available (download step is in Dockerfile)
try:
    nltk.data.find('corpora/stopwords')
    nltk.data.find('tokenizers/punkt')
    # nltk.data.find('corpora/wordnet.zip') # Uncomment if using wordnet
except LookupError:
    logging.warning("NLTK data missing despite Docker download step? Analysis might fail.")
    # Attempt download again (might fail in restricted envs)
    # nltk.download('stopwords', quiet=True)
    # nltk.download('punkt', quiet=True)
    # nltk.download('wordnet', quiet=True)

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import gensim
from gensim import corpora
from gensim.models import LdaModel
from sklearn.feature_extraction.text import CountVectorizer
import regex # For better emoji handling

from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# X API Configuration
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

# Analysis Parameters
NUM_TWEETS_TO_FETCH = 5 # Fetch only the last 5 original tweets
MIN_TWEETS_FOR_ANALYSIS = 3 # Need at least 3 valid tweets for any meaningful analysis
NUM_TOPICS_LDA = 2 # Reduced topics due to low tweet count
NUM_TOP_WORDS_PER_TOPIC = 4
MIN_TWEET_LENGTH_FOR_ANALYSIS = 15 # Ignore very short tweets for topic modeling

# --- Initialize Tweepy Client ---
tweepy_client = None
if X_BEARER_TOKEN:
    try:
        tweepy_client = tweepy.Client(bearer_token=X_BEARER_TOKEN, wait_on_rate_limit=False)
        # Test authentication slightly (optional, remove if causing startup issues)
        # me_user = tweepy_client.get_me() # This requires User Context auth, not Bearer. Cannot test Bearer this way easily.
        logging.info("Tweepy client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Tweepy client: {e}", exc_info=True)
        tweepy_client = None
else:
    logging.error("FATAL: X_BEARER_TOKEN environment variable not set.")


# --- Helper Functions (Adapted/Kept) ---

def preprocess_text(text: str) -> str:
    """Basic text preprocessing: lowercase, remove URLs, mentions, hashtags symbol, punctuation, stopwords."""
    # (Keep previous implementation, it's generally fine)
    if not text: return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\@\w+', '', text)
    text = text.replace("#", "") # Remove only the symbol
    text = text.translate(str.maketrans('', '', string.punctuation.replace('_',''))) # Keep underscores if desired
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word.isalpha() and word not in stop_words and len(word) > 1]
    return " ".join(filtered_tokens)

def extract_hashtags_from_entities(tweet_entities: dict) -> list[str]:
    """Extracts hashtags from the API's tweet entities object."""
    hashtags = []
    if tweet_entities and 'hashtags' in tweet_entities:
        for tag_info in tweet_entities['hashtags']:
            if 'tag' in tag_info:
                hashtags.append(f"#{tag_info['tag']}") # Add # back
    return hashtags

def extract_emojis(text: str) -> list[str]:
    """Extracts emojis using the regex library."""
    # (Keep previous implementation)
    emoji_pattern = regex.compile(r'\p{Emoji}')
    return emoji_pattern.findall(text)

def analyze_topics_lda(texts: list[str], num_topics: int, num_words: int) -> list[str]:
    """Performs LDA topic modeling. WARNING: Results likely poor with low tweet count."""
    if not texts or len(texts) < max(MIN_TWEETS_FOR_ANALYSIS, num_topics): # Need enough docs
        logging.warning(f"Not enough documents ({len(texts)}) for LDA analysis with {num_topics} topics.")
        return []
    logging.warning("Running LDA on a very small number of tweets (<10). Results may be unreliable.")
    try:
        vectorizer = CountVectorizer(max_df=0.90, min_df=1, stop_words='english') # Adjust min_df to 1 for small corpus
        doc_term_matrix = vectorizer.fit_transform(texts)
        feature_names = vectorizer.get_feature_names_out()

        if doc_term_matrix.shape[1] == 0: # Check if vocabulary is empty
             logging.warning("LDA failed: Vocabulary is empty after vectorization.")
             return []

        corpus = gensim.matutils.Sparse2Corpus(doc_term_matrix, documents_columns=False)
        dictionary = corpora.Dictionary.from_corpus(corpus, id2word=dict((i, s) for i, s in enumerate(feature_names)))

        # Adjust LDA parameters for small dataset if needed, though results still limited
        lda_model = LdaModel(corpus=corpus,
                             id2word=dictionary, # Use the created dictionary
                             num_topics=num_topics,
                             random_state=42,
                             passes=15, # More passes might help slightly
                             alpha='auto',
                             eta='auto', # symmetric eta might be better for small data
                             minimum_probability=0.01)

        topics = []
        for idx, topic in lda_model.show_topics(formatted=False, num_words=num_words):
            topic_words = [word[0] for word in topic]
            topics.append(" ".join(topic_words))
        logging.info(f"LDA Themes (potentially unreliable): {topics}")
        return topics
    except ValueError as ve:
         logging.error(f"LDA failed, likely due to vocabulary/data issues: {ve}", exc_info=True)
         return []
    except Exception as e:
        logging.error(f"LDA analysis failed: {e}", exc_info=True)
        return []


def analyze_style_tone_heuristics(texts: list[str]) -> tuple[str, str]:
    """Basic heuristic analysis. WARNING: Limited reliability with low tweet count."""
    # (Keep previous implementation, but results are less meaningful)
    if not texts: return "unknown", "unknown"
    # ... (rest of the heuristic logic remains the same) ...
    total_len = 0
    question_count = 0
    exclamation_count = 0
    num_texts = len(texts)

    for text in texts:
        total_len += len(text)
        if '?' in text: question_count += 1
        if '!' in text: exclamation_count += 1

    avg_len = total_len / num_texts if num_texts > 0 else 0

    style = ""
    if avg_len == 0: style = "no text found"
    elif avg_len < 100: style = "concise"
    elif avg_len > 200: style = "potentially long-form"
    else: style = "moderate length"

    if num_texts > 0:
        if question_count / num_texts > 0.2: style += " (frequent questions?)"
        elif question_count / num_texts > 0.05: style += " (occasional questions?)"

    tone = "neutral/undetermined"
    if num_texts > 0:
        if exclamation_count / num_texts > 0.25: tone = "potentially enthusiastic/emphatic"
        elif exclamation_count / num_texts > 0.1: tone = "mildly expressive"

    logging.info(f"Heuristic Style (Limited): {style}, Tone (Limited): {tone}")
    return style, tone

def get_top_items(items_list: list, top_n: int = 5) -> list:
    """Finds the most common items in a list."""
    # (Keep previous implementation)
    if not items_list: return []
    counter = Counter(items_list)
    return [item for item, count in counter.most_common(top_n)]

# --- API Interaction Functions ---

def get_user_id(username: str) -> str | None:
    """Gets the user ID for a given username using Tweepy."""
    if not tweepy_client: return None
    try:
        logging.info(f"Fetching user ID for username: {username}")
        response = tweepy_client.get_user(username=username)
        if response.data:
            user_id = response.data.id
            logging.info(f"Found user ID: {user_id}")
            return user_id
        else:
            logging.warning(f"User not found: {username}")
            return None
    except tweepy.errors.NotFound:
         logging.warning(f"User not found via Tweepy API: {username}")
         return None
    except tweepy.errors.TweepyException as e:
        logging.error(f"Tweepy API error fetching user '{username}': {e}", exc_info=True)
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching user ID for '{username}': {e}", exc_info=True)
        return None


def fetch_tweets_api(user_id: str, limit: int) -> list:
    """Fetches recent original tweets for a user ID using Tweepy."""
    if not tweepy_client: return []
    tweets_data = []
    try:
        logging.info(f"Fetching max {limit} tweets for user ID: {user_id}")
        # Fetch tweets, excluding retweets and replies
        # Request 'entities' to get hashtag info
        response = tweepy_client.get_users_tweets(
            id=user_id,
            max_results=limit,
            exclude=["retweets", "replies"],
            tweet_fields=["created_at", "entities", "public_metrics"] # Request needed fields
        )

        if response.data:
            for tweet in response.data:
                tweets_data.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "entities": tweet.entities, # Contains hashtags, mentions etc.
                    "metrics": tweet.public_metrics
                })
            logging.info(f"Fetched {len(tweets_data)} tweets via API for user ID {user_id}")
        else:
             logging.info(f"No non-retweet/reply tweets found recently for user ID {user_id}.")

        return tweets_data

    except tweepy.errors.NotFound:
         logging.warning(f"User ID not found or tweets are protected/unavailable: {user_id}")
         return []
    except tweepy.errors.TweepyException as e:
        # Handle specific errors like rate limits if needed
        logging.error(f"Tweepy API error fetching tweets for user ID '{user_id}': {e}", exc_info=True)
        # Check for rate limit error specifically?
        # if isinstance(e, tweepy.errors.TooManyRequests):
        #     logging.error("Rate limit exceeded.")
        return [] # Return empty on API error
    except Exception as e:
        logging.error(f"Unexpected error fetching tweets for user ID '{user_id}': {e}", exc_info=True)
        return []

# --- API Endpoint ---

@app.route('/analyze/past-tweets', methods=['POST'])
def analyze_tweets_endpoint():
    """Analyzes past 5 tweets fetched via API for a given username."""
    if not tweepy_client:
        logging.error("X API client not initialized. Check Bearer Token.")
        return jsonify({"error": "Tweet analysis service not available (config error)"}), 503 # Service Unavailable

    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    username = data.get('username')

    if not username or not isinstance(username, str):
        return jsonify({"error": "Missing or invalid required field: username"}), 400

    # --- 1. Get User ID ---
    user_id = get_user_id(username)
    if not user_id:
        return jsonify({"error": f"User '{username}' not found or API error occurred."}), 404 # User not found

    # --- 2. Fetch Tweets ---
    user_tweets = fetch_tweets_api(user_id, NUM_TWEETS_TO_FETCH)

    if len(user_tweets) < MIN_TWEETS_FOR_ANALYSIS:
        logging.warning(f"Found only {len(user_tweets)} valid tweets via API for {username}. Insufficient for full analysis.")
        return jsonify({"error": f"Could not retrieve sufficient recent original tweets for analysis (found {len(user_tweets)}). User may have protected tweets or low activity."}), 404 # Treat as not found/unavailable data

    # --- 3. Preprocessing & Feature Extraction ---
    all_hashtags = []
    all_emojis = []
    processed_tweets_for_lda = []
    raw_tweet_texts = []

    logging.info(f"Preprocessing {len(user_tweets)} tweets for {username}...")
    for tweet_data in user_tweets:
        text = tweet_data.get("text", "")
        entities = tweet_data.get("entities")
        raw_tweet_texts.append(text) # Keep raw text for style/tone heuristics

        all_hashtags.extend(extract_hashtags_from_entities(entities))
        all_emojis.extend(extract_emojis(text))

        if len(text) >= MIN_TWEET_LENGTH_FOR_ANALYSIS:
            processed = preprocess_text(text)
            if processed:
                 processed_tweets_for_lda.append(processed)

    logging.info(f"Prepared {len(processed_tweets_for_lda)} tweets for LDA.")

    # --- 4. Analysis ---
    common_themes = analyze_topics_lda(processed_tweets_for_lda, NUM_TOPICS_LDA, NUM_TOP_WORDS_PER_TOPIC)
    tweeting_style, tone = analyze_style_tone_heuristics(raw_tweet_texts)
    typical_hashtags = get_top_items(all_hashtags, top_n=5) # Already have # prefix
    top_emojis = get_top_items(all_emojis, top_n=5)
    emoji_usage = f"frequent use of {' '.join(top_emojis)}" if top_emojis else "minimal emoji use"


    # --- 5. Compile Results ---
    result = {
        "common_themes": common_themes,
        "tweeting_style": tweeting_style,
        "tone": tone,
        "typical_hashtags": typical_hashtags,
        "emoji_usage": emoji_usage
    }

    logging.info(f"API-based analysis complete for {username}. Results: {result}")
    return jsonify(result), 200

# --- Run the App ---
if __name__ == '__main__':
    # Use port 5005
    app.run(host='0.0.0.0', port=5017, debug=False)
