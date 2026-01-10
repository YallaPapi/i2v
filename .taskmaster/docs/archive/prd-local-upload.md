# PRD: Local Image Upload & Auto-Download

## Overview
Enhance the i2v system to support local image folders and automatic video downloads.

## Problem
1. Using external URLs (imgur, etc.) causes rate limiting and job failures
2. Videos are stored as URLs in database but not downloaded automatically
3. No way to batch process multiple local images

## Requirements

### 1. Local Image Upload to Fal CDN

**Functionality:**
- Accept a local folder path containing images
- Upload each image to Fal's CDN before job submission
- Cache uploaded URLs to avoid re-uploading same images
- Support common formats: jpg, jpeg, png, webp

**Implementation:**
- Create `app/fal_upload.py` module
- Use Fal's file upload API endpoint
- Return Fal CDN URL for each uploaded file
- Store mapping of local path → Fal URL in database or cache file

**API Endpoint:**
- Fal upload endpoint: `https://fal.ai/api/storage/upload` or similar
- Use multipart/form-data
- Returns CDN URL like `https://fal.media/files/...`

### 2. Auto-Download on Completion

**Functionality:**
- When a job completes, automatically download the video
- Save to configurable output directory
- Name files descriptively: `{job_id}_{model}_{timestamp}.mp4`

**Implementation:**
- Add download logic to worker's poll function
- Use async streaming download for large files
- Config option: `AUTO_DOWNLOAD_DIR` in .env
- Skip download if file already exists

### 3. Updated Bulk Generate Script

**New CLI options:**
```bash
python scripts/bulk_generate.py prompts/file.txt \
  --images-dir "C:\path\to\images" \
  --model wan \
  --output-dir downloads
```

**Behavior:**
- Scan `--images-dir` for image files
- Upload each to Fal CDN (with caching)
- For each image × each prompt → create job
- Example: 5 images × 6 prompts = 30 jobs

### 4. Image-Prompt Pairing Options

**Option A: All combinations (default)**
- Each image paired with every prompt
- 5 images × 6 prompts = 30 videos

**Option B: One-to-one**
- First image with first prompt, second with second, etc.
- Requires equal count of images and prompts
- Flag: `--one-to-one`

## Database Changes

Add new table for upload cache:
```sql
CREATE TABLE upload_cache (
    id INTEGER PRIMARY KEY,
    local_path TEXT UNIQUE,
    file_hash TEXT,
    fal_url TEXT,
    uploaded_at TIMESTAMP
);
```

## Config Changes

Add to `.env`:
```
AUTO_DOWNLOAD_DIR=downloads
UPLOAD_CACHE_ENABLED=true
```

## Success Criteria
1. Local images upload to Fal CDN without errors
2. Same image re-used without re-uploading
3. Videos auto-download when jobs complete
4. Bulk script handles folder of images
5. No more rate limiting failures
