Okay, here is a comprehensive `README.md` file for the **Enhanced Engagement Predictor (EEP) Orchestrator** based on the multi-candidate generation script (`orchestrator/main_generator.py`) you've developed.

```markdown
# EEP: Enhanced Engagement Post Generator (Orchestrator)

## Project Goal

This project acts as an orchestrator for generating high-engagement social media posts, specifically tailored for X.com (Twitter). It coordinates multiple specialized AI components (Individual Engagement Predictors - IEPs) to create, evaluate, and select the most promising post suggestion based on user input and contextual analysis.

The primary goal is to automate the creation of relevant, engaging, and brand-aligned content by leveraging individual AI strengths for different sub-tasks like captioning, hashtag generation, image creation/analysis, trend analysis, and engagement prediction.

## Workflow Overview

The EEP orchestrator (`orchestrator/main_generator.py`) follows these steps:

1.  **Input:** Receives a target `username`, an optional `keyword`, and an optional `image_path`.
2.  **Context Gathering:**
    *   Calls the `past-tweet-analyzer` IEP to understand the user's recent posting style, tone, and common themes.
    *   Calls the `trend-analyzer` IEP to fetch current general, tech, and cultural trends and relevant hashtags.
3.  **Keyword Processing:**
    *   Uses the user-provided `keyword` if available.
    *   If no keyword is provided, it attempts to derive one from the user's past themes or current trends; otherwise, it uses a default keyword (e.g., "innovation").
    *   *(Future Enhancement: Could call `keyword-suggester` to refine user-provided keywords).*
4.  **Image Handling:**
    *   If an `image_path` is provided:
        *   Calls the `computer-vision` IEP to get a description of the image.
    *   If no image path is provided:
        *   Constructs a prompt based on the keyword and user context.
        *   Calls the `image-generator` IEP to create a relevant image and obtain its URL.
    *   Determines the `base_image_ref` (path or URL) and `base_has_media` flag for subsequent steps. Handles image processing errors.
5.  **Multi-Candidate Generation Loop:**
    *   Repeats a configured number of times (`NUM_CAPTION_CANDIDATES`).
    *   **Caption Generation:** Calls the `caption-generator` IEP using the keyword, image description (if any), user profile summary, and relevant trends to generate diverse caption options.
    *   **Hashtag Generation:** Calls the `hashtag-generator` IEP for each caption, using caption content, user topics, and trend keywords to get relevant hashtags.
6.  **Candidate Evaluation Loop:**
    *   For each generated caption, creates variations:
        *   Text: With generated hashtags, without generated hashtags.
        *   Media: With the base image (if available), without any image.
    *   For *each* combination:
        *   **Filtering:** Calls the `filter` IEP to check the text content against predefined rules (profanity, sensitivity, custom rules).
        *   **Scoring:** If the filter status is not "NOT OK", calls the `engagement-prediction` IEP with the specific text, media flag, and placeholder time features to get a predicted relative engagement score.
        *   Stores the full details of each evaluated candidate (text, image ref, hashtags, filter status, score).
7.  **Selection:**
    *   Filters the evaluated candidates, keeping only those that passed the filter (status "OK" or "CAN BE CHANGED") and received a valid engagement score.
    *   Selects the candidate with the **highest** predicted relative engagement score.
8.  **Output:**
    *   Prints the selected best post suggestion (caption, hashtags, image reference, predicted score) to the console.
    *   Saves a detailed JSON file (`generation_run_*.json`) containing the run arguments, context gathered, all evaluated candidates, and the final selection for review and analysis.

## Features

*   **Context-Aware Generation:** Utilizes past user tweets and current trends.
*   **Multi-Modal:** Handles both text and optional image inputs/outputs.
*   **Multi-Candidate Generation:** Creates multiple caption variations.
*   **Variation Testing:** Evaluates candidates with/without hashtags and with/without images.
*   **Content Filtering:** Checks generated text against safety/appropriateness rules.
*   **Engagement-Based Selection:** Uses a dedicated prediction model to rank and select the most promising candidate.
*   **Modular Design:** Relies on distinct IEP components for specialized tasks.
*   **Detailed Logging & Output:** Saves comprehensive run details for analysis.

## Setup

1.  **Clone Repository:**
    ```bash
    git clone <your-repo-url>
    cd <repo-directory> # e.g., cd master_content_generator
    ```
2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install Orchestrator Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Ensure IEP Services are Running:** This orchestrator requires the individual IEP services (listed below) to be running and accessible at the configured URLs. Update URLs via environment variables if needed.
5.  **(Optional) Create Output Directories:** The script will attempt to create these if they don't exist:
    ```bash
    mkdir -p generated_content/images
    ```

## Running the Orchestrator

Execute the main script from the **root directory** of the project (e.g., `master_content_generator/`) or ensure Python can find the `orchestrator` package.

```bash
python orchestrator/main_generator.py <username> [--keyword <keyword>] [--image_path <path/to/image.jpg>] [--num_captions <N>]
```

**Arguments:**

*   `username`: (Required) The target X.com username for context gathering (e.g., `Google`).
*   `--keyword`: (Optional) A specific keyword or topic to focus the generation on. If omitted, a keyword will be derived or defaulted.
*   `--image_path`: (Optional) Path to a local image file to use as input. If omitted, the orchestrator will attempt to generate an image.
*   `--num_captions`: (Optional) Number of initial caption candidates to generate. Defaults to `3`.

**Example:**

```bash
# Generate post for user 'Microsoft', focusing on 'Cloud AI'
python orchestrator/main_generator.py Microsoft --keyword "Cloud AI"

# Generate post for user 'Nike', using a provided image
python orchestrator/main_generator.py Nike --image_path path/to/your/shoe_image.png

# Generate post for 'OpenAI' with default keyword and generate 5 caption candidates
python orchestrator/main_generator.py OpenAI --num_captions 5
```

## Input Specification (Command Line)

See "Running the Orchestrator" section above for command-line arguments.

## Output Specification

1.  **Console Output:** Detailed logs showing the workflow progress, calls to simulated IEPs, generated content snippets, filter statuses, engagement scores, and the final selected suggestion printed as a JSON object.
2.  **File Output:** A detailed JSON file saved in the `generated_content/` directory named `generation_run_YYYYMMDD_HHMMSS.json`. This file includes:
    *   `run_args`: The command-line arguments used.
    *   `context_results`: The output received from the initial context-gathering IEPs (Past Tweets, Trends).
    *   `evaluated_candidates`: A list containing *all* generated and evaluated candidates, including their text, media info, filter status, and predicted score (if applicable).
    *   `selected_suggestion`: The single candidate dictionary selected as the best, or `null` if none were suitable.

**Structure of the `selected_suggestion` (if successful):**

```json
{
  "status": "SUCCESS",
  "username": "...",
  "selected_keyword": "...",
  "image_description": "...", // null if no image or CV failed
  "generated_caption": "...",
  "generated_hashtags": ["...", "..."],
  "final_text_suggestion": "...", // caption + hashtags
  "final_image_reference": "...", // URL or path, null if no image
  "has_media": true/false,
  "filter_status": "OK" / "CAN BE CHANGED",
  "predicted_relative_engagement": 1.2345, // null if prediction failed
  "timestamp_generated": "..."
}
```

## IEP Dependencies

This orchestrator relies on the following IEP services being operational and accessible:

| IEP Service             | Default URL (Configurable via Env Var) | Method | Purpose                                     |
| :---------------------- | :------------------------------------- | :----- | :------------------------------------------ |
| Engagement Predictor    | `http://localhost:5010/predict`        | POST   | Scores candidate posts                      |
| Caption Generator       | `http://localhost:5011/generate/caption` | POST   | Generates caption text                      |
| Computer Vision         | `http://localhost:5012/describe_image` | POST   | Describes provided images                   |
| Filter                  | `http://localhost:5013/filter`           | POST   | Checks text content safety/appropriateness  |
| Hashtag Generator       | `http://localhost:5014/generate/hashtags`| POST   | Generates relevant hashtags                 |
| Image Generator         | `http://localhost:5015/generate/image`   | POST   | Creates images from prompts, returns URL    |
| Keyword Suggester       | `http://localhost:5016/generate/keywords`| POST   | *(Currently unused)* Refines input keywords |
| Past Tweet Analyzer     | `http://localhost:5017/analyze/past-tweets` | POST | Analyzes user's recent tweet history        |
| Trend Analyzer          | `http://localhost:5018/analyze/trends`   | GET    | Fetches current trends and hashtags         |

**Note:** The current `main_generator.py` uses **simulated API calls**. To make it functional, replace the logic inside the `call_api` function with actual HTTP requests using the `requests` library pointed at the real running IEP services.

## Configuration

*   **IEP Service URLs:** Primarily configured via environment variables (e.g., `export ENGAGEMENT_PREDICTOR_URL=http://192.168.1.100:5010/predict`). Defaults to `localhost` with ports 5010+ as listed above.
*   **Output Directory:** Defined by `OUTPUT_DIR` constant within the script.
*   **Number of Candidates:** Defined by `NUM_CAPTION_CANDIDATES` constant or `--num_captions` argument.

## Limitations & Future Work

*   **Simulation:** Currently relies on simulated API calls within `call_api`. Needs integration with actual running IEP services.
*   **IEP Quality:** Overall quality depends heavily on the performance of the individual IEPs.
*   **Error Handling:** Basic error handling; needs more robust retries, fallback logic, and clearer error propagation.
*   **Selection Logic:** Currently selects purely based on the highest score among filtered candidates. Could be enhanced with multi-objective ranking (e.g., considering filter status "CAN BE CHANGED" differently) or diversity considerations.
*   **Keyword Derivation:** Logic for deriving keywords when none are provided is basic. Could be improved.
*   **Refinement:** Does not currently implement a loop to re-generate content based on filter feedback ("CAN BE CHANGED") or low scores.
*   **No UI:** Purely a command-line tool at present.

```
