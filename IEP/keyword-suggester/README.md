# IEP: Keyword Suggester

## Purpose

To enhance user-provided keywords by suggesting more engaging, relevant, and potentially trend-aware alternatives. This IEP combines semantic enrichment using NLTK/WordNet with LLM-based refinement to improve the discoverability and effectiveness of keywords used in X.com posts.

## Endpoint Details

*   **Route:** `/generate/keywords`
*   **Method:** `POST`
*   **Trigger Condition:** This IEP should only be called by the EEP if the user actually provides initial keywords.

## Input Specification

*   **Format:** `application/json`

| Field          | Type             | Required | Description                                                                                                |
| :------------- | :--------------- | :------- | :--------------------------------------------------------------------------------------------------------- |
| `keywords`     | `array of strings` | Yes      | A non-empty list of user-provided keywords or key phrases intended for the post.                           |
| `username`     | `string`         | No       | The user's X.com handle. Passed to the LLM prompt for potential contextual style/topic consideration.      |
| `image_context`| `string`         | No       | Optional text description of an associated image (e.g., alt-text, visual summary) to provide more context. |

## Output Specification

### Success (HTTP 200 OK)

*   **Format:** `application/json`

```json
{
  "improved_keywords": [
    "creative design",
    "digital inspiration",
    "art trends",
    "visual storytelling",
    "colorful ideas"
  ]
}