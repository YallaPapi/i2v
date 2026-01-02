Below is a PRD you can hand straight to a coding agent.

***

# PRD: Image → Wan 2.5 Video Generation Service

## 1. Goal

Build a small backend service that:

1. Takes a list of image URLs and motion prompts.
2. For each image, calls a Wan 2.5 **image‑to‑video** API (Fal or similar).
3. Stores and exposes the resulting **video URLs**.

No UI needed beyond basic health/status endpoints. All orchestration must be in **code**, not n8n.

***

## 2. Tech Stack & Assumptions

- Language: **Python** (preferred) or Node.js if necessary.
- Data store: **SQLite** for v1 (file‑based, simple) with an easy path to swap to Postgres/MySQL later.
- Runtime: Can run on a laptop or a cheap VPS.
- External services:
  - **Wan 2.5 image‑to‑video via Fal API** (default).[1]
    - Async queue model: submit job → poll for result.
  - API keys supplied via environment variables.

***

## 3. Data Model

Use a single table `jobs` to represent each image → video request.

**Table: `jobs`**

| Column          | Type        | Description                                           |
|-----------------|------------|-------------------------------------------------------|
| id              | INTEGER PK | Internal id                                           |
| image_url       | TEXT        | URL of image to animate                              |
| motion_prompt   | TEXT        | Text describing motion / camera                      |
| resolution      | TEXT        | e.g. `480p`, `1080p`                                 |
| duration_sec    | INTEGER     | e.g. 5 or 10                                         |
| wan_request_id  | TEXT NULL   | Returned job id from Wan/Fal                         |
| wan_status      | TEXT        | `pending`, `submitted`, `running`, `completed`, `failed` |
| wan_video_url   | TEXT NULL   | Final MP4 URL when completed                         |
| error_message   | TEXT NULL   | Error details if failed                              |
| created_at      | DATETIME    | Creation time                                        |
| updated_at      | DATETIME    | Last update time                                     |

***

## 4. External API Integration: Wan 2.5 on Fal

Use Fal's **Wan 2.5 image‑to‑video** model.[1]

### 4.1 Configuration

- Env var: `FAL_API_KEY`.
- Base: use the official Fal client or plain HTTP requests to:
  - Queue submit endpoint for `"fal-ai/wan-25-preview/image-to-video"`.
  - Queue result endpoint for same model.[2][1]

### 4.2 Submit Job

Implement:

```python
def submit_wan_job(image_url: str, motion_prompt: str, resolution: str, duration_sec: int) -> str:
    """
    Calls Fal's Wan 2.5 image-to-video queue submit endpoint.
    Returns wan_request_id.
    """
```

Behavior:

- Construct JSON:

  ```json
  {
    "input": {
      "prompt": "<motion_prompt>",
      "image_url": "<image_url>",
      "resolution": "<resolution>",       // "480p" or "1080p"
      "duration": "<duration_sec_as_string>",
      "negative_prompt": "low resolution, error, worst quality, low quality, artifacts",
      "enable_prompt_expansion": true,
      "enable_safety_checker": true
    }
  }
  ```

- Send authenticated request with `FAL_API_KEY`.
- On success: parse and return `request_id`.[1]
- On error: raise exception; caller will update `wan_status = 'failed'` and `error_message`.

### 4.3 Poll Job Result

Implement:

```python
def get_wan_result(wan_request_id: str) -> dict:
    """
    Calls Fal's Wan 2.5 queue result endpoint.
    Returns a dict with:
      - status: "pending" | "running" | "succeeded" | "failed"
      - video_url: str | None
      - error_message: str | None
    """
```

Behavior:

- Query Fal's queue result endpoint for the given `request_id`.[1]
- Map Fal's internal state to generic `status`.
- If succeeded and `data.video.url` exists, return `video_url`.
- If failed, set `error_message`.
- If still in progress, status should be `pending` or `running` and `video_url = None`.

***

## 5. Core Service Logic

### 5.1 Job Creation API

Create a simple HTTP endpoint (FastAPI or Flask):

`POST /jobs`

Request body:

```json
{
  "image_url": "https://example.com/path/to/image.png",
  "motion_prompt": "Keep the same person and outfit. She changes pose slightly, camera slowly pushes in.",
  "resolution": "1080p",
  "duration_sec": 5
}
```

Behavior:

- Validate inputs:
  - `image_url`: non‑empty string.
  - `resolution`: must be `"480p"` or `"1080p"` (extendable).
  - `duration_sec`: allowed values: `5` or `10`.
- Insert new row into `jobs`:
  - `wan_status = 'pending'`.
  - `wan_request_id = NULL`.
  - `wan_video_url = NULL`.
- Return created job row as JSON (including `id`).

### 5.2 Job Status API

`GET /jobs/{id}`

Returns JSON representation of the job:

```json
{
  "id": 1,
  "image_url": "...",
  "motion_prompt": "...",
  "resolution": "1080p",
  "duration_sec": 5,
  "wan_status": "completed",
  "wan_video_url": "https://fal-cdn.com/output/video.mp4",
  "error_message": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### 5.3 Batch Listing

`GET /jobs?status=pending|submitted|completed|failed`

- Allow filtering by `wan_status`.
- Return a list of jobs (paginated later if necessary).

***

## 6. Background Worker

Implement a simple **looping worker** (could be a separate process or thread) that runs continuously (or on a short interval).

### 6.1 Responsibilities

1. **Submit pending jobs**

   - Query `jobs` where `wan_status = 'pending'`.
   - For each:
     - Call `submit_wan_job(...)`.
     - On success:
       - Set `wan_request_id` to returned id.
       - Set `wan_status = 'submitted'`.
     - On failure:
       - Set `wan_status = 'failed'`.
       - Set `error_message`.

2. **Poll submitted jobs**

   - Query `jobs` where `wan_status IN ('submitted', 'running')`.
   - For each:
     - Call `get_wan_result(wan_request_id)`.
     - If status still pending/running:
       - Update `wan_status` accordingly.
     - If succeeded with `video_url`:
       - Set `wan_status = 'completed'`.
       - Set `wan_video_url = video_url`.
     - If failed:
       - Set `wan_status = 'failed'`.
       - Set `error_message`.

3. Sleep for a short interval (e.g. 5–15 seconds) and repeat.

### 6.2 Concurrency & Limits

- Initial v1 can be **sequential**; optimize later if needed.
- Add `MAX_CONCURRENT_SUBMITS` and `MAX_CONCURRENT_POLLS` constants for future scaling.

***

## 7. Configuration

Use environment variables:

- `FAL_API_KEY` – required.
- `DB_PATH` – path to SQLite DB (default: `wan_jobs.db`).
- `WORKER_POLL_INTERVAL_SECONDS` – default 10.
- `DEFAULT_RESOLUTION` – fallback if not set per job (e.g. `1080p`).
- `DEFAULT_DURATION_SEC` – fallback (e.g. `5`).

***

## 8. Error Handling & Retries

- If submit fails (Fal returns error or network exception):
  - Set `wan_status = 'failed'`.
  - Store `error_message`.
  - Optionally add a retry count if you want automatic retries later.

- If poll fails temporarily:
  - Keep status as `submitted` or `running`.
  - Log error; retry on next loop.

- If Fal reports job failed:
  - Set `wan_status = 'failed'`.
  - Persist Fal's error message.

***

## 9. Testing Requirements

Agent should provide:

1. Unit tests for:
   - `submit_wan_job` (with mocked Fal responses).
   - `get_wan_result` (mocked Fal responses for pending, success, failure).
   - Worker logic transitions between statuses.

2. An example script:

   `scripts/demo_create_jobs.py`

   - Reads a small JSON or CSV of `{image_url, motion_prompt}`.
   - Calls `POST /jobs` for each.
   - Prints resulting job ids.

3. README that shows:

   - How to set `FAL_API_KEY`.
   - How to run DB migrations/init.
   - How to run the API server.
   - How to run the worker.
   - Example `curl` commands to create a job and fetch the final `wan_video_url`.

***

## 10. Future Extensions (for context, not required now)

- Swap SQLite for Postgres.
- Support multiple providers (e.g. AIMLAPI / WaveSpeed Wan 2.5) via a provider abstraction.[3][4]
- Add optional download & re‑upload of final MP4 to own storage.
- Add a `hook_text` field and a later overlay stage for 1‑sentence on‑screen captions.

***

This PRD's v1 deliverable is a **working backend** that:

- Accepts images + prompts.
- Pipes them into Wan 2.5 image‑to‑video via Fal.
- Exposes the resulting video URLs cleanly so later stages (captions, posting) can hook in.

[1](https://fal.ai/models/fal-ai/wan-25-preview/image-to-video/api)
[2](https://novita.ai/docs/api-reference/model-apis-wan2.5-i2v)
[3](https://docs.aimlapi.com/api-references/video-models/alibaba-cloud/wan-2.5-preview-image-to-video)
[4](https://wavespeed.ai/docs-api/alibaba/alibaba-wan-2.5-image-to-video)
