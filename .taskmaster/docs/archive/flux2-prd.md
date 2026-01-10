# Product Requirements Document: Integration of FLUX.2 Image Generation Model

**Version:** 1.0
**Date:** January 7, 2026
**Author:** Implementation Plan

## 1. Overview

### 1.1 Product Background

The i2v app currently uses `flux-general` (FLUX.1) via fal.ai for image-to-image generation. This is outdated. FLUX.2 was released November 25, 2025 by Black Forest Labs and offers:

- **Improved architecture**: Combines Mistral-3 24B VLM with rectified flow transformer
- **Multi-reference support**: Up to 10 reference images
- **Better prompt adherence**: Substantially improved text rendering and world knowledge
- **Higher resolution**: Up to 4MP output
- **Natural language editing**: No masks required for targeted edits

### 1.2 Current Implementation Issues

Based on codebase review:

**Backend (`app/image_client.py`):**
- Only exposes `flux-general` with endpoint `https://queue.fal.run/fal-ai/flux-general/image-to-image`
- Limited parameters: strength, guidance_scale (max 5), num_inference_steps, seed, scheduler

**Frontend (`frontend/src/pages/Playground.tsx`):**
- FLUX settings only shown when `i2iModel === 'flux-general'`
- Parameters: fluxStrength, fluxGuidanceScale, fluxNumInferenceSteps, fluxSeed, fluxScheduler

**Schemas (`app/schemas.py`):**
- `BulkI2IConfig` has FLUX params but only for flux-general model

### 1.3 Target Implementation

Replace/supplement with FLUX.2 models via fal.ai:
- `fal-ai/flux-2` (dev) - Open-source, consumer GPU friendly
- `fal-ai/flux-2-pro` - Production-grade
- `fal-ai/flux-2-flex` - Multi-reference, customizable
- `fal-ai/flux-2-max` - Highest quality, web-grounded generation

Additionally support FLUX.1 Kontext for specialized editing:
- `fal-ai/flux-kontext/dev` - Dev version
- `fal-ai/flux-pro/kontext` - Pro version

## 2. Objectives and Success Criteria

### 2.1 Business Objectives
- Enhanced image quality in i2v pipelines with state-of-the-art model
- Allow full parameter control for user experimentation
- Maintain backward compatibility with existing FLUX.1 workflows

### 2.2 Success Metrics
- 100% parameter pass-through from frontend to fal.ai API
- Successful t2i and i2i generations with FLUX.2 variants
- No regressions in existing model functionality
- Clear model selection with variant descriptions in UI

## 3. Scope

### 3.1 In Scope
- Integration of FLUX.2 variants (dev, pro, flex, max) as selectable models
- Integration of FLUX.1 Kontext (dev, pro) for specialized editing
- Support for t2i and i2i modes via fal.ai endpoints
- Exposure of ALL tweakable parameters in frontend, backend, and database
- Multi-reference image support (up to 10 images for flex/max)
- Logging and error handling for FLUX.2-specific issues
- UI updates: Model dropdown with variant info, conditional parameter sections

### 3.2 Out of Scope
- Local deployment (use fal.ai APIs only)
- Custom LoRA training
- Video-specific extensions

## 4. Functional Requirements

### 4.1 Model Selection

Add these models to `IMAGE_MODELS` in `app/image_client.py`:

| Model ID | fal.ai Endpoint | Pricing | Description |
|----------|-----------------|---------|-------------|
| `flux-2-dev` | `fal-ai/flux-2` | ~$0.025/img | Open-source dev version |
| `flux-2-pro` | `fal-ai/flux-2-pro` | ~$0.05/img | Production text-to-image |
| `flux-2-flex` | `fal-ai/flux-2-flex` | ~$0.04/img | Multi-reference editing |
| `flux-2-max` | `fal-ai/flux-2-max` | ~$0.08/img | Highest quality + web grounding |
| `flux-kontext-dev` | `fal-ai/flux-kontext/dev` | ~$0.025/img | In-context editing (dev) |
| `flux-kontext-pro` | `fal-ai/flux-pro/kontext` | ~$0.04/img | In-context editing (pro) |

Frontend should show FLUX.2-specific parameters only when a FLUX.2 variant is selected.

### 4.2 Generation Workflows

**Text-to-Image (t2i):**
- Use `fal-ai/flux-2-pro` or `fal-ai/flux-2-dev` endpoints
- No source image required

**Image-to-Image (i2i):**
- Use `/image-to-image` sub-endpoint or edit endpoints
- Support natural language editing prompts

**Multi-Reference:**
- For `flux-2-flex` and `flux-2-max`: Accept `image_urls` array (up to 10)
- Allow combining multiple reference images

### 4.3 Pipeline Integration

Modify these files to handle FLUX.2 calls:

1. **`app/image_client.py`**: Add new `_build_flux2_payload()` function
2. **`app/services/generation_service.py`**: Route to FLUX.2 calls based on model
3. **`app/services/pipeline_executor.py`**: Pass all params through `_execute_i2i()`
4. **`app/routers/pipelines.py`**: Ensure `_execute_bulk_pipeline_task` passes FLUX.2 params

### 4.4 Error Handling
- Handle fal.ai errors (invalid param ranges, safety violations)
- Add detailed logging: "Submitting FLUX.2 job" with all param values
- Fallback suggestion: If FLUX.2 fails, suggest trying FLUX.1 or different variant

## 5. Tweakable Parameters

### 5.1 Core Generation Parameters (All Variants)

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `prompt` | string | (required) | - | Text description or edit instruction |
| `image_url` | string | null | - | Source image URL (required for i2i) |
| `image_urls` | array | [] | 1-10 items | Multiple reference images (flex/max only) |
| `guidance_scale` | float | 3.5 | 1.0-10.0 | How strictly to follow prompt |
| `num_inference_steps` | int | 28 | 10-50 | Quality vs speed tradeoff |
| `seed` | int | random | - | For reproducibility |
| `num_images` | int | 1 | 1-4 | Batch generation |

### 5.2 Size and Format Parameters

| Parameter | Type | Default | Options | Description |
|-----------|------|---------|---------|-------------|
| `image_size` | enum/object | "landscape_4_3" | "square_hd", "square", "portrait_4_3", "portrait_16_9", "landscape_4_3", "landscape_16_9", or {width, height} | Output dimensions |
| `output_format` | enum | "png" | "jpeg", "png", "webp" | File format |

### 5.3 Advanced Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strength` | float | 0.75 | Transformation intensity for i2i (0.0-1.0) |
| `enable_prompt_expansion` | bool | false | Auto-expand prompt for better results |
| `safety_tolerance` | enum | "2" | Content filtering: "1" (strict) to "5" (permissive) - flex only |
| `enable_safety_checker` | bool | true | Filter unsafe content |

### 5.4 Variant-Specific Parameters

**FLUX.2 Max Only:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_grounded_generation` | bool | false | Use web-search context |
| `max_references` | int | 1 | Up to 10 reference images |

**FLUX.1 Kontext:**
- Natural language editing without masks
- In-context understanding of source image

## 6. Implementation Tasks

### Phase 1: Backend Integration

1. **Add FLUX.2 model configurations to `image_client.py`**
   - Add all FLUX.2 endpoints to `IMAGE_MODELS` dict
   - Create `_build_flux2_payload()` for each variant
   - Update `ImageModelType` literal type

2. **Update schemas in `app/schemas.py`**
   - Add `Flux2Config` Pydantic model with all parameters
   - Update `ImageJobCreate`, `I2IConfig`, `BulkI2IConfig` to include new params
   - Add multi-image support types

3. **Modify generation service**
   - Update `generate_image()` to handle FLUX.2 params
   - Add proper model routing based on variant

4. **Update pipeline executor**
   - Ensure `_execute_i2i()` passes ALL FLUX.2 params
   - Handle multi-reference image arrays

5. **Update bulk pipeline router**
   - `_execute_bulk_pipeline_task` must pass all new params
   - Add logging for debugging

### Phase 2: Frontend Integration

6. **Update `ModelSelector.tsx`**
   - Add all FLUX.2 model options with descriptions and pricing
   - Group models by provider (Black Forest Labs)

7. **Update `Playground.tsx`**
   - Conditional FLUX.2 parameter panel when FLUX.2 model selected
   - Add all parameter controls (sliders, inputs, toggles)
   - Persist new settings to localStorage
   - Multi-image upload support for flex/max

8. **Update `types.ts`**
   - Add new FLUX.2 model types
   - Add all parameter types

### Phase 3: Testing and Refinement

9. **Add comprehensive logging**
   - Log full payload before submission
   - Log response data for debugging

10. **Test all model variants**
    - Verify each endpoint works
    - Confirm all parameters pass through
    - Test error handling

## 7. Technical Notes

### fal.ai Endpoint URLs
```
Text-to-Image:
- fal-ai/flux-2 (dev)
- fal-ai/flux-2-pro
- fal-ai/flux-2-flex
- fal-ai/flux-2-max

Image-to-Image / Edit:
- fal-ai/flux-2/image-to-image (if available)
- fal-ai/flux-2-flex/edit
- fal-ai/flux-kontext/dev
- fal-ai/flux-pro/kontext
```

### Pricing Reference (fal.ai January 2026)
- FLUX.2 Dev: ~$0.025/image
- FLUX.2 Pro: ~$0.05/image
- FLUX.2 Flex: ~$0.04/image
- FLUX.2 Max: ~$0.08/image
- FLUX.1 Kontext Dev: ~$0.025/image
- FLUX.1 Kontext Pro: ~$0.04/image

### Key Files to Modify
```
Backend:
- app/image_client.py (primary)
- app/schemas.py
- app/services/generation_service.py
- app/services/pipeline_executor.py
- app/routers/pipelines.py

Frontend:
- frontend/src/components/pipeline/ModelSelector.tsx
- frontend/src/pages/Playground.tsx
- frontend/src/api/types.ts
```

## 8. Sources and References

- [fal.ai FLUX.2 API](https://fal.ai/flux-2)
- [fal.ai FLUX Kontext](https://fal.ai/models/fal-ai/flux-kontext/dev/api)
- [Black Forest Labs FLUX.2](https://bfl.ai/models/flux-2)
- [Black Forest Labs Docs](https://docs.bfl.ml/quick_start/introduction)
