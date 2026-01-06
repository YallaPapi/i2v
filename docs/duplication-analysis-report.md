# Code Duplication Analysis Report

Generated: 2026-01-06

## Executive Summary

Code duplication analysis using jscpd detected **29 total clones** across the codebase:
- **Python Backend**: 14 clones (1.69% of lines)
- **TypeScript Frontend**: 15 clones (4.21% of lines)

The most significant finding is **170 lines of nearly identical code** between `ImageGeneration.tsx` and `VideoGeneration.tsx`, representing a high-priority refactoring opportunity.

## Duplication Statistics

| Area | Files Analyzed | Total Lines | Clones Found | Duplicated Lines | % |
|------|----------------|-------------|--------------|------------------|---|
| Python Backend | 32 | 10,619 | 14 | 179 | 1.69% |
| TypeScript Frontend | 71 | 8,227 | 15 | 346 | 4.21% |
| **Total** | 103 | 18,846 | 29 | 525 | 2.79% |

## High Priority Duplications

### 1. ImageGeneration.tsx vs VideoGeneration.tsx (CRITICAL)

**Impact**: HIGH | **Lines**: 170 | **Files**: 2

| Location | Lines |
|----------|-------|
| `frontend/src/pages/ImageGeneration.tsx` | 114-284 |
| `frontend/src/pages/VideoGeneration.tsx` | 111-263 |

**Duplicated Elements**:
- Source image input with URL/Upload tab switching
- Prompt and negative prompt text areas
- Model selection dropdowns
- Form validation patterns
- Submit button and loading states
- Error display components

**Recommended Refactoring**:
```tsx
// Create shared components:
// components/generation/SourceImageInput.tsx
// components/generation/PromptInputGroup.tsx
// components/generation/GenerationFormLayout.tsx

// Usage:
<GenerationFormLayout
  title="Image Generation"
  sourceImage={<SourceImageInput mode={inputMode} onModeChange={setInputMode} />}
  prompts={<PromptInputGroup register={register} errors={errors} promptLabel="Prompt" />}
  options={<ImageOptionsPanel model={model} aspectRatio={aspectRatio} />}
  onSubmit={handleSubmit}
/>
```

### 2. fal_client.py vs image_client.py (HIGH)

**Impact**: HIGH | **Lines**: 46 | **Files**: 2

| Clone | fal_client.py | image_client.py |
|-------|---------------|-----------------|
| 1 | 263-275 | 174-186 |
| 2 | 283-292 | 194-203 |
| 3 | 304-313 | 215-224 |
| 4 | 313-329 | 224-240 |

**Duplicated Elements**:
- HTTP client setup with httpx.AsyncClient
- Retry decorator configuration
- Error handling for Fal API responses
- Status polling and mapping logic
- Request ID extraction

**Recommended Refactoring**:
```python
# app/services/base_fal_client.py
class BaseFalClient:
    """Base class for Fal API clients with shared HTTP and retry logic."""

    def __init__(self, models: dict, api_error_class: type):
        self.models = models
        self.api_error_class = api_error_class

    async def submit_job(self, model: str, payload: dict) -> str:
        """Submit a job to Fal API. Returns request_id."""
        config = self.models[model]
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                config["submit_url"],
                headers=_get_headers(),
                json=payload,
            )
            self._handle_response_error(response, model)
            return response.json().get("request_id")

    async def get_job_status(self, model: str, request_id: str) -> dict:
        """Poll Fal API for job status."""
        # Shared status polling logic
        pass

# Then:
class VideoFalClient(BaseFalClient):
    def __init__(self):
        super().__init__(MODELS, FalAPIError)

class ImageFalClient(BaseFalClient):
    def __init__(self):
        super().__init__(IMAGE_MODELS, ImageAPIError)
```

### 3. rate_limiter.py Internal Duplication (MEDIUM)

**Impact**: MEDIUM | **Lines**: 40 | **Files**: 1

| Location 1 | Location 2 | Lines |
|------------|------------|-------|
| 201-221 | 166-186 | 20 |
| 376-396 | 336-356 | 20 |

**Pattern**: Redis connection and fallback logic duplicated within the same file.

**Recommendation**: Extract Redis connection handling into a helper method.

### 4. retry_manager.py Internal Duplication (MEDIUM)

**Impact**: MEDIUM | **Lines**: 18 | **Files**: 1

| Location 1 | Location 2 |
|------------|------------|
| 379-397 | 325-343 |

**Pattern**: Retry logic patterns repeated.

**Recommendation**: Use a factory function or decorator for consistent retry behavior.

### 5. models.py Field Patterns (LOW)

**Impact**: LOW | **Lines**: 25 | **Files**: 1

| Locations |
|-----------|
| 159-167, 78-86 |
| 265-273, 78-86 |
| 316-325, 265-274 |

**Pattern**: SQLAlchemy model field definitions (id, created_at, updated_at) repeated across models.

**Recommendation**: Create a `TimestampMixin` class:
```python
class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    # ... other fields
```

### 6. schemas.py vs input_validator.py (LOW)

**Impact**: LOW | **Lines**: 18 | **Files**: 2

**Pattern**: Similar validation schemas defined in both files.

**Recommendation**: Consolidate validation logic into schemas.py using Pydantic validators.

## Frontend Duplications (Additional)

### 7. Jobs.tsx vs VideoGeneration.tsx (LOW)
**Lines**: 13 | Import/interface definitions

### 8. Jobs.tsx vs ImageLibrary.tsx (LOW)
**Lines**: 7 | URL handling utilities

### 9. Dashboard.tsx vs VideoGeneration.tsx (LOW)
**Lines**: 14 | API query interfaces

## Refactoring Priority Matrix

| Priority | File(s) | Effort | Impact | ROI |
|----------|---------|--------|--------|-----|
| **1** | ImageGeneration + VideoGeneration | Medium | High | High |
| **2** | fal_client + image_client | Medium | High | High |
| **3** | rate_limiter.py | Low | Medium | Medium |
| **4** | retry_manager.py | Low | Medium | Medium |
| **5** | models.py (mixins) | Low | Low | Medium |

## Action Items

### Immediate (Sprint 1)
1. Extract shared generation form components from ImageGeneration/VideoGeneration
2. Create `BaseFalClient` class for shared API logic

### Short-term (Sprint 2)
3. Add `TimestampMixin` to models
4. Consolidate rate_limiter.py Redis logic
5. Review and merge duplicate validation schemas

### Long-term
6. Consider shared component library for form elements
7. Document abstraction patterns for future development

## Test Strategy

Before refactoring:
1. Ensure existing pytest suite passes
2. Add snapshot tests for ImageGeneration and VideoGeneration forms
3. Create integration tests for fal_client and image_client

After refactoring:
1. Run full test suite
2. Manual testing of form submissions
3. Verify API responses match expected format

---
*Report generated as part of Task 219: Code Duplication Analysis*
