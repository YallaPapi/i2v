# PRD: Pipeline System Audit & Verification

## Overview

This document defines a comprehensive audit of the recently implemented pipeline system. The goal is to systematically verify every component works correctly end-to-end before considering the implementation complete.

## Background

The following components were implemented but have not been properly tested:

### Backend Components
1. **Database Models** (`app/models.py`): Pipeline, PipelineStep with enums
2. **Prompt Enhancer** (`app/services/prompt_enhancer.py`): Claude API integration
3. **Cost Calculator** (`app/services/cost_calculator.py`): Pricing calculations
4. **Pipeline Executor** (`app/services/pipeline_executor.py`): State machine
5. **Generation Service** (`app/services/generation_service.py`): Fal API wrappers
6. **Pipeline Router** (`app/routers/pipelines.py`): All CRUD + execution endpoints
7. **File Upload** (`app/fal_upload.py`): Fal CDN upload

### Frontend Components
1. **ImageUploadZone** (`frontend/src/components/pipeline/ImageUploadZone.tsx`)
2. **PromptInput** (`frontend/src/components/pipeline/PromptInput.tsx`)
3. **ModelSelector** (`frontend/src/components/pipeline/ModelSelector.tsx`)
4. **SetModeModal** (`frontend/src/components/pipeline/SetModeModal.tsx`)
5. **CostPreview** (`frontend/src/components/pipeline/CostPreview.tsx`)
6. **ProgressMonitor** (`frontend/src/components/pipeline/ProgressMonitor.tsx`)
7. **OutputGallery** (`frontend/src/components/pipeline/OutputGallery.tsx`)
8. **Playground Page** (`frontend/src/pages/Playground.tsx`)

---

## Audit Tasks

### Task 1: Backend Import & Startup Verification

**Objective:** Verify all Python modules import without errors and the server starts cleanly.

**Acceptance Criteria:**
- [ ] `python -c "from app.main import app"` succeeds with no errors (warnings OK)
- [ ] `uvicorn app.main:app` starts without crashing
- [ ] All service singletons initialize (`prompt_enhancer`, `cost_calculator`, `pipeline_executor`)
- [ ] Database tables are created on startup (check `wan_jobs.db` has `pipelines` and `pipeline_steps` tables)

**Test Commands:**
```bash
python -c "from app.main import app; print('OK')"
python -c "from app.services.prompt_enhancer import prompt_enhancer; print('OK')"
python -c "from app.services.cost_calculator import cost_calculator; print('OK')"
python -c "from app.services.pipeline_executor import pipeline_executor; print('OK')"
python -c "from app.services.generation_service import generate_image, generate_video; print('OK')"
sqlite3 wan_jobs.db ".tables"
```

---

### Task 2: File Upload End-to-End Test

**Objective:** Verify file upload works from frontend through to Fal CDN.

**Acceptance Criteria:**
- [ ] Backend `/upload` endpoint accepts PNG/JPG/WEBP files
- [ ] Returns valid Fal CDN URL (starts with `https://v3.fal.media/` or `https://fal.media/`)
- [ ] Frontend ImageUploadZone successfully uploads and displays preview
- [ ] Error handling works for invalid file types
- [ ] Upload caching works (same file returns cached URL)

**Test Commands:**
```bash
# Create test image
python -c "from PIL import Image; Image.new('RGB',(100,100),'red').save('test.png')"

# Test backend directly
curl -X POST http://localhost:8000/upload -F "file=@test.png"

# Test via frontend proxy
curl -X POST http://localhost:5175/upload -F "file=@test.png"

# Test invalid file type rejection
curl -X POST http://localhost:8000/upload -F "file=@README.md"
```

**Frontend Test:**
- Open http://localhost:5175
- Drag and drop an image file
- Verify preview appears
- Verify no console errors

---

### Task 3: Pipeline CRUD API Verification

**Objective:** Verify all pipeline CRUD operations work correctly.

**Acceptance Criteria:**
- [ ] POST `/api/pipelines` creates a pipeline with steps
- [ ] GET `/api/pipelines` lists all pipelines
- [ ] GET `/api/pipelines/{id}` returns pipeline with steps
- [ ] PUT `/api/pipelines/{id}` updates pipeline
- [ ] DELETE `/api/pipelines/{id}` deletes pipeline and steps (cascade)
- [ ] Cost estimates are calculated on creation

**Test Commands:**
```bash
# Create pipeline
curl -X POST http://localhost:8000/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Pipeline",
    "mode": "auto",
    "steps": [{
      "step_type": "i2v",
      "step_order": 0,
      "config": {"model": "kling", "resolution": "1080p", "duration_sec": 5},
      "inputs": {"image_urls": ["https://example.com/test.jpg"], "prompts": ["test"]}
    }]
  }'

# List pipelines
curl http://localhost:8000/api/pipelines

# Get specific pipeline (use ID from create response)
curl http://localhost:8000/api/pipelines/1

# Delete pipeline
curl -X DELETE http://localhost:8000/api/pipelines/1
```

---

### Task 4: Cost Estimation API Verification

**Objective:** Verify cost calculation returns correct pricing.

**Acceptance Criteria:**
- [ ] POST `/api/pipelines/estimate` returns breakdown with totals
- [ ] I2I pricing matches `cost_calculator.py` values
- [ ] I2V pricing matches `cost_calculator.py` values
- [ ] Prompt enhance pricing included when applicable
- [ ] Set mode multipliers calculated correctly

**Test Commands:**
```bash
# I2V cost estimate
curl -X POST http://localhost:8000/api/pipelines/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [{
      "step_type": "i2v",
      "step_order": 0,
      "config": {"model": "kling", "videos_per_image": 1, "resolution": "1080p", "duration_sec": 5}
    }]
  }'
# Expected: $0.35 for kling 5s

# I2I cost estimate
curl -X POST http://localhost:8000/api/pipelines/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [{
      "step_type": "i2i",
      "step_order": 0,
      "config": {"model": "gpt-image-1.5", "quality": "high", "images_per_prompt": 1}
    }]
  }'
# Expected: $0.20 for gpt-image high quality

# Full pipeline cost
curl -X POST http://localhost:8000/api/pipelines/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"step_type": "prompt_enhance", "step_order": 0, "config": {"input_prompts": ["test"], "variations_per_prompt": 5}},
      {"step_type": "i2i", "step_order": 1, "config": {"model": "gpt-image-1.5", "quality": "high"}},
      {"step_type": "i2v", "step_order": 2, "config": {"model": "kling", "duration_sec": 5}}
    ]
  }'
```

---

### Task 5: Prompt Enhancement API Verification

**Objective:** Verify prompt enhancement works with Claude API or fallback.

**Acceptance Criteria:**
- [ ] POST `/api/pipelines/prompts/enhance` returns enhanced prompts
- [ ] Works without Anthropic API key (fallback mode)
- [ ] Works with Anthropic API key (if configured)
- [ ] Returns correct number of variations
- [ ] Different styles produce different results

**Test Commands:**
```bash
# Basic enhancement
curl -X POST http://localhost:8000/api/pipelines/prompts/enhance \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": ["a woman walking on the beach"],
    "count": 3,
    "target": "i2v",
    "style": "cinematic"
  }'

# Multiple prompts
curl -X POST http://localhost:8000/api/pipelines/prompts/enhance \
  -H "Content-Type: application/json" \
  -d '{
    "prompts": ["sunset", "ocean waves"],
    "count": 2,
    "target": "i2i",
    "style": "photorealistic"
  }'
```

---

### Task 6: Pipeline Execution Verification

**Objective:** Verify pipeline execution actually runs and calls Fal APIs.

**Acceptance Criteria:**
- [ ] POST `/api/pipelines/{id}/run` starts execution
- [ ] Pipeline status changes to "running"
- [ ] Steps execute in order
- [ ] Fal API is called for I2I/I2V steps
- [ ] Results are stored in step outputs
- [ ] Pipeline status changes to "completed" or "failed"
- [ ] Errors are captured in step error_message

**Test Commands:**
```bash
# Create pipeline with real image URL
curl -X POST http://localhost:8000/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Execution Test",
    "mode": "auto",
    "steps": [{
      "step_type": "i2v",
      "step_order": 0,
      "config": {"model": "kling", "resolution": "1080p", "duration_sec": 5, "videos_per_image": 1},
      "inputs": {"image_urls": ["YOUR_UPLOADED_IMAGE_URL"], "prompts": ["gentle camera movement"]}
    }]
  }'

# Start execution (use ID from above)
curl -X POST http://localhost:8000/api/pipelines/1/run

# Poll for status
curl http://localhost:8000/api/pipelines/1

# Check step outputs after completion
curl http://localhost:8000/api/pipelines/1/steps
```

---

### Task 7: Frontend Component Rendering Verification

**Objective:** Verify all frontend components render without errors.

**Acceptance Criteria:**
- [ ] Playground page loads at http://localhost:5175
- [ ] No console errors on page load
- [ ] Mode tabs (Edit Image, Animate, Full Pipeline) switch correctly
- [ ] ImageUploadZone renders and accepts drops
- [ ] PromptInput renders with enhance button
- [ ] ModelSelector shows all models grouped by provider
- [ ] Settings sidebar shows correct options per mode
- [ ] CostPreview renders (even if empty)
- [ ] Generate button enables when image + prompt provided

**Manual Test Checklist:**
1. Open http://localhost:5175 in browser
2. Open browser DevTools Console
3. Check for any red errors
4. Click each mode tab
5. Verify sidebar options change per mode
6. Upload an image
7. Enter a prompt
8. Check Generate button becomes enabled
9. Click "Create Photo Set" button in I2I mode
10. Verify SetModeModal opens

---

### Task 8: Frontend-Backend Integration Verification

**Objective:** Verify frontend correctly calls backend APIs.

**Acceptance Criteria:**
- [ ] File upload from frontend works
- [ ] Prompt enhance button calls API and displays results
- [ ] Cost estimate updates when settings change
- [ ] Generate button creates pipeline via API
- [ ] Progress monitor shows pipeline status
- [ ] Results appear in output gallery

**Integration Test Flow:**
1. Upload an image via drag-drop
2. Enter a prompt
3. Click enhance button - verify enhanced prompts appear
4. Change model selection - verify cost updates
5. Click Generate
6. Verify pipeline is created (check Network tab)
7. Verify progress monitor appears
8. Wait for completion
9. Verify output gallery shows results

---

### Task 9: Error Handling Verification

**Objective:** Verify errors are handled gracefully throughout the system.

**Acceptance Criteria:**
- [ ] Invalid file type shows error message (not crash)
- [ ] Network errors show user-friendly message
- [ ] Missing API keys handled gracefully
- [ ] Invalid model names return clear error
- [ ] Pipeline execution failures captured and displayed
- [ ] Frontend shows error states appropriately

**Test Scenarios:**
```bash
# Invalid file type
curl -X POST http://localhost:8000/upload -F "file=@README.md"
# Expected: 400 with clear error message

# Invalid model
curl -X POST http://localhost:8000/api/pipelines/estimate \
  -H "Content-Type: application/json" \
  -d '{"steps": [{"step_type": "i2v", "config": {"model": "nonexistent"}}]}'

# Missing required fields
curl -X POST http://localhost:8000/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### Task 10: Database Integrity Verification

**Objective:** Verify database operations maintain data integrity.

**Acceptance Criteria:**
- [ ] Pipeline deletion cascades to steps
- [ ] Step outputs are valid JSON
- [ ] Cost estimates are stored correctly
- [ ] Status transitions are valid (pending -> running -> completed/failed)
- [ ] No orphaned steps exist

**Test Commands:**
```bash
# Check tables exist
sqlite3 wan_jobs.db ".schema pipelines"
sqlite3 wan_jobs.db ".schema pipeline_steps"

# Check for orphaned steps
sqlite3 wan_jobs.db "SELECT * FROM pipeline_steps WHERE pipeline_id NOT IN (SELECT id FROM pipelines)"

# Verify cascade delete works
# Create pipeline, get ID, delete, verify steps gone
```

---

### Task 11: Model Pricing Consistency Verification

**Objective:** Verify pricing is consistent across frontend display, backend calculation, and source files.

**Acceptance Criteria:**
- [ ] ModelSelector prices match cost_calculator.py
- [ ] cost_calculator.py prices match fal_client.py comments
- [ ] All models in fal_client.py appear in ModelSelector
- [ ] All models in image_client.py appear in ModelSelector

**Files to Cross-Reference:**
- `app/fal_client.py` - MODELS dict with pricing comments
- `app/image_client.py` - IMAGE_MODELS dict with pricing
- `app/services/cost_calculator.py` - I2I_PRICING, I2V_PRICING dicts
- `frontend/src/components/pipeline/ModelSelector.tsx` - I2I_MODELS, I2V_MODELS arrays

---

### Task 12: Vite Proxy Configuration Verification

**Objective:** Verify all API routes are properly proxied.

**Acceptance Criteria:**
- [ ] `/api/*` routes proxy to backend
- [ ] `/upload` route proxies to backend
- [ ] `/health` route proxies to backend
- [ ] No CORS errors in browser console
- [ ] WebSocket connections work (if implemented)

**Test Commands:**
```bash
# Test each proxy route from frontend port
curl http://localhost:5175/health
curl http://localhost:5175/api/pipelines
curl -X POST http://localhost:5175/upload -F "file=@test.png"
```

---

## Success Criteria

The audit is complete when:

1. All 12 tasks have been executed
2. All acceptance criteria checkboxes are checked
3. No critical bugs remain
4. All API endpoints return expected responses
5. Frontend renders without console errors
6. End-to-end flow works: Upload → Configure → Generate → View Results

## Priority Order

Execute tasks in this order:
1. Task 1 (Backend startup) - foundation
2. Task 2 (File upload) - core functionality
3. Task 3 (Pipeline CRUD) - core functionality
4. Task 4 (Cost estimation) - core functionality
5. Task 5 (Prompt enhancement) - feature
6. Task 7 (Frontend rendering) - UI verification
7. Task 12 (Proxy config) - integration prerequisite
8. Task 8 (Frontend-Backend integration) - integration
9. Task 6 (Pipeline execution) - full flow
10. Task 9 (Error handling) - robustness
11. Task 10 (Database integrity) - data safety
12. Task 11 (Pricing consistency) - accuracy
