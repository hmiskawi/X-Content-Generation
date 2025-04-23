# IEP: Engagement Predictor

## Purpose

To predict the relative engagement (specifically, `Likes / Author's Average Likes`) for a potential X.com post based on its textual content and basic metadata. This IEP loads a pre-trained machine learning pipeline (expected to be a scikit-learn pipeline including preprocessing and a regression model like XGBoost) and serves predictions via a REST API.

## Endpoint Details

### Health Check

*   **Route:** `/`
*   **Method:** `GET`
*   **Description:** Returns the status of the API and the loaded model. Useful for monitoring and deployment checks.
*   **Output (Success - 200 OK):**
    ```json
    {
      "message": "Engagement Prediction API",
      "model_status": "LOADED",
      "model_path_used": "/app/models/engagement_model_pipeline.pkl"
    }
    ```
*   **Output (Model Load Error - 200 OK but indicates issue):**
    ```json
    {
      "message": "Engagement Prediction API",
      "model_status": "ERROR: Model file not found at /app/models/engagement_model_pipeline.pkl",
      "model_path_used": "/app/models/engagement_model_pipeline.pkl"
    }
    ```

### Prediction

*   **Route:** `/predict`
*   **Method:** `POST`
*   **Description:** Predicts the relative engagement score for the provided post details.

## Input Specification (`/predict`)

*   **Format:** `application/json`

| Field         | Type      | Required | Description                                                                                                                               | Example     |
| :------------ | :-------- | :------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :---------- |
| `text`        | `string`  | Yes      | The full text content of the potential post.                                                                                              | "Check out our new blog post! #AI" |
| `has_media`   | `integer` | Yes      | Flag indicating media presence. `1` if the post includes an image or video, `0` otherwise.                                                    | `1`         |
| `hour_of_day` | `integer` | Yes      | The hour (0-23) when the post is intended to be published (UTC or consistent timezone expected by the model).                             | `16`        |
| `weekday`     | `integer` | Yes      | The day of the week (0 = Monday, 1 = Tuesday, ..., 6 = Sunday) when the post is intended to be published.                                   | `2` (Wed)   |

**Note:** Features like `num_hashtags`, `num_mentions`, `num_urls`, and `text_length` are calculated *internally* by the API from the provided `text` input before being passed to the model pipeline. They should **not** be included in the input JSON payload.

## Output Specification (`/predict`)

### Success (HTTP 200 OK)

*   **Format:** `application/json`

```json
{
  "predicted_relative_engagement": 1.4572
}
Description: The predicted score represents how the post's engagement (likes) might compare to the author's historical average (e.g., 1.45 means ~45% higher engagement than average is predicted).
