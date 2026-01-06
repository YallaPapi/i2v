# Security Vulnerability Analysis Report

Generated: 2026-01-06

## Executive Summary

Security analysis of the i2v codebase identified **14 issues** across different severity levels. The most critical findings are:

1. **No API authentication** - All endpoints are publicly accessible
2. **Permissive CORS** - `allow_origins=["*"]` allows any origin
3. **Potential SQL injection** - String-based query construction (low risk)
4. **Weak hash for caching** - MD5 used for cache keys

## Scan Results Summary

### Bandit (Static Analysis)
| Severity | Count | Status |
|----------|-------|--------|
| High | 1 | Review needed |
| Medium | 2 | Review needed |
| Low | 11 | Acceptable |

### Safety (Dependencies)
| Package | Vulnerability | Severity |
|---------|---------------|----------|
| py 1.11.0 | CVE-2022-42969 (ReDoS) | Medium |
| capstone 5.0.6 | PVE-2024-73501 (Buffer overflow) | Medium |

## Critical Findings

### 1. Missing API Authentication (HIGH)

**Risk**: Any client can access all API endpoints without authentication.

**Location**: All routes in `app/main.py` and `app/routers/pipelines.py`

**Current State**:
```python
@app.post("/api/jobs")
async def create_job(job: JobCreate):
    # No authentication check
    ...
```

**Recommendation**:
```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@app.post("/api/jobs")
async def create_job(
    job: JobCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    verify_api_key(credentials.credentials)
    ...
```

### 2. Permissive CORS Configuration (HIGH)

**Risk**: Cross-origin requests from any domain are allowed, enabling CSRF attacks.

**Location**: `app/main.py:140`

**Current State**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # UNSAFE
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Recommendation**:
```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    os.getenv("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 3. SQL Injection Risk (MEDIUM)

**Risk**: String-based SQL query construction could be exploited if input sanitization changes.

**Location**: `app/routers/pipelines.py:199-207`

**Current State**:
```python
placeholders = ",".join([str(pid) for pid in pipeline_ids])
output_count_sql = f"""
    SELECT pipeline_id, ...
    WHERE pipeline_id IN ({placeholders})
"""
```

**Mitigation**: The `pipeline_ids` are integers from the database, so current risk is LOW. However, parameterized queries should be used:

**Recommendation**:
```python
from sqlalchemy import bindparam

stmt = text("""
    SELECT pipeline_id, ...
    WHERE pipeline_id IN :ids
""").bindparams(bindparam("ids", expanding=True))
result = db.execute(stmt, {"ids": pipeline_ids})
```

### 4. Weak Hash Algorithm (MEDIUM)

**Risk**: MD5 is cryptographically weak, though used here only for caching.

**Location**: `app/services/prompt_enhancer.py:61`

**Current State**:
```python
return hashlib.md5(key_data.encode()).hexdigest()
```

**Recommendation**:
```python
# Mark as non-security use
return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

# Or use SHA256 for better practice
return hashlib.sha256(key_data.encode()).hexdigest()[:32]
```

## Medium Findings

### 5. No Rate Limiting on API Endpoints

**Risk**: API abuse through unlimited requests.

**Current State**: Rate limiting exists internally for Fal API calls but not for the i2v API itself.

**Recommendation**: Add slowapi rate limiting:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/jobs")
@limiter.limit("10/minute")
async def create_job(request: Request, job: JobCreate):
    ...
```

### 6. File Upload Security

**Location**: `app/main.py:315`

**Issues**:
- No explicit file size limit (relies on FastAPI defaults)
- No MIME type validation (only extension check)

**Current State**:
```python
suffix = Path(file.filename or "").suffix.lower()
if suffix not in SUPPORTED_FORMATS:
    raise HTTPException(...)
```

**Recommendation**:
```python
import magic

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # Validate MIME type
    mime = magic.from_buffer(content[:2048], mime=True)
    if mime not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
```

### 7. Download Proxy Domain Validation

**Location**: `app/routers/pipelines.py:299-308`

**Current State**: Good - validates allowed domains
```python
allowed_domains = ["fal.media", "fal.ai", "r2.dev", "r2.cloudflarestorage.com"]
if not any(domain in parsed.netloc for domain in allowed_domains):
    raise HTTPException(status_code=400, detail="URL not from allowed domain")
```

**Status**: ACCEPTABLE - domain validation is implemented.

## Low Severity Findings

### 8. Try-Except-Pass Patterns (11 occurrences)

**Risk**: Silent exception handling may hide errors.

**Locations**:
- `app/main.py:340, 353` - Temp file cleanup
- `app/services/r2_cache.py:82, 147` - Object existence check
- `app/services/file_lock.py:156, 173, 219, 235` - Lock cleanup
- `app/services/checkpoint_manager.py:436, 499` - JSON parsing

**Assessment**: Most are acceptable for cleanup code. Add logging for debugging:
```python
except Exception as e:
    logger.debug("Cleanup failed (non-critical)", error=str(e))
    pass
```

### 9. Pseudo-Random Number Generator

**Location**: `app/services/retry_manager.py:128`

**Current State**:
```python
delay += random.uniform(-jitter_amount, jitter_amount)
```

**Assessment**: ACCEPTABLE - Used for jitter timing, not security purposes.

## Dependency Vulnerabilities

### py 1.11.0 - CVE-2022-42969

**Severity**: Medium (disputed)
**Issue**: ReDoS via Subversion repository info
**Impact**: Low - likely a transitive dependency not directly used
**Recommendation**: Update if direct dependency, otherwise monitor

### capstone 5.0.6 - PVE-2024-73501

**Severity**: Medium
**Issue**: Buffer overflow vulnerability
**Impact**: Low - reverse engineering library, not used in web context
**Recommendation**: Update to 6.0.0+ when available

## Security Checklist

| Category | Status | Priority |
|----------|--------|----------|
| API Authentication | Missing | **HIGH** |
| CORS Configuration | Permissive | **HIGH** |
| SQL Parameterization | Partial | MEDIUM |
| Rate Limiting (API) | Missing | MEDIUM |
| File Upload Validation | Basic | MEDIUM |
| Error Handling | Acceptable | LOW |
| Dependency Updates | 2 vulnerable | LOW |

## Recommendations

### Immediate Actions
1. Add API key authentication for production deployment
2. Restrict CORS to specific origins
3. Add explicit file size limits

### Short-term Actions
4. Implement slowapi rate limiting on endpoints
5. Add MD5 `usedforsecurity=False` flag
6. Convert SQL string formatting to parameterized queries

### Long-term Actions
7. Add MIME type validation for uploads
8. Implement proper logging for security events
9. Set up dependency vulnerability scanning in CI
10. Consider OAuth2/JWT for multi-user scenarios

## Production Deployment Considerations

Before deploying to production:

1. **Environment Variables**:
   ```bash
   FRONTEND_URL=https://your-domain.com
   API_KEY_SECRET=<generated-secret>
   ```

2. **Reverse Proxy** (nginx/Caddy):
   - TLS termination
   - Additional rate limiting
   - Request size limits

3. **Monitoring**:
   - Failed authentication attempts
   - Rate limit violations
   - Error patterns

---
*Report generated as part of Task 221: Security Vulnerability Analysis*
