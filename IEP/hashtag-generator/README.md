# IEP: Hashtag Generator

## Purpose

To generate a list of highly relevant, refined, and potentially trend-aware hashtags for an X.com (Twitter) post. This IEP utilizes a hybrid approach, combining automated keyword extraction with Large Language Model (LLM) based refinement. The goal is to deliver hashtags that balance broad reach, niche relevance, and contextual fit, aiming to maximize post visibility and engagement.

## Endpoint Details

*   **Route:** `/generate/hashtags`
*   **Method:** `POST`

## Input Specification

*   **Format:** `application/json`

| Field           | Type             | Required | Description                                                                                         |
| :-------------- | :--------------- | :------- | :-------------------------------------------------------------------------------------------------- |
| `content_context` | `string`         | Yes      | A textual description of the post's content. This could include the caption, keywords, image context, etc. |
| `user_topics`   | `array of strings` | No       | List of topics typically associated with the user's profile (derived from Past Tweet Analysis IEP). |
| `trend_keywords`| `array of strings` | No       | List of currently trending keywords or hashtags relevant to the potential topic area.                |
| `desired_count` | `integer`        | No       | The preferred number of hashtags to generate. Defaults to `4`.                                      |

## Output Specification

### Success (HTTP 200 OK)

*   **Format:** `application/json`

```json
{
  "hashtags": [
    "#relevanthashtag1",
    "#anothergoodone",
    "#nichetag",
    "#broadertag"
  ]
}