# PRD: Vast.ai SwarmUI Integration

## Overview

The goal is to make the Vast.ai SwarmUI template reliably start on an RTX 5090 instance and be reachable by the backend for image-to-video generation. The current SwarmUI instance remains stuck in a "loading" state and never exposes a usable URL.

## Current Issue

- Target instance (e.g. RTX 5090) is stuck in `loading`.
- `webpage` is `null` / missing, so there is no Cloudflare tunnel URL.
- SwarmUI never becomes accessible from the backend.

The underlying cause is not yet confirmed and requires focused investigation rather than trial-and-error.

## Research Tasks

1. **Vast.ai template behavior**
   - Understand how `template_hash_id` is resolved on the Vast API side.
   - Confirm required fields for creating an instance from the official SwarmUI template (disk, ports, env, etc.).

2. **SwarmUI template specifics**
   - Verify which ports are exposed (internal and external).
   - Determine expected startup time on a 24 GB+ GPU.
   - Identify a simple health-check condition (e.g. HTTP 200 on the portal / SwarmUI endpoint).

3. **Instance diagnostics**
   - Determine how to:
     - Inspect instance logs (portal logs, Docker logs, SwarmUI logs).
     - Connect via SSH and verify that SwarmUI is running.
     - Interpret the "loading" state and common reasons it never transitions to "running".

## Code Areas to Review

- `app/services/vastai_client.py`
  - `create_swarmui_instance()` and any helper it uses for the Vast payload.
  - Payload fields: `template_hash_id`, disk size, ports, env, `onstart`.
  - The model download / `onstart` script: confirm it does not block or break initial startup.
  - Port and URL extraction logic used to derive the final SwarmUI URL.

- Any code that:
  - Polls for Vast instance status.
  - Maps Vast instance data into `webpage` / `swarmui_url` in configuration.

## Success Criteria

SwarmUI integration is considered working when all of the following are true:

1. The Vast.ai instance reaches `running` (not stuck in `loading`).
2. The instance has a valid `webpage` or equivalent URL (Cloudflare tunnel) populated.
3. SwarmUI is reachable at that URL and passes a basic health check.
4. The backend can trigger video generation via SwarmUI and receive a successful response for a test job.

## Monitoring & Runtime Behavior

- Poll Vast.ai instance status every 15 seconds.
- Update internal state / logs at least once per minute while the instance is starting.
- Avoid hard timeouts during initial debugging; instead, log extended startup durations and surface clear errors when startup exceeds a configured threshold.

## Next Step

Once this PRD is approved, it can be fed into the task orchestration / research tooling to systematically:

- Map the Vast.ai template API behavior.
- Validate the SwarmUI template assumptions.
- Implement and verify the fixes in `vastai_client.py` and related health-check logic.
