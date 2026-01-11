# Claude Code Instructions for i2v

---

## TASKMASTER MCP REFERENCE (QUICK GUIDE)

### Available MCP Tools (Core Tier)

| Tool | CLI Equivalent | Purpose |
|------|---------------|---------|
| `mcp__task-master-ai__get_tasks` | `task-master list` | List all tasks |
| `mcp__task-master-ai__next_task` | `task-master next` | Get next available task |
| `mcp__task-master-ai__get_task` | `task-master show <id>` | View task details |
| `mcp__task-master-ai__set_task_status` | `task-master set-status` | Update task status |
| `mcp__task-master-ai__update_subtask` | `task-master update-subtask` | Add notes to subtask |
| `mcp__task-master-ai__parse_prd` | `task-master parse-prd` | Generate tasks from PRD |
| `mcp__task-master-ai__expand_task` | `task-master expand` | Break task into subtasks |

### Research Mode (CRITICAL)

**For ANY research question, use `expand_task` with `research=true`:**

```python
mcp__task-master-ai__expand_task(
    id="<task_id>",           # Must be existing task ID (e.g., "350")
    research=True,            # Uses Perplexity AI for web research
    force=True,               # Overwrite existing subtasks
    prompt="Your research question here...",
    projectRoot="C:/Users/asus/Desktop/projects/i2v"
)
```

**For parsing a PRD with research:**

```python
mcp__task-master-ai__parse_prd(
    input=".taskmaster/docs/prd.txt",
    research=True,            # Research-backed task generation
    force=True,
    projectRoot="C:/Users/asus/Desktop/projects/i2v"
)
```

### Task ID Format

- Main tasks: `350`, `351`, `352`
- Subtasks: `350.1`, `350.2`, `351.1`
- Sub-subtasks: `350.1.1`, `350.1.2`

### Task Status Values

`pending` | `in-progress` | `done` | `deferred` | `cancelled` | `blocked` | `review`

### Common Patterns

```python
# Get next task to work on
mcp__task-master-ai__next_task(projectRoot="...")

# Mark task done
mcp__task-master-ai__set_task_status(id="350", status="done", projectRoot="...")

# Research and expand a task
mcp__task-master-ai__expand_task(id="350", research=True, force=True, prompt="...", projectRoot="...")

# Add implementation notes to subtask
mcp__task-master-ai__update_subtask(id="350.1", prompt="Notes here...", projectRoot="...")
```

---

## THE 10 COMMANDMENTS OF TASKMASTER (MANDATORY)

**Claude MUST follow these rules. No exceptions. GOSPEL.**

### 0. THOU SHALT NOT USE WEB SEARCH
Web search is outdated and dysfunctional. Use Taskmaster research function which utilizes Perplexity, this gives much much more accurate answers.

### I. THOU SHALT NOT THINK ON THY OWN
Never guess. Use TaskMaster with `research=true` for ALL unknowns.

### II. THOU SHALT USE TASKMASTER FOR ALL RESEARCH
```python
mcp__task-master-ai__expand_task(id="X", research=True, force=True, prompt="...")
```
`research=true` uses **Perplexity AI** which ACTUALLY SEARCHES THE WEB.

### III. THOU SHALT NEVER ASSUME API BEHAVIOR
API fails? STOP. TaskMaster research subtask. Fix with VERIFIED info only.

### IV-X. [See full commandments in previous version]

---

## AUTOMATIC VIDEO GENERATION (LIKE FAL.AI)

The SwarmUI integration is now **fully automatic**. No manual GPU setup needed.

### One Endpoint, Fully Automatic

```bash
curl -X POST http://localhost:8000/api/vastai/swarmui/generate-video \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://...", "prompt": "camera slowly zooms in"}'
```

### What Happens Automatically

1. Check for existing GPU - Uses configured URL if available
2. Provision RTX 5090 - Finds cheapest offer, creates instance
3. Wait for instance - Polls every 15s until "running"
4. Wait for SwarmUI healthy - Polls every 15s, logs every minute
5. Auto-configure URL - Sets runtime GPU config
6. Generate video - Uses SwarmUI API
7. Cache to R2 - Returns permanent URL

---

## VAST.AI SWARMUI - VERIFIED WORKING CONFIG

**CRITICAL LEARNING (2026-01-10):**
- Template hash does NOT work ("not accessible by user")
- Must use Docker image: `vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311`
- Must use `runtype: "jupyter_direct"` for port exposure
- Ports 7865/tcp and 8080/tcp are exposed with dynamic HostPort mapping

### Working API Payload
```python
payload = {
    "client_id": "i2v-swarmui",
    "image": "vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311",
    "disk": 80.0,
    "runtype": "jupyter_direct",
    "onstart": onstart_script,
}
```

---

## Project Overview

**i2v** - AI image-to-video platform. FastAPI + React + Vast.ai GPU.

## Key Files

| File | Purpose |
|------|---------|
| `app/services/vastai_client.py` | Vast.ai GPU + auto health check |
| `app/services/swarmui_client.py` | SwarmUI REST API client |
| `app/routers/vastai.py` | `/api/vastai/*` endpoints |

## Commands

```bash
uvicorn app.main:app --reload    # Backend
cd frontend && npm run dev       # Frontend
```
