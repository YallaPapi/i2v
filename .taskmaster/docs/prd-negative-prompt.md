# PRD: Fix Missing Negative Prompt and Image Generation Parameters

## Problem Statement
The image generation pipeline has a critical bug where `negative_prompt` is completely ignored throughout the entire data flow. Users can set negative prompts in the UI, but they are never passed to the Fal API. Additionally, nano-banana is missing the `resolution` parameter.

## Root Cause Analysis
1. `BulkI2IConfig` and `BulkI2VConfig` schemas don't include `negative_prompt` field
2. When i2i/i2v steps are created, negative_prompt is not stored in step config
3. Pipeline executor doesn't pass negative_prompt to generation functions
4. `generate_image()` accepts negative_prompt but it's never called with it from pipelines

## Required Changes

### Task 1: Add negative_prompt to BulkI2IConfig schema
File: `app/schemas.py`
- Add `negative_prompt: Optional[str] = None` to `BulkI2IConfig` class

### Task 2: Add negative_prompt to BulkI2VConfig schema
File: `app/schemas.py`
- Add `negative_prompt: Optional[str] = None` to `BulkI2VConfig` class

### Task 3: Store negative_prompt in i2i step config when creating bulk pipeline
File: `app/routers/pipelines.py`
- In `create_bulk_pipeline()` function, when creating i2i steps, include `negative_prompt` in the step config dict

### Task 4: Store negative_prompt in i2v step config when creating bulk pipeline
File: `app/routers/pipelines.py`
- In `create_bulk_pipeline()` function, when creating i2v steps, include `negative_prompt` in the step config dict

### Task 5: Pass negative_prompt to generate_image() in bulk pipeline executor
File: `app/routers/pipelines.py`
- In `_execute_bulk_pipeline_task()`, when calling `generate_image()`, pass `negative_prompt=config.get("negative_prompt")`

### Task 6: Pass negative_prompt to generate_video() in bulk pipeline executor
File: `app/routers/pipelines.py`
- In `_execute_bulk_pipeline_task()`, when calling `generate_video()`, pass `negative_prompt=config.get("negative_prompt")`

### Task 7: Add resolution parameter to nano-banana payload
File: `app/image_client.py`
- In `_build_image_payload()` for nano-banana model, add `"resolution": "1K"` to the payload dict

### Task 8: Pass negative_prompt in image_client.py for all models that support it
File: `app/image_client.py`
- nano-banana: add `"negative_prompt": negative_prompt` if negative_prompt is provided
- nano-banana-pro: add `"negative_prompt": negative_prompt` if negative_prompt is provided
- gpt-image-1.5: check API docs and add if supported

## Success Criteria
- When user sets a negative prompt in the UI, it reaches the Fal API
- nano-banana generates images with proper resolution
- All i2i image generation respects negative prompts
- All i2v video generation respects negative prompts
