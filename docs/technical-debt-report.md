# Technical Debt Estimation Report

Generated: 2026-01-06

## Executive Summary

Technical debt analysis identified **23 debt items** across the codebase, with an estimated remediation effort of **40-60 hours**. Priority should be given to extracting shared Fal client code and splitting the large pipelines router.

## Debt Quadrant Analysis

```
                    HIGH IMPACT
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    │  QUICK WINS       │  STRATEGIC        │
    │  (Do First)       │  (Plan & Execute) │
    │                   │                   │
    │  • MD5 → SHA256   │  • Split router   │
    │  • Add noqa       │  • Extract base   │
    │  • Fix bare       │    client         │
    │    except         │  • PostgreSQL     │
    │                   │    migration      │
    │                   │                   │
LOW ├───────────────────┼───────────────────┤ HIGH
EFF │                   │                   │ EFFORT
ORT │  LOW PRIORITY     │  AVOID            │
    │  (Backlog)        │  (Not Worth It)   │
    │                   │                   │
    │  • Add type hints │  • Full rewrite   │
    │  • Doc strings    │  • Change ORM     │
    │  • Comments       │                   │
    │                   │                   │
    └───────────────────┼───────────────────┘
                        │
                    LOW IMPACT
```

## Debt Inventory

### Code Duplication (from Task 219)

| ID | Location | Lines | Effort | Priority |
|----|----------|-------|--------|----------|
| D1 | fal_client ↔ image_client | 46 | 4h | HIGH |
| D2 | ImageGeneration ↔ VideoGeneration | 170 | 6h | HIGH |
| D3 | models.py timestamps | 25 | 1h | MEDIUM |
| D4 | rate_limiter.py internal | 40 | 2h | LOW |

**Total Duplication Debt**: ~13h

### Complexity (from Task 220)

| ID | Function | CC | Effort | Priority |
|----|----------|-----|--------|----------|
| C1 | get_image_result | 34 | 4h | HIGH |
| C2 | get_job_result | 18 | 3h | HIGH |
| C3 | list_pipelines | 14 | 2h | MEDIUM |
| C4 | _fallback_enhance | 15 | 2h | MEDIUM |
| C5 | Functions with >5 args | 17 | 4h | MEDIUM |

**Total Complexity Debt**: ~15h

### Security (from Task 221)

| ID | Issue | Severity | Effort | Priority |
|----|-------|----------|--------|----------|
| S1 | Missing API auth | HIGH | 4h | HIGH |
| S2 | CORS allow_origins=* | HIGH | 0.5h | HIGH |
| S3 | SQL string formatting | MEDIUM | 1h | MEDIUM |
| S4 | MD5 for cache keys | MEDIUM | 0.5h | LOW |

**Total Security Debt**: ~6h

### Architecture (from Task 224)

| ID | Issue | Impact | Effort | Priority |
|----|-------|--------|--------|----------|
| A1 | pipelines.py 1600+ lines | HIGH | 6h | HIGH |
| A2 | In-process workers | HIGH | 8h | MEDIUM |
| A3 | SQLite single file | HIGH | 4h | MEDIUM |
| A4 | No service layer | MEDIUM | 4h | LOW |

**Total Architecture Debt**: ~22h

### Code Quality

| ID | Issue | Count | Effort | Priority |
|----|-------|-------|--------|----------|
| Q1 | Hardcoded URLs | 56 | 2h | LOW |
| Q2 | Missing type hints | ~100 | 4h | LOW |
| Q3 | Try-except-pass | 11 | 1h | LOW |
| Q4 | No TODO/FIXME found | 0 | 0h | N/A |

**Total Quality Debt**: ~7h

## Debt by File

| File | Debt Score | Items | Effort |
|------|------------|-------|--------|
| pipelines.py | HIGH | 4 | 10h |
| fal_client.py | MEDIUM | 3 | 5h |
| image_client.py | HIGH | 4 | 7h |
| worker.py | MEDIUM | 2 | 4h |
| ImageGeneration.tsx | MEDIUM | 1 | 3h |
| VideoGeneration.tsx | MEDIUM | 1 | 3h |

## Prioritized Remediation Plan

### Phase 1: Quick Wins (1-2 days)

**Estimated Effort**: 6h

1. **Fix CORS configuration** (S2) - 0.5h
   ```python
   ALLOWED_ORIGINS = [
       "http://localhost:3000",
       os.getenv("FRONTEND_URL", ""),
   ]
   ```

2. **Add MD5 usedforsecurity flag** (S4) - 0.5h
   ```python
   hashlib.md5(data, usedforsecurity=False)
   ```

3. **Convert SQL to parameterized** (S3) - 1h

4. **Add type hints to public APIs** - 2h

5. **Replace bare except with Exception** - 1h (already done in Task 218)

### Phase 2: Strategic Refactoring (1-2 weeks)

**Estimated Effort**: 25h

1. **Extract BaseFalClient** (D1) - 4h
   - Create abstract base class
   - Refactor fal_client.py
   - Refactor image_client.py
   - Update imports

2. **Split pipelines.py router** (A1) - 6h
   - Extract CRUD operations
   - Extract execution endpoints
   - Extract bulk operations
   - Update main.py

3. **Refactor get_image_result** (C1) - 4h
   - Extract model-specific parsers
   - Implement parser factory

4. **Extract frontend components** (D2) - 6h
   - Create SourceImageInput
   - Create PromptInputGroup
   - Refactor pages

5. **Add API authentication** (S1) - 4h
   - Implement API key middleware
   - Add to config

### Phase 3: Infrastructure (2-4 weeks)

**Estimated Effort**: 16h

1. **PostgreSQL migration** (A3) - 4h
   - Add Alembic
   - Create migration scripts
   - Update connection config

2. **Celery workers** (A2) - 8h
   - Set up Celery
   - Create task definitions
   - Update worker.py

3. **Centralize hardcoded URLs** (Q1) - 2h
   - Move to config
   - Add environment variables

4. **Add service layer** (A4) - 4h
   - Create PipelineService
   - Refactor router dependencies

## Technical Debt Metrics

### Current State

| Metric | Value | Target |
|--------|-------|--------|
| Code duplication | 2.79% | <2% |
| Max cyclomatic complexity | 34 | <15 |
| Files >500 lines | 2 | 0 |
| Missing type hints | ~40% | <10% |
| Test coverage | Unknown | >80% |

### Debt Interest

If unaddressed, technical debt accumulates "interest":

| Debt Item | Monthly Interest |
|-----------|------------------|
| Duplicated code | +2h maintenance |
| High complexity | +1h debugging |
| Missing tests | +3h bug fixes |
| No auth | Security incident risk |

## ROI Analysis

| Investment | Effort | Return |
|------------|--------|--------|
| Extract BaseFalClient | 4h | -2h/month maintenance |
| Split pipelines.py | 6h | -3h/month onboarding |
| Add PostgreSQL | 4h | Enable scaling |
| Add auth | 4h | Security compliance |

**Break-even**: ~3-4 months

## Recommendations

### Do Now
1. Fix CORS (30 min, high security impact)
2. Parameterize SQL (1h, security fix)

### Plan This Sprint
3. Extract BaseFalClient (reduces duplication)
4. Split pipelines.py (improves maintainability)

### Backlog
5. PostgreSQL migration
6. Celery workers
7. Full type hints coverage

### Technical Debt Budget

Recommend allocating **20% of each sprint** to debt reduction:
- 2-day sprint: 0.5 days debt work
- 1-week sprint: 1 day debt work

---
*Report generated as part of Task 226: Technical Debt Estimation*
