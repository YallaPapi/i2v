# Performance and Scalability Analysis Report

Generated: 2026-01-06

## Executive Summary

The i2v application uses SQLite with good async patterns but has scalability limitations for production deployment. Key bottlenecks include single-file database, in-process workers, and optional Redis caching.

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CURRENT ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Frontend   │───▶│  FastAPI     │───▶│   SQLite     │       │
│  │   (React)    │    │  (Uvicorn)   │    │   (File)     │       │
│  └──────────────┘    └──────┬───────┘    └──────────────┘       │
│                             │                                    │
│                      ┌──────▼───────┐                           │
│                      │   In-Process │                           │
│                      │   Workers    │                           │
│                      └──────┬───────┘                           │
│                             │                                    │
│                      ┌──────▼───────┐    ┌──────────────┐       │
│                      │  Fal.ai API  │    │  Redis       │       │
│                      │  (External)  │    │  (Optional)  │       │
│                      └──────────────┘    └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Performance Analysis

### Database (SQLite)

**Current Configuration**:
```python
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for async
)
```

**Bottlenecks**:
| Issue | Impact | Severity |
|-------|--------|----------|
| Single-file database | No concurrent writes | HIGH |
| No connection pooling | Limited connections | MEDIUM |
| No read replicas | All queries hit same file | MEDIUM |

**Query Analysis**:
- 44 query operations in `pipelines.py`
- Proper indexing on status, created_at, favorite, hidden
- Some N+1 potential with relationships

**Recommendations**:
```python
# PostgreSQL migration
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost/i2v"
)

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
)
```

### Async/Concurrency

**Good Patterns Found**:

1. **Concurrent Job Processing**:
```python
# worker.py - Good: Uses asyncio.gather
results = await asyncio.gather(*tasks)
```

2. **Configurable Concurrency**:
```python
# config.py
max_concurrent_submits: int = 20
max_concurrent_polls: int = 20
```

3. **Semaphore Usage**:
```python
# pipelines.py - Good: Limits concurrent operations
semaphore = asyncio.Semaphore(20)
```

**Bottlenecks**:
| Issue | Impact | Severity |
|-------|--------|----------|
| In-process workers | Can't scale independently | HIGH |
| Synchronous DB session | Blocks event loop | MEDIUM |
| No job queue | Lost jobs on crash | HIGH |

### Caching Strategy

**Current Implementation**:
```python
# services/cache.py
async def cache_get(key: str) -> Optional[str]:
    redis = await get_redis()
    if redis is None:
        return None  # Graceful degradation
    return await redis.get(key)
```

**Assessment**:
| Feature | Status |
|---------|--------|
| Redis integration | ✅ Optional |
| Graceful degradation | ✅ Falls back to no-cache |
| Pipeline list caching | ✅ Implemented |
| Cache invalidation | ✅ On mutations |
| TTL configuration | ✅ 60 seconds default |

**Missing Caching**:
- Individual pipeline responses
- Prompt enhancement results (has its own cache)
- Cost calculations

### API Response Times

**Estimated Response Times** (without profiling):

| Endpoint | Complexity | Estimated P95 |
|----------|------------|---------------|
| GET /health | O(1) | <10ms |
| GET /pipelines | O(n) + cache | 50-200ms |
| GET /pipelines/{id} | O(1) | 20-50ms |
| POST /pipelines | O(1) | 50-100ms |
| POST /execute | O(steps) | 100-500ms |

### External API Calls

**Fal.ai Integration**:
```python
# Rate limiting in place
fal_rate_limiter = SlidingWindowRateLimiter(max_per_second=10)
openai_rate_limiter = SlidingWindowRateLimiter(max_per_minute=60)
```

**Timeouts**:
```python
async with httpx.AsyncClient(timeout=60.0) as client:
    # 60 second timeout for job submission
```

## Scalability Assessment

### Current Limits

| Resource | Current | Recommended |
|----------|---------|-------------|
| Max concurrent requests | ~100 (Uvicorn) | 1000+ |
| Database connections | 1 (SQLite) | 20-50 (PostgreSQL) |
| Worker processes | 1 (in-process) | 5-10 (separate) |
| Cache capacity | Optional | Required |

### Horizontal Scaling Blockers

1. **SQLite File Lock**: Only one writer at a time
2. **In-Memory State**: Singletons not shared across processes
3. **File-based Checkpoints**: Local filesystem dependency
4. **In-process Workers**: Can't scale API and workers separately

## Recommendations

### Immediate (Production-Ready)

1. **Add PostgreSQL**:
```yaml
# docker-compose.yml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: i2v
      POSTGRES_USER: i2v
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

2. **Enable Redis**:
```yaml
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

3. **Configure Connection Pool**:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)
```

### Short-term (Scalable)

4. **Separate Workers with Celery**:
```python
# tasks/video_tasks.py
from celery import Celery

app = Celery('i2v', broker='redis://localhost:6379/0')

@app.task
def submit_video_job(job_id: int, image_url: str, ...):
    ...
```

5. **Add Health Checks**:
```python
@app.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    # Check DB connection
    db.execute(text("SELECT 1"))
    # Check Redis
    redis = await get_redis()
    if redis:
        await redis.ping()
    return {"status": "ready"}
```

### Long-term (Enterprise)

6. **Kubernetes Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: i2v-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "2000m"
            memory: "2Gi"
```

7. **Add Metrics**:
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests')
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Request latency')
```

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  RECOMMENDED ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │   Frontend   │                                               │
│  │   (CDN)      │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│  ┌──────▼───────┐    ┌──────────────┐                          │
│  │ Load Balancer│───▶│   Redis      │                          │
│  └──────┬───────┘    │   (Cache)    │                          │
│         │            └──────────────┘                          │
│  ┌──────▼───────┐                                               │
│  │  FastAPI x3  │───┐                                          │
│  │  (Stateless) │   │                                          │
│  └──────────────┘   │    ┌──────────────┐                      │
│                     ├───▶│  PostgreSQL  │                      │
│  ┌──────────────┐   │    │   (Primary)  │                      │
│  │ Celery x5    │───┘    └──────────────┘                      │
│  │  (Workers)   │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│  ┌──────▼───────┐    ┌──────────────┐                          │
│  │    Redis     │    │  Fal.ai API  │                          │
│  │   (Queue)    │    │  (External)  │                          │
│  └──────────────┘    └──────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Load Testing Recommendations

```python
# locustfile.py
from locust import HttpUser, task, between

class I2VUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def list_pipelines(self):
        self.client.get("/api/pipelines?limit=10")

    @task(5)
    def get_pipeline(self):
        self.client.get("/api/pipelines/1")

    @task(1)
    def create_pipeline(self):
        self.client.post("/api/pipelines", json={...})
```

**Target Metrics**:
| Metric | Target |
|--------|--------|
| P95 Latency | <500ms |
| P99 Latency | <1000ms |
| Throughput | 100 req/s |
| Error Rate | <0.1% |

---
*Report generated as part of Task 225: Performance and Scalability Analysis*
