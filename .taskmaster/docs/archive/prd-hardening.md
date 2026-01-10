# Production Hardening Playbook

A methodology for transforming prototypes into production-grade systems, extracted from building reliable automation systems.

---

## Table of Contents

1. [Philosophy: The 8 Principles](#philosophy-the-8-principles)
2. [Diagnostic Checklist](#diagnostic-checklist)
3. [Hardening Prompts](#hardening-prompts)
4. [Application Example: i2v Project](#application-example-i2v-project)

---

## Philosophy: The 8 Principles

These principles emerged from building autonomous systems that run 24/7 without human intervention. Each principle addresses a specific failure mode discovered through production incidents.

### Principle 1: Separation of Concerns

**What**: Each module has ONE job. Workers don't coordinate. Coordinators don't execute. Clients don't parse.

**Why**: When a 500-line file handles execution, retries, logging, and state management, a bug in logging can crash execution. Isolation contains failures.

**Pattern**:
```
Orchestrator (coordination)
    ├── Worker (execution)
    ├── StateManager (persistence)
    ├── RetryManager (resilience)
    └── FlowLogger (observability)
```

**Anti-pattern**: God classes that do everything. "Utils" files with 50 unrelated functions.

---

### Principle 2: Error Classification

**What**: Not all errors are equal. Classify them and handle accordingly.

**Why**: Retrying an "invalid API key" error 100 times wastes resources. Failing immediately on a network blip loses work unnecessarily.

**Classification**:
| Type | Examples | Action |
|------|----------|--------|
| NETWORK | Timeout, connection refused | Retry with backoff |
| RATE_LIMIT | HTTP 429, quota exceeded | Retry with longer backoff |
| INVALID_INPUT | HTTP 400, validation error | Fail immediately |
| TRANSIENT | HTTP 500-503 | Retry 2-3x then fail |
| PERMANENT | HTTP 401/403, suspended account | Fail, flag for review |

**Implementation**:
```python
class ErrorClassifier:
    def classify(self, error: Exception) -> ErrorType:
        if isinstance(error, TimeoutError):
            return ErrorType.NETWORK
        if isinstance(error, HTTPError):
            if error.status_code == 429:
                return ErrorType.RATE_LIMIT
            if error.status_code == 400:
                return ErrorType.INVALID_INPUT
        return ErrorType.UNKNOWN
```

---

### Principle 3: State Persistence

**What**: Every state change is written to disk before proceeding. If it's not persisted, it didn't happen.

**Why**: Processes crash. Servers reboot. Memory is ephemeral. The only reliable state is on disk.

**Pattern**: Write-Ahead Logging
```python
def process_job(job):
    checkpoint.write(job.id, status="started")

    result = execute(job)

    checkpoint.write(job.id, status="completed", result=result)
    return result
```

**Recovery**:
```python
def recover():
    for entry in checkpoint.read_incomplete():
        if entry.status == "started":
            # Crashed mid-execution, retry
            requeue(entry.job_id)
```

**Anti-pattern**: In-memory state only. Database writes without checkpoints.

---

### Principle 4: File-Based Locking

**What**: Use file locks to prevent concurrent access to shared resources.

**Why**: Database locks are unreliable (especially SQLite). Distributed locks need infrastructure. File locks are simple, portable, and work.

**Pattern**:
```python
import portalocker

class FileLock:
    def __init__(self, path: str):
        self.path = path
        self.file = None

    def __enter__(self):
        self.file = open(self.path, 'w')
        portalocker.lock(self.file, portalocker.LOCK_EX)
        return self

    def __exit__(self, *args):
        portalocker.unlock(self.file)
        self.file.close()

# Usage
with FileLock("jobs.lock"):
    jobs = claim_pending_jobs()
```

**When to use**:
- Job claiming in workers
- Progress file updates
- Any shared mutable state

---

### Principle 5: Defense in Depth

**What**: Validate at every layer. Never trust upstream.

**Why**: Bugs happen. APIs change. Users do unexpected things. Multiple validation layers catch what single layers miss.

**Pattern**:
```
Request → Router Validation → Service Validation → Execution
              ↓                      ↓
         "Is it JSON?"        "Does account exist?"
         "Required fields?"    "Has quota remaining?"
```

**Example**:
```python
# Router layer - structure validation
@router.post("/jobs")
def create_job(request: JobRequest):  # Pydantic validates structure
    return service.create_job(request)

# Service layer - business validation
class JobService:
    def create_job(self, request: JobRequest):
        # Re-validate even though router checked
        if not self.account_repo.exists(request.account_id):
            raise ValidationError("Account not found")
        if not self.quota_manager.has_quota(request.account_id):
            raise ValidationError("Quota exceeded")
        # Now safe to proceed
```

**Anti-pattern**: "The frontend validates this" or "We checked this upstream"

---

### Principle 6: Retry with Exponential Backoff

**What**: Failed operations are retried with increasing delays, up to a maximum.

**Why**: Transient failures are common. Immediate retries often fail again. Backing off gives systems time to recover.

**Formula**: `delay = min(base * (multiplier ^ attempt) + jitter, max_delay)`

**Implementation**:
```python
async def retry_with_backoff(
    operation,
    max_attempts=3,
    base_delay=1.0,
    multiplier=2.0,
    max_delay=300.0
):
    for attempt in range(max_attempts):
        try:
            return await operation()
        except RetryableError as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(base_delay * (multiplier ** attempt), max_delay)
            delay += random.uniform(0, delay * 0.1)  # Jitter
            await asyncio.sleep(delay)
```

**Jitter**: Random variation prevents thundering herd when many clients retry simultaneously.

---

### Principle 7: Flow Logging

**What**: Every operation produces a step-by-step trace in JSONL format.

**Why**: When something fails at 3 AM, you need to know exactly what happened. Regular logs are scattered. Flow logs are coherent narratives.

**Format**:
```json
{"ts": "2026-01-04T10:00:00Z", "flow_id": "job-123", "step": 0, "action": "start", "status": "pending"}
{"ts": "2026-01-04T10:00:01Z", "flow_id": "job-123", "step": 1, "action": "submit", "status": "submitted", "request_id": "req-456"}
{"ts": "2026-01-04T10:00:30Z", "flow_id": "job-123", "step": 2, "action": "poll", "status": "running", "progress": 45}
{"ts": "2026-01-04T10:01:00Z", "flow_id": "job-123", "step": 3, "action": "complete", "status": "success", "output_url": "..."}
```

**Implementation**:
```python
class FlowLogger:
    def __init__(self, flow_id: str, output_dir: str = "flow_logs"):
        self.flow_id = flow_id
        self.step = 0
        self.file = open(f"{output_dir}/{flow_id}.jsonl", "a")

    def log(self, action: str, status: str, **context):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "flow_id": self.flow_id,
            "step": self.step,
            "action": action,
            "status": status,
            **context
        }
        self.file.write(json.dumps(entry) + "\n")
        self.file.flush()
        self.step += 1
```

**Debugging**: `cat flow_logs/job-123.jsonl | jq .` shows the complete operation history.

---

### Principle 8: Cooldown and Rate Limiting

**What**: Track failures per entity. Increase backoff with consecutive failures. Respect rate limits.

**Why**: Hammering a failing endpoint wastes resources and can get you blocked. Respecting limits maintains good standing with APIs.

**Cooldown Schedule**:
```python
COOLDOWN_SECONDS = [60, 300, 900, 3600, 86400]  # 1m, 5m, 15m, 1h, 1d

def get_cooldown(consecutive_failures: int) -> int:
    index = min(consecutive_failures - 1, len(COOLDOWN_SECONDS) - 1)
    return COOLDOWN_SECONDS[index]
```

**Rate Limiting Pattern**:
```python
class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.max = max_per_minute
        self.timestamps = []

    async def acquire(self):
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 60]

        if len(self.timestamps) >= self.max:
            wait = 60 - (now - self.timestamps[0])
            await asyncio.sleep(wait)

        self.timestamps.append(time.time())
```

---

## Diagnostic Checklist

Use this checklist to audit any codebase. Each "No" indicates a hardening opportunity.

### Architecture
- [ ] Is each module focused on a single responsibility?
- [ ] Are there clear boundaries between layers (API, Service, Data)?
- [ ] Is the largest file under 300 lines?
- [ ] Are design patterns used appropriately (Factory, Strategy, Adapter)?

### Error Handling
- [ ] Are errors classified by type (network, rate limit, invalid input)?
- [ ] Do retryable errors get retried? Do permanent errors fail fast?
- [ ] Is there a centralized retry manager?
- [ ] Are error messages actionable (include context, suggest fixes)?

### State Management
- [ ] Is critical state persisted to disk, not just memory?
- [ ] Can operations resume after a crash?
- [ ] Is there a checkpoint/progress file for long-running operations?
- [ ] Is state recovery tested?

### Concurrency
- [ ] Are shared resources protected by locks?
- [ ] Can multiple workers run without claiming the same work?
- [ ] Are race conditions addressed (check-then-act patterns)?
- [ ] Is there deadlock prevention?

### Reliability
- [ ] Is there retry with exponential backoff?
- [ ] Is there jitter to prevent thundering herd?
- [ ] Are there circuit breakers for failing dependencies?
- [ ] Is there graceful degradation?

### Observability
- [ ] Are operations traceable end-to-end?
- [ ] Is there flow logging (JSONL or similar)?
- [ ] Can you diagnose a failure from logs alone?
- [ ] Are metrics collected (success rate, latency, error rate)?

### Validation
- [ ] Is input validated at the API layer?
- [ ] Is input re-validated at the service layer?
- [ ] Are file uploads size-limited?
- [ ] Are URLs validated before fetching?

### Rate Limiting
- [ ] Is there per-entity cooldown tracking?
- [ ] Are API rate limits respected?
- [ ] Is there backpressure when overwhelmed?

---

## Hardening Prompts

These prompts are designed to be given to an AI coding assistant (Claude, Cursor, etc.) to systematically harden a codebase. Customize the placeholders for your project.

### Prompt 1: Architecture Audit

```
Analyze the architecture of [PROJECT_PATH].

Map out:
1. Entry points (main files, CLI commands, API routes)
2. Core business logic (services, processors, handlers)
3. Data access (database, file I/O, external APIs)
4. Utilities (helpers, constants, config)

For each major file (>200 lines), answer:
- What is its single responsibility?
- Does it have multiple responsibilities that should be split?
- What are its dependencies?

Produce:
1. Architecture diagram (ASCII or mermaid)
2. List of files that should be refactored
3. Recommended module structure
```

### Prompt 2: Error Handling Audit

```
Audit error handling in [PROJECT_PATH].

Find all try/except blocks and categorize:
1. What exception types are caught?
2. Is there differentiation between retryable and non-retryable?
3. Are errors logged with sufficient context?
4. Are errors re-raised or swallowed?

Find all external calls (HTTP, database, file I/O) and check:
1. Is there timeout handling?
2. Is there retry logic?
3. What happens on failure?

Produce:
1. Table of error handling gaps (file, line, issue)
2. Recommended ErrorType enum for this project
3. Error classification function implementation
```

### Prompt 3: State Persistence Implementation

```
Analyze state management in [PROJECT_PATH].

Identify:
1. What state is kept in memory only?
2. What state is persisted to database?
3. What state is persisted to files?
4. What happens if the process crashes mid-operation?

For long-running operations, determine:
1. Can they be resumed after restart?
2. Is there checkpointing?
3. Is progress tracked?

Implement:
1. A checkpoint system that writes state to [CHECKPOINT_FILE] before/after operations
2. Recovery logic that runs on startup
3. File locking for the checkpoint file

Pattern to follow:
- Write checkpoint before starting operation
- Write checkpoint after completing operation
- On startup, find incomplete checkpoints and resume
```

### Prompt 4: Concurrency Safety

```
Audit concurrency in [PROJECT_PATH].

Find all shared mutable state:
1. Global variables
2. Class attributes shared across instances
3. Files written by multiple processes
4. Database rows updated by multiple processes

For each, determine:
1. Is there locking?
2. What kind of locking (mutex, file lock, DB lock)?
3. Are there race conditions?

Implement file-based locking for [SPECIFIC_RESOURCE]:
1. Create a lock manager using portalocker
2. Wrap all access to the resource in lock acquisition
3. Handle lock timeout gracefully
4. Add logging for lock acquisition/release
```

### Prompt 5: Retry Logic Implementation

```
Implement centralized retry logic for [PROJECT_PATH].

Create [PROJECT_PATH]/retry_manager.py with:

1. RetryConfig dataclass:
   - max_attempts (default 3)
   - base_delay_seconds (default 1.0)
   - max_delay_seconds (default 300)
   - exponential_base (default 2.0)
   - jitter (default True)
   - retryable_errors (list of ErrorType)

2. RetryManager class:
   - async execute_with_retry(operation, config) -> result
   - Logs each retry attempt
   - Calculates delay with exponential backoff + jitter
   - Checks error classification before retrying

3. Decorators for convenience:
   - @retry(max_attempts=3, on=[ErrorType.NETWORK])

Update these locations to use RetryManager:
[LIST SPECIFIC FUNCTIONS THAT NEED RETRY]
```

### Prompt 6: Flow Logging Implementation

```
Implement flow logging for [PROJECT_PATH].

Create [PROJECT_PATH]/flow_logger.py with:

1. FlowLogger class:
   - __init__(flow_type, flow_id, output_dir="flow_logs")
   - log_step(action, status, **context)
   - log_error(error, error_type, **context)
   - Writes JSONL format
   - Auto-increments step counter

2. Format:
   {"ts": "ISO8601", "flow_id": "...", "step": N, "action": "...", "status": "...", ...context}

3. Context manager for automatic start/end logging:
   with FlowLogger("job", job_id) as flow:
       flow.log_step("process", "started")
       # ... work ...
       flow.log_step("process", "completed")

Add flow logging to:
[LIST SPECIFIC OPERATIONS THAT NEED TRACING]

The goal: Given a flow_id, I can cat the JSONL file and see exactly what happened.
```

### Prompt 7: Validation Layer

```
Implement defense-in-depth validation for [PROJECT_PATH].

Create [PROJECT_PATH]/validators.py with:

1. InputValidator class with methods for:
   - validate_file_upload(file) - check size, type, extension
   - validate_url(url) - check format, scheme, optionally reachability
   - validate_required_fields(data, fields) - ensure fields exist
   - validate_enum_value(value, enum_class) - check valid enum

2. ValidationError exception:
   - field: str
   - message: str
   - value: Any (optional, for debugging)

3. Validation at TWO layers:
   - Router/Controller: Structure validation (is it valid JSON? required fields?)
   - Service: Business validation (does entity exist? has permission?)

Apply to these endpoints:
[LIST SPECIFIC ENDPOINTS THAT NEED VALIDATION]

Specific validations needed:
[LIST SPECIFIC VALIDATION RULES]
```

### Prompt 8: Cooldown System

```
Implement cooldown and rate limiting for [PROJECT_PATH].

1. Add to [MODEL_FILE] model:
   - consecutive_failures: int (default 0)
   - cooldown_until: datetime (nullable)
   - last_attempt_at: datetime (nullable)

2. Create [PROJECT_PATH]/cooldown_manager.py:

   class CooldownManager:
       SCHEDULE = [60, 300, 900, 3600]  # Seconds

       def should_process(self, entity) -> bool:
           # Check if past cooldown

       def record_failure(self, entity) -> None:
           # Increment failures, set cooldown

       def record_success(self, entity) -> None:
           # Reset failures and cooldown

       def get_next_eligible(self, entities) -> list:
           # Filter to only processable entities

3. Create [PROJECT_PATH]/rate_limiter.py:

   class RateLimiter:
       def __init__(self, max_per_minute: int):
           ...

       async def acquire(self) -> None:
           # Wait if at limit

       def current_usage(self) -> int:
           # Return current count

Apply cooldown to: [SPECIFIC_ENTITY_TYPE]
Apply rate limiting to: [SPECIFIC_API_CALLS]
```

---

## Application Example: i2v Project

Here's how the playbook applies to the i2v project (AI video generation backend):

### Diagnostic Results

| Principle | Status | Gap |
|-----------|--------|-----|
| Separation of Concerns | Partial | PipelineExecutor is 491 lines with multiple responsibilities |
| Error Classification | Missing | All errors treated equally |
| State Persistence | Missing | No checkpoint file, DB-only |
| File-Based Locking | Missing | Race condition on job claims |
| Defense in Depth | Partial | Router validation only |
| Retry with Backoff | Partial | Only for timeouts |
| Flow Logging | Missing | No operation traces |
| Cooldown/Rate Limiting | Missing | No tracking |

### Prioritized Prompts for i2v

**Week 1 - Critical**:
1. Prompt 4 (Concurrency) → Fix job claiming race condition in `worker.py:115-157`
2. Prompt 2 (Error Handling) → Add error classification in `fal_client.py`
3. Prompt 3 (State Persistence) → Add checkpoint file for worker

**Week 2 - Reliability**:
4. Prompt 5 (Retry Logic) → Centralize retry in new `retry_manager.py`
5. Prompt 6 (Flow Logging) → Add JSONL traces for jobs and pipelines
6. Prompt 1 (Architecture) → Split `pipeline_executor.py` into focused modules

**Week 3 - Hardening**:
7. Prompt 7 (Validation) → Add file size checks, URL validation
8. Prompt 8 (Cooldown) → Add failure tracking per job/model

### Customized Prompt Example

Here's Prompt 4 customized for i2v:

```
Audit concurrency in C:\Users\asus\Desktop\projects\i2v-analysis\app.

Find all shared mutable state:
1. Global variables in worker.py
2. Job records in SQLite database
3. The pending jobs query in worker.py lines 115-157

The critical race condition is in worker.py:
```python
pending_jobs = db.query(Job).filter(Job.wan_status == "pending").limit(N).all()
# Two workers can fetch the same jobs here!
for job in pending_jobs:
    job.wan_status = "submitted"
```

Implement file-based locking:
1. Create app/job_lock.py using portalocker
2. Wrap the job claiming logic:
   with JobLock("jobs.lock"):
       pending = claim_pending_jobs(limit=N, worker_id=MY_ID)
3. Add a claimed_by field to Job model
4. Log lock acquisition: "Worker X acquired job lock, claiming N jobs"
```

---

## Quick Reference Card

```
WHEN BUILDING PRODUCTION SYSTEMS:

1. SEPARATE concerns → One module, one job
2. CLASSIFY errors → Retry transient, fail permanent
3. PERSIST state → If not on disk, it didn't happen
4. LOCK resources → File locks for shared access
5. VALIDATE twice → Router AND service layer
6. RETRY with backoff → Exponential + jitter
7. LOG flows → JSONL traces for debugging
8. TRACK failures → Cooldown after repeated errors

DIAGNOSTIC QUESTIONS:
- What happens if this crashes mid-operation?
- What happens if two processes run this simultaneously?
- Can I debug a 3 AM failure from logs alone?
- What if the external API returns an error?
```

---

*This playbook is a living document. Update it as new failure modes are discovered and new patterns emerge.*
