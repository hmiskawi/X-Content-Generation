# IEP: Image Generator

## Purpose

To generate raster images (e.g., PNG) based on textual descriptions using Stable Diffusion models via the Stability AI API. This IEP handles prompt construction, API interaction, aspect ratio calculation, and uploads the final image to Azure Blob Storage, returning a publicly accessible URL. It enables the creation of stylized or conceptual images suitable for social media posts.

## Endpoint Details

*   **Route:** `/generate/image`
*   **Method:** `POST`

## Input Specification

*   **Format:** `application/json`

| Field             | Type     | Required | Description                                                                                                   |
| :---------------- | :------- | :------- | :------------------------------------------------------------------------------------------------------------ |
| `prompt`          | `string` | Yes      | A textual description of the desired image content, style, and composition.                                     |
| `style_preference`| `string` | No       | Artistic style guidance (e.g., "digital painting", "photorealistic", "cartoon"). Appended to the core prompt. |
| `aspect_ratio`    | `string` | No       | Desired aspect ratio (e.g., "16:9", "1:1", "9:16"). Defaults to "1:1". Dimensions are calculated based on this. |
| `negative_prompt` | `string` | No       | Text describing elements or qualities to *avoid* in the generated image.                                        |

## Output Specification

### Success (HTTP 200 OK)

*   **Format:** `application/json`

```json
{
  "image_url": "https://yourstorageaccount.blob.core.windows.net/your-container/unique-guid.png",
  "prompt_used": "A majestic fantasy castle on a floating island at sunset, vibrant colors, digital painting style"
}