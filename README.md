# X-Content-Generation

## Overview

X-Content-Generation is a powerful application designed to assist users in creating engaging content suggestions for X.com (formerly Twitter). It leverages a suite of specialized AI/ML microservices orchestrated by a central web UI to analyze context, generate text and images, filter content, and predict engagement.

The goal is to provide users with high-quality, contextually relevant post suggestions tailored to their profile and desired topic, potentially including generated visuals.

## Features

*   **Contextual Analysis:**
    *   Analyzes past user tweets (style, tone, topics, hashtags, emojis) via the X API (requires Bearer Token). Handles user not found or insufficient tweet scenarios gracefully.
    *   Fetches current trending topics and news via Google Trends and NewsAPI.
*   **Content Generation:**
    *   Generates tweet captions using Google Gemini, considering user style, topic, trends, and image context.
    *   Generates relevant hashtags using keyword extraction (YAKE!) and LLM refinement (Google Gemini).
    *   Suggests improved keywords based on initial input, WordNet enrichment, and LLM refinement (Google Gemini).
    *   Generates images relevant to the topic/prompt using Stability AI (if no user image is provided).
*   **Content Enhancement & Analysis:**
    *   Describes user-uploaded images using a Computer Vision model (Hugging Face BLIP).
    *   Filters generated text content for appropriateness using a custom Hugging Face classification model.
    *   Predicts the relative engagement score of generated post candidates using a machine learning model (LightGBM + Sentence Transformer).
*   **Orchestration & UI:**
    *   A Flask-based web UI allows users to input parameters (username, keyword, theme, optional image).
    *   The backend orchestrates calls to the various IEP microservices.
    *   Selects the best post candidate based on filter status and predicted engagement, with fallback logic.
    *   Displays the final suggestion and intermediate results.
*   **Microservice Architecture:** Built using Docker and Docker Compose, with each IEP running as a separate containerized Flask application.

## Architecture

The application follows a microservice architecture:

1.  **EEP UI (External Execution Platform UI):** A Flask web application (`eep_ui` service in Docker Compose) that serves the user interface. It receives user input, calls the orchestrator logic internally, and displays the results.
2.  **Orchestrator Logic:** Python functions (`main_generator.py` module) imported and executed by the EEP UI. This logic coordinates the calls to various IEPs in a defined workflow.
3.  **IEPs (Intelligent Execution Primitives):** Individual Flask microservices, each responsible for a specific task (e.g., `caption_generator`, `image_generator`, `filter`, `past_tweet_analyzer`). They communicate via HTTP REST APIs.
4.  **Docker Compose:** Used to define, build, and run the multi-container application stack.
5.  **Network:** All services communicate over a shared Docker bridge network (`xgen_network`).

```mermaid
graph TD
    User["Browser User"] -->|HTTP Request| EEP_UI["EEP UI Service (Flask)<br>Port 5050"];
    EEP_UI -->|Internal Call| Orchestrator["Orchestrator Logic<br>(main_generator.py)"];

    subgraph IEP Microservices (Docker Network: xgen_network)
        Orchestrator -->|HTTP API Call| PastTweet["past_tweet_analyzer<br>(Port: 5005)"];
        Orchestrator -->|HTTP API Call| Trend["trend_analyzer<br>(Port: 5006)"];
        Orchestrator -->|HTTP API Call| CV["computer_vision<br>(Port: 5021)"];
        Orchestrator -->|HTTP API Call| ImgGen["image_generator<br>(Port: 5003)"];
        Orchestrator -->|HTTP API Call| Caption["caption_generator<br>(Port: 5001)"];
        Orchestrator -->|HTTP API Call| Hashtag["hashtag_generator<br>(Port: 5002)"];
        Orchestrator -->|HTTP API Call| Filter["filter<br>(Port: 5022)"];
        Orchestrator -->|HTTP API Call| Predict["engagement_prediction<br>(Port: 5010)"];
        Orchestrator -->|HTTP API Call| Keyword["keyword_suggester<br>(Port: 5004)"];
    end

    ImgGen -->|API Call| Stability["Stability AI API"];
    ImgGen -->|Blob Upload| Azure["Azure Blob Storage"];
    Caption -->|API Call| Gemini["Google Gemini API"];
    Hashtag -->|API Call| Gemini;
    Keyword -->|API Call| Gemini;
    PastTweet -->|API Call| XAPI["X.com API v2"];
    Trend -->|Lib Call| GTr["Google Trends"];
    Trend -->|API Call| News["NewsAPI"];

    Filter -->|Load Model| HF_Filter["Local Filter Model"];
    CV -->|Load Model| HF_BLIP["Hugging Face BLIP Model"];
    Predict -->|Load Model| LEncoder["Local Sentence Transformer"];
    Predict -->|Load Model| LModel["Local LGBM Model"];

    Orchestrator -->|Result| EEP_UI;
    EEP_UI -->|HTTP Response| User;

    style User fill:#fff,stroke:#333,stroke-width:2px
    style EEP_UI fill:#ccf,stroke:#333,stroke-width:2px