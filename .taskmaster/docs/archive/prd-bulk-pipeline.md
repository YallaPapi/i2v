# PRD: Bulk Pipeline - Multi-Image/Prompt Generation

## Overview

Enable bulk generation workflow: Upload multiple source images, provide image variation prompts and video motion prompts, and generate all combinations in one pipeline run.

**Example workflow:**
- Upload 3 source images
- Provide 2 image prompts → generates 6 image variations (3 images × 2 prompts)
- Provide 2 video prompts → generates 12 videos (6 images × 2 prompts)

---

## User Flow

### Step 1: Upload Source Images
- Drag/drop or click to upload 1-10 source images
- Show thumbnail grid of uploaded images
- Allow remove/reorder

### Step 2: Image Generation (Optional)
- Toggle: "Generate image variations" (skip to go straight to video)
- If enabled:
  - Multi-line textarea for image prompts (one per line)
  - Model selector for i2i
  - Preview: "3 images × 2 prompts = 6 variations"

### Step 3: Video Generation
- Multi-line textarea for video/motion prompts (one per line)
- Model selector for i2v
- Resolution/duration settings
- Preview: "6 images × 2 prompts = 12 videos"

### Step 4: Cost Preview & Generate
- Show full cost breakdown tree
- "Generate All" button
- Progress monitor showing all generations

### Step 5: Results
- Grid of all outputs organized by source image
- Bulk download by source image or all

---

## Technical Requirements

### Backend Changes

#### 1. New Bulk Pipeline Endpoint
```
POST /api/pipelines/bulk
{
  "name": "Bulk Generation",
  "source_images": ["url1", "url2", "url3"],
  "i2i_config": {
    "enabled": true,
    "prompts": ["prompt 1", "prompt 2"],
    "model": "gpt-image-1.5",
    "images_per_prompt": 1
  },
  "i2v_config": {
    "prompts": ["motion prompt 1", "motion prompt 2"],
    "model": "kling",
    "resolution": "1080p",
    "duration_sec": 5
  }
}
```

#### 2. Bulk Pipeline Execution
- Create pipeline with multiple steps:
  - One i2i step per (source_image × i2i_prompt) combination
  - One i2v step per (result_image × i2v_prompt) combination
- Execute steps with concurrency limit (max 3 parallel)
- Track progress per step
- Handle partial failures (continue with remaining)

#### 3. New Schemas
- `BulkPipelineCreate` - request schema
- `BulkPipelineResponse` - response with all outputs grouped

#### 4. Cost Estimation for Bulk
```
POST /api/pipelines/bulk/estimate
```
- Calculate total cost for all combinations
- Return breakdown by step type

### Frontend Changes

#### 1. New Playground Mode: "Bulk" Tab
- Replace current single-image flow with bulk workflow
- Multi-image upload zone
- Multi-prompt input (textarea with line-by-line parsing)
- Pipeline preview showing matrix

#### 2. Multi-Image Upload Component
- Grid display of uploaded images
- Add/remove individual images
- Show count: "3 images uploaded"

#### 3. Multi-Prompt Input Component
- Textarea that parses lines into array
- Show count: "2 prompts entered"
- Enhance all prompts button

#### 4. Pipeline Matrix Preview
- Visual diagram: Images → (optional) I2I → I2V → Outputs
- Show multiplication: 3 × 2 × 2 = 12 outputs
- Expandable cost breakdown

#### 5. Bulk Progress Monitor
- Progress bar for overall pipeline
- Expandable list of individual step progress
- Show completed outputs as they finish

#### 6. Bulk Results Gallery
- Group by source image
- Expandable sections
- "Download All from Image 1" button per group
- "Download All" master button

---

## Data Model

### Pipeline Steps for Bulk
Each step tracks its lineage:
```json
{
  "step_type": "i2v",
  "config": {...},
  "inputs": {
    "source_image_index": 0,
    "source_image_url": "...",
    "prompt_index": 1,
    "prompt": "..."
  },
  "outputs": {
    "items": [{"url": "...", "type": "video"}]
  }
}
```

### Grouping in Response
```json
{
  "pipeline_id": 123,
  "status": "completed",
  "groups": [
    {
      "source_image": "url1",
      "source_index": 0,
      "i2i_outputs": [...],
      "i2v_outputs": [...]
    }
  ],
  "totals": {
    "source_images": 3,
    "i2i_generated": 6,
    "i2v_generated": 12
  }
}
```

---

## Files to Create/Modify

### Backend
- `app/schemas.py` - Add BulkPipelineCreate, BulkPipelineResponse
- `app/routers/pipelines.py` - Add /bulk and /bulk/estimate endpoints
- `app/services/pipeline_executor.py` - Add bulk execution logic with concurrency

### Frontend
- `frontend/src/pages/Playground.tsx` - Add Bulk tab and workflow
- `frontend/src/components/pipeline/MultiImageUpload.tsx` - New component
- `frontend/src/components/pipeline/MultiPromptInput.tsx` - New component
- `frontend/src/components/pipeline/BulkPreview.tsx` - Matrix preview
- `frontend/src/components/pipeline/BulkProgress.tsx` - Bulk progress monitor
- `frontend/src/components/pipeline/BulkResults.tsx` - Grouped results gallery

---

## Success Criteria

1. User can upload multiple source images (1-10)
2. User can enter multiple prompts for both i2i and i2v (1-10 each)
3. System generates all combinations in parallel (with rate limiting)
4. Progress shows per-step status
5. Results grouped by source image
6. Bulk download works for all outputs
7. Cost estimation accurate before generation
8. Partial failures don't crash entire pipeline
