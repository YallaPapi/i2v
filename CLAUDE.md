# Claude Code Instructions for i2v

---

## THE 10 COMMANDMENTS OF TASKMASTER (MANDATORY)

**Claude MUST follow these rules. No exceptions. GOSPEL.**

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

## VAST.AI SWARMUI - VERIFIED WORKING CONFIG

**CRITICAL LEARNING (2026-01-10):**
- Template hash `8e5e6ab1fceb9db3f813e815907b3390` does NOT work ("not accessible by user")
- Must use Docker image directly: `vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311`
- Must use `runtype: "jupyter_direct"` for port exposure
- Ports 7865/tcp and 8080/tcp are exposed with dynamic HostPort mapping

### Working API Payload
```python
payload = {
    "client_id": "i2v-swarmui",
    "image": "vastai/swarmui:v0.9.4.0-Beta-cuda-12.1-pytorch-2.5.1-py311",
    "disk": 80.0,
    "runtype": "jupyter_direct",
    "onstart": onstart_script,  # Optional model downloads
}
```

### Getting SwarmUI URL
```python
# After instance is running, extract port from ports dict
ports = instance_data.get('ports', {})
for port, mappings in ports.items():
    if '7865' in port:
        host_port = mappings[0]['HostPort']
        swarmui_url = f"http://{instance_data['public_ipaddr']}:{host_port}"
```

### RTX 5090 Filtering
```python
query = {
    'gpu_ram': {'gte': 30720},  # 30GB in MB (5090 has ~31.8GB)
    'gpu_name': {'eq': 'RTX 5090'},
    'rentable': {'eq': True},
    'dph_total': {'lte': 2.0}
}
```

---

## Project Overview

**i2v** - AI image-to-video platform. FastAPI + React + Vast.ai GPU.

## Key Files

| File | Purpose |
|------|---------|
| `app/services/vastai_client.py` | Vast.ai GPU management |
| `app/services/swarmui_client.py` | SwarmUI client |

## Commands

```bash
task-master list
task-master next
task-master set-status --id=X --status=done
```
