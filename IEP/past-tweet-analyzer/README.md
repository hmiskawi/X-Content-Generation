# IEP: Past Tweet Analyzer (X API v2)

## Purpose

To analyze a user's **most recent 5 original tweets** retrieved via the **official X API v2** and extract insights about their common themes, tweeting style, and tone. This IEP aims to enhance personalization by providing a **limited snapshot** of the user’s recent content tendencies, enabling more tailored suggestions from other generator IEPs.

**Note:** Analysis based on only 5 tweets provides very limited insight. Results, especially topic modeling and style/tone analysis, may not be fully representative of the user's overall profile.

## Endpoint Details

*   **Route:** `/analyze/past-tweets`
*   **Method:** `POST`

## Input Specification

*   **Format:** `application/json`

| Field      | Type     | Required | Description                                      |
| :--------- | :------- | :------- | :----------------------------------------------- |
| `username` | `string` | Yes      | The user's X.com handle to fetch tweets for via API. |

## Output Specification

### Success (HTTP 200 OK)

*   **Format:** `application/json`

```json
{
  "common_themes": [
    "ai progress updates", // Example - highly dependent on the 5 tweets
    "space exploration tech"
  ],
  "tweeting_style": "concise (occasional questions?)", // Based on limited data
  "tone": "neutral/undetermined", // Based on limited data
  "typical_hashtags": [
    "#AI",
    "#DevUpdate"
  ],
  "emoji_usage": "minimal emoji use" // Based on limited data
}