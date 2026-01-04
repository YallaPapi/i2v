# PRD: Critical Fixes and Improvements for i2v Service

## Overview

This PRD consolidates findings from two comprehensive code reviews identifying bugs, gaps, and improvements needed to make the i2v service fully functional.

## Priority 1: Critical Bugs (Service Not Working)

### 1.1 Add /api/health Endpoint

**Problem:** Frontend checks `/api/health` but backend only has `/health`. This causes "API offline" status in the UI.

**Solution:** Add health endpoint under `/api` prefix.

**File:** `app/main.py`

**Implementation:**
```python
@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """Health check endpoint for frontend."""
    return {"status": "ok"}
```

### 1.2 Fix Fal Model Routing

**Problem:** CLI supports many `--model` values (`wan`, `wan21`, `wan22`, `kling`, `veo31`, etc.) but backend doesn't properly map them to Fal model IDs. Jobs fail silently or route to wrong endpoint.

**Solution:** Create explicit model mapping in `fal_client.py` with fail-fast for unsupported models.

**File:** `app/fal_client.py`

**Implementation:**
```python
VIDEO_MODEL_MAP = {
    "wan": "fal-ai/wan-25-preview/image-to-video",
    "wan21": "fal-ai/wan-21/image-to-video",
    "kling": "fal-ai/kling-video/v1/standard/image-to-video",
    "veo2": "fal-ai/veo-2",
    # Add all supported models
}

def get_video_model_endpoint(model: str) -> str:
    if model not in VIDEO_MODEL_MAP:
        raise ValueError(f"Unsupported model: {model}. Supported: {list(VIDEO_MODEL_MAP.keys())}")
    return VIDEO_MODEL_MAP[model]
```

### 1.3 Fix Fal Response Parsing

**Problem:** Fal's queue result for Wan 2.5 returns `result.data.video.url` but code may assume different structure like `result["video_url"]`. This causes `wan_video_url` to stay NULL.

**Solution:** Update response parsing to match actual Fal API response structure.

**File:** `app/fal_client.py`

**Implementation:**
```python
def parse_video_result(result: dict, model: str) -> str:
    """Extract video URL from Fal response based on model."""
    # Wan models use data.video.url
    if model.startswith("wan"):
        return result.get("data", {}).get("video", {}).get("url")
    # Kling uses different structure
    elif model == "kling":
        return result.get("video", {}).get("url")
    # Generic fallback
    return result.get("video_url") or result.get("output", [{}])[0].get("url")
```

### 1.4 Fix Image URL Handling

**Problem:** `bulk_generate.py` may pass local file paths (`file:///` or `C:\...`) directly as `image_url` instead of uploading to Fal CDN first. Fal/Wan expects HTTP(S) URLs.

**Solution:** Ensure all local images are uploaded via `fal_upload.py` before job creation.

**File:** `scripts/bulk_generate.py`

**Verification Points:**
- Scan `--images-dir`
- For each image, upload via `fal_upload.py` to get `https://fal.media/files/...` URL
- Use that URL as `image_url` when calling backend `/jobs`
- Confirm `upload_cache` table is used to avoid re-uploads

## Priority 2: Reliability Improvements

### 2.1 Add Retry Logic for API/Fal Calls

**Problem:** Bulk jobs fail midway if API isn't running or Fal rate-limits. No retry mechanism.

**Solution:** Add tenacity retry decorator around job submission and Fal API calls.

**Files:** `scripts/bulk_generate.py`, `app/fal_client.py`

**Implementation:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def submit_to_fal(endpoint: str, payload: dict) -> dict:
    # Fal submission logic
    pass
```

### 2.2 Fix Worker Duplicate Download Prevention

**Problem:** Worker doesn't check for existing files before downloading, causing duplicate downloads.

**Solution:** Add file existence check before download.

**File:** `app/worker.py`

**Implementation:**
```python
if output_path.exists():
    logger.info(f"Skipping existing file: {output_path}")
    return output_path
```

### 2.3 Add Model-Specific Validation

**Problem:** Job creation allows invalid resolution/model combinations (e.g., "1080p" on `wan21` which only supports "580p"). Fal fails silently.

**Solution:** Add model-specific validators in Pydantic schemas.

**File:** `app/schemas.py`

**Implementation:**
```python
from pydantic import field_validator

MODEL_RESOLUTIONS = {
    "wan": ["480p", "720p", "1080p"],
    "wan21": ["480p", "580p"],
    "kling": ["720p", "1080p"],
}

class JobCreate(BaseModel):
    model: str
    resolution: str

    @field_validator('resolution')
    @classmethod
    def validate_resolution(cls, v, info):
        model = info.data.get('model', 'wan')
        valid = MODEL_RESOLUTIONS.get(model, ["480p", "720p", "1080p"])
        if v not in valid:
            raise ValueError(f"Resolution {v} not supported for {model}. Valid: {valid}")
        return v
```

### 2.4 Fix Database Timestamp Auto-Update

**Problem:** `updated_at` not automatically updated on status changes, causing stale data.

**Solution:** Add SQLAlchemy event listener for timestamp updates.

**File:** `app/models.py`

**Implementation:**
```python
from sqlalchemy import event
from datetime import datetime

@event.listens_for(Job, 'before_update')
def update_job_timestamp(mapper, connection, target):
    target.updated_at = datetime.utcnow()
```

### 2.5 Add Timeout Handling for Fal Uploads

**Problem:** `fal_upload.py` doesn't handle large files or network timeouts, causing upload failures.

**Solution:** Add httpx timeouts and file size validation.

**File:** `app/fal_upload.py`

**Implementation:**
```python
MAX_FILE_SIZE_MB = 50
UPLOAD_TIMEOUT_SECONDS = 120

async def upload_image(file_path: Path) -> str:
    file_size = file_path.stat().st_size / (1024 * 1024)
    if file_size > MAX_FILE_SIZE_MB:
        raise ValueError(f"File too large: {file_size:.1f}MB > {MAX_FILE_SIZE_MB}MB limit")

    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT_SECONDS) as client:
        # upload logic with proper timeout
        pass
```

## Priority 3: Feature Gaps

### 3.1 Add API Pagination

**Problem:** `GET /jobs` returns all jobs, inefficient for 100+ jobs, could OOM or timeout.

**Solution:** Add `limit` and `offset` query parameters.

**File:** `app/main.py`

**Implementation:**
```python
@app.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.wan_status == status)
    return query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
```

### 3.2 Improve Download Filename Format

**Problem:** Filename is `{job_id}_{model}.mp4` but should include timestamp to prevent overwrites.

**Solution:** Update filename format to include timestamp.

**File:** `scripts/download_videos.py`

**Implementation:**
```python
from datetime import datetime

filename = f"job_{job['id']}_{job['model']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
```

### 3.3 Add Upload Cache Path Normalization

**Problem:** Upload cache uses raw paths which could have normalization issues (absolute vs relative).

**Solution:** Store normalized absolute paths or use file hash as primary key.

**File:** `app/fal_upload.py`

**Implementation:**
```python
def normalize_path(path: Path) -> str:
    return str(path.resolve().absolute())

def get_cached_url(file_path: Path) -> Optional[str]:
    normalized = normalize_path(file_path)
    # Query cache with normalized path
```

## Priority 4: Monitoring & Debugging

### 4.1 Add Comprehensive Logging

**Problem:** Hard to debug Fal failures - need to see exact request/response.

**Solution:** Add debug logging for Fal API calls.

**File:** `app/fal_client.py`

**Implementation:**
```python
logger.debug("Submitting to Fal",
    endpoint=endpoint,
    payload=payload,
    model=model
)

response = await client.post(endpoint, json=payload)

logger.debug("Fal response",
    status_code=response.status_code,
    body=response.json() if response.ok else response.text
)
```

### 4.2 Add Worker Status Endpoint

**Problem:** No way to monitor worker status or Fal queue backlog.

**Solution:** Add `/api/status` endpoint with job counts by status.

**File:** `app/main.py`

**Implementation:**
```python
@app.get("/api/status")
async def get_status(db: Session = Depends(get_db)):
    return {
        "jobs": {
            "pending": db.query(Job).filter(Job.wan_status == "pending").count(),
            "submitted": db.query(Job).filter(Job.wan_status == "submitted").count(),
            "running": db.query(Job).filter(Job.wan_status == "running").count(),
            "completed": db.query(Job).filter(Job.wan_status == "completed").count(),
            "failed": db.query(Job).filter(Job.wan_status == "failed").count(),
        }
    }
```

## Verification Checklist

After implementing fixes, verify:

1. [ ] Create a test job via API with valid Fal CDN image URL
2. [ ] Confirm `wan_request_id` is set in database after submission
3. [ ] Confirm worker polls and eventually sets `wan_video_url`
4. [ ] Confirm auto-download works without duplicates
5. [ ] Test bulk mode with local images - verify upload cache works
6. [ ] Test invalid model/resolution combo - should fail fast with clear error
7. [ ] Frontend shows "API online" with health endpoint working
