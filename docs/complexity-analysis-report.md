# Code Complexity Analysis Report

Generated: 2026-01-06

## Executive Summary

Analysis of the i2v codebase using ruff and radon identified **49 complexity violations** and several functions requiring refactoring. The most critical finding is `get_image_result()` with a cyclomatic complexity of 34 (Grade E - very high risk).

## Tools & Thresholds

| Tool | Metric | Threshold | Description |
|------|--------|-----------|-------------|
| ruff C901 | Cyclomatic Complexity | >10 | Too many decision paths |
| ruff PLR0912 | Branches | >12 | Too many if/elif/else branches |
| ruff PLR0913 | Arguments | >5 | Too many function parameters |
| ruff PLR0915 | Statements | >50 | Too many lines in function |
| radon CC | Cyclomatic Complexity | A-F scale | A=1-5, B=6-10, C=11-20, D=21-30, E=31-40, F=41+ |

## Maintainability Index

| File | Grade | Status |
|------|-------|--------|
| app/routers/pipelines.py | **C** | Needs attention |
| All other files | **A** | Good |

## Critical Complexity Issues (Grade C-E)

### 1. get_image_result() - Grade E (CC=34)
**File**: `app/image_client.py:203`

| Metric | Value | Threshold |
|--------|-------|-----------|
| Cyclomatic Complexity | 34 | >10 |
| Branches | 24 | >12 |
| Statements | 59 | >50 |

**Root Cause**: Multiple nested conditionals handling different image models (flux-kontext, flux-redux, bria, recraft, etc.) each with different response structures.

**Refactoring Strategy**:
```python
# Create model-specific result parsers
class ResultParser(Protocol):
    def parse(self, data: dict) -> dict: ...

class FluxKontextParser(ResultParser):
    def parse(self, data: dict) -> dict:
        images = data.get("images", [])
        return {"image_urls": [img.get("url") for img in images]}

class FluxReduxParser(ResultParser):
    def parse(self, data: dict) -> dict:
        images = data.get("images", [])
        return {"image_urls": [img.get("url") for img in images]}

# Factory pattern
RESULT_PARSERS: dict[str, ResultParser] = {
    "flux-kontext": FluxKontextParser(),
    "flux-redux": FluxReduxParser(),
    # ...
}

async def get_image_result(model: ImageModelType, request_id: str) -> dict:
    # ... HTTP logic (unchanged)
    parser = RESULT_PARSERS.get(model, DefaultParser())
    return parser.parse(result_data)
```

### 2. get_job_result() - Grade C (CC=18)
**File**: `app/fal_client.py:292`

| Metric | Value | Threshold |
|--------|-------|-----------|
| Cyclomatic Complexity | 18 | >10 |
| Branches | 13 | >12 |

**Root Cause**: Similar pattern to `get_image_result()` - model-specific response handling.

**Refactoring Strategy**: Extract video model-specific parsing into separate functions or use the same parser pattern.

### 3. _determine_type() - Grade C (CC=16)
**File**: `app/services/error_classifier.py:151`

**Root Cause**: Long chain of error type detection conditionals.

**Refactoring Strategy**: Use a list of (pattern, error_type) tuples and iterate:
```python
ERROR_PATTERNS = [
    (r"rate.?limit", ErrorType.RATE_LIMIT),
    (r"timeout", ErrorType.TIMEOUT),
    (r"connection", ErrorType.CONNECTION),
    # ...
]

def _determine_type(self, message: str) -> ErrorType:
    message_lower = message.lower()
    for pattern, error_type in ERROR_PATTERNS:
        if re.search(pattern, message_lower):
            return error_type
    return ErrorType.UNKNOWN
```

### 4. _fallback_enhance() - Grade C (CC=15)
**File**: `app/services/prompt_enhancer.py:275`

| Metric | Value | Threshold |
|--------|-------|-----------|
| Cyclomatic Complexity | 15 | >10 |
| Branches | 15 | >12 |
| Arguments | 7 | >5 |

**Root Cause**: Multiple enhancement strategies based on target type and conditions.

**Refactoring Strategy**: Extract enhancement strategies into separate methods.

### 5. list_pipelines() - Grade C (CC=14)
**File**: `app/routers/pipelines.py:103`

| Metric | Value | Threshold |
|--------|-------|-----------|
| Cyclomatic Complexity | 14 | >10 |
| Branches | 13 | >12 |
| Arguments | 7 | >5 |
| Statements | 51 | >50 |

**Root Cause**: Complex filtering logic with many optional parameters.

**Refactoring Strategy**: Extract filter building into a separate function:
```python
def build_pipeline_query(
    db: Session,
    status: str | None,
    tag: str | None,
    demo_mode: bool,
    show_hidden: bool,
) -> Query:
    """Build SQLAlchemy query with filters."""
    query = db.query(Pipeline)
    if status:
        query = query.filter(Pipeline.status == status)
    if tag:
        query = query.filter(Pipeline.tags.contains(tag))
    # ... etc
    return query

async def list_pipelines(...):
    query = build_pipeline_query(db, status, tag, demo_mode, show_hidden)
    # ... pagination and response
```

## Too Many Arguments Issues (17 occurrences)

Functions with more than 5 parameters should consider:

| File | Function | Args | Recommendation |
|------|----------|------|----------------|
| fal_client.py:132 | _build_payload | 7 | Use dataclass/Pydantic model |
| fal_client.py:230 | submit_job | 7 | Use dataclass/Pydantic model |
| image_client.py:69 | _build_image_payload | 7 | Use dataclass/Pydantic model |
| image_client.py:152 | submit_image_job | 7 | Use dataclass/Pydantic model |
| worker.py:93 | submit_single_job | 7 | Use JobConfig dataclass |
| worker.py:284 | submit_single_image_job | 8 | Use ImageJobConfig dataclass |
| prompt_enhancer.py | Multiple methods | 6-7 | Use EnhanceConfig dataclass |

**Example Refactoring**:
```python
@dataclass
class JobSubmitConfig:
    model: str
    image_url: str
    prompt: str
    negative_prompt: str = ""
    duration_sec: int = 5
    resolution: str = "720p"
    enable_audio: bool = False

async def submit_job(config: JobSubmitConfig) -> str:
    """Submit job using config object."""
    payload = _build_payload(config)
    # ...
```

## Too Many Statements (6 occurrences)

| File | Function | Statements | Threshold |
|------|----------|------------|-----------|
| image_client.py:203 | get_image_result | 59 | 50 |
| job_orchestrator.py:144 | submit_job | 70 | 50 |
| pipeline_executor.py:38 | execute_pipeline | 54 | 50 |
| thumbnail.py:44 | generate_thumbnail | 55 | 50 |
| bulk_generate.py:156 | main | 61 | 50 |
| pipelines.py:103 | list_pipelines | 51 | 50 |

**Recommendation**: Extract logical blocks into helper functions.

## Complexity Distribution

```
Complexity Grade Distribution:
├── Grade A (1-5):   ~85% of functions
├── Grade B (6-10):  ~10% of functions
├── Grade C (11-20): ~4% of functions
├── Grade D (21-30): 0% of functions
└── Grade E (31-40): 1 function (get_image_result)
```

## Refactoring Priority

| Priority | Function | Current CC | Target CC | Effort |
|----------|----------|------------|-----------|--------|
| 1 | get_image_result | 34 (E) | <10 (A) | High |
| 2 | get_job_result | 18 (C) | <10 (A) | Medium |
| 3 | list_pipelines | 14 (C) | <10 (A) | Low |
| 4 | _determine_type | 16 (C) | <10 (A) | Low |
| 5 | _fallback_enhance | 15 (C) | <10 (A) | Medium |

## Recommended Actions

### Immediate
1. Add `# noqa: C901` comments to acknowledge known complexity (temporary)
2. Create GitHub issues for high-priority refactors

### Short-term
1. Implement parser pattern for `get_image_result()` and `get_job_result()`
2. Extract query building from `list_pipelines()`
3. Convert multi-argument functions to use config dataclasses

### Long-term
1. Establish complexity budgets in CI (radon --fail-under=B)
2. Add pre-commit hook for complexity checking
3. Document patterns for handling model-specific logic

## Testing Considerations

Before refactoring:
1. Ensure test coverage for affected functions
2. Add integration tests for API responses
3. Create snapshot tests for complex outputs

After refactoring:
1. Verify all existing tests pass
2. Confirm API responses unchanged
3. Performance benchmark critical paths

---
*Report generated as part of Task 220: Code Complexity Analysis*
