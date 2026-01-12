# PRD: vast.ai / SwarmUI Integration

**Author:** Gemini
**Version:** 1.0
**Date:** 2026-01-12

---

## 1. Overview

This document outlines the requirements for integrating a new backend generation provider into the existing application. The new provider will leverage a persistent GPU instance rented from `vast.ai`, running `SwarmUI` to execute jobs using open-source models.

### 1.1. Goal

The primary goal is to augment the current `fal.ai`-based generation service with a more cost-effective and scalable solution for bulk content creation, utilizing a persistent `vast.ai` instance.

### 1.2. Problem Statement

API costs for the existing `fal.ai` provider are high, making large-scale bulk generation expensive. The application needs a backend that can leverage cheaper, rented GPU hardware and open-source models to perform the same tasks.

### 1.3. Current State

An initial, non-functional attempt at `vast.ai` integration exists in the codebase. It consists of three disconnected components:
1.  A `vast.ai` client for provisioning machines (`app/vastai_client.py`).
2.  A `SwarmUI` client for submitting jobs, misnamed as `app/runpod_provider.py`.
3.  A generic job queue (`app/services/batch_queue.py`) that is not connected to the `vast.ai` components.

This project aims to fix, connect, and complete this integration.

---

## 2. Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| **FR1** | **Persistent Instance Management** | The system must manage a single, long-running `vast.ai` instance for processing jobs. It should not create a new instance for each job. |
| **FR1.1** | Automatic Recovery | The system must automatically detect if the active `vast.ai` instance has failed (via a health check). If it has failed or does not exist, it must automatically provision a new instance to take its place. |
| **FR2** | **Job Routing to `vast.ai`** | Users must be able to submit generation jobs to the `vast.ai`/`SwarmUI` backend. The API should allow the user to specify "vastai" as the desired provider. |
| **FR3** | **Model & Environment Support** | The `vast.ai` environment must be pre-configured with the required software and models. |
| **FR3.1** | Software Stack | The environment must run on a CUDA 12.8+ compatible GPU (e.g., A100/H100) and include `SwarmUI`, `triton`, and `sageattention`. |
| **FR3.2** | Models & LoRAs | The environment must include: <br> - `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` <br> - `wan22EnhancedNSFWCameraPrompt_nsfwFASTMOVEV2Q8H.gguf` <br> - `wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise` (LoRA) |
| **FR4** | **Seamless Frontend Experience** | Existing frontend features, particularly bulk job creation, must function correctly when the `vast.ai` backend is selected. The change should be transparent to the end-user's workflow. |

---

## 3. Technical Implementation Plan

This section outlines the technical steps to achieve the functional requirements.

| ID | Task | Description |
|---|---|---|
| **TR1** | **Refactor `SwarmUI` Client** | - Rename `app/runpod_provider.py` to `app/swarmui_client.py`. <br> - Rename the class `RunPodProvider` to `SwarmUIClient`. <br> - Modify the constructor to accept a dynamic `base_url`, removing the hardcoded dependency on `settings`. <br> - Remove the singleton pattern from the file. |
| **TR2** | **Create Orchestration Service** | - Create a new service file: `app/services/vastai_orchestrator.py`. <br> - Implement a `VastAIOrchestrator` class to manage the persistent `vast.ai` instance state (`get_or_create_instance` logic). <br> - This service will use `VastAIClient` for provisioning and `SwarmUIClient` for job submission. |
| **TR3** | **Integrate with Job Queue** | - Implement a `generation_fn` in the `VastAIOrchestrator` that is compatible with the `BatchQueue`. <br> - Modify `app/main.py` and `app/routers/batch_jobs.py` to check for a `provider` field in the job request. <br> - Inject the appropriate `generation_fn` (`fal.ai` or `vast.ai`) into the `BatchQueue` based on the selected provider. |
| **TR4** | **Build `vast.ai` Docker Image** | - Create a `Dockerfile.swarmui`. <br> - The image will install all required software (TR3.1) and download all specified models and LoRAs (TR3.2). <br> - The build process must include a mechanism to automate or bypass the `SwarmUI` setup wizard. |

---

## 4. Out of Scope

- A UI for directly managing `vast.ai` instances.
- Support for models or LoRAs other than those specified in FR3.2.
- Dynamic scaling to multiple `vast.ai` instances.

---

## 5. Success Criteria

- A user can submit a bulk generation job via the API/frontend, specifying `"provider": "vastai"`.
- The job is successfully processed by the persistent `SwarmUI` instance.
- The system demonstrates resilience: if the `vast.ai` instance is terminated, the next job submission automatically provisions a new instance and completes successfully.
- The final generated artifact (e.g., video) is correctly returned and accessible.
