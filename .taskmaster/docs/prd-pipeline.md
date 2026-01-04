# PRD: Multi-Step Generation Pipeline

## Overview

Build a flexible pipeline system that chains I2I (image-to-image), I2V (image-to-video), and prompt enhancement together. Users can run individual steps or chain them automatically with optional manual checkpoints.

The UI follows a Leonardo.ai-inspired "playground" style: clean, creator-friendly, with a central canvas for prompts/uploads, sidebar for models/parameters, real-time previews, and workflow "blueprints" for chaining steps.

---

## Core Concepts

### Pipeline = Chain of Steps
```
[Source Image(s)]
    → [Prompt Enhancer] (optional)
    → [I2I Generator] (optional)
    → [I2V Generator] (optional)
    → [Final Outputs]
```

Each step can:
- Be skipped
- Run in bulk (multiple inputs × multiple prompts = combinatorial expansion)
- Have manual review checkpoint OR auto-continue
- Use different models
- Generate multiple outputs per input

---

## Step Types

### 1. Prompt Enhancer
**Input**: Simple prompt + context
**Output**: Enhanced prompt(s)

Features:
- Takes lazy one-liner → produces detailed, model-optimized prompt
- Can generate N variations from 1 input prompt
- Context-aware (knows if target is I2I or I2V)
- Bulk mode: multiple input prompts → multiple enhanced outputs
- Theme options: Focus on outfits/poses/expressions/lighting

Example:
```
Input: "woman in red dress"
Output (5 variations):
  1. "Elegant woman in flowing crimson evening gown, soft studio lighting..."
  2. "Young woman wearing fitted red cocktail dress, urban street backdrop..."
  3. "Model in vintage red dress with lace details, golden hour lighting..."
  ...
```

### 2. I2I (Image-to-Image)
**Input**: Source image + prompt
**Output**: Modified image(s)

Features:
- Single image + single prompt → N output images
- "Set mode": Generate variations (angles, poses, expressions, outfits)
- Bulk: M images × P prompts × N outputs = M×P×N total images
- Model selection (gpt-image-1.5, kling-image, nano-banana, nano-banana-pro)

Set Mode Options:
- Angle variations (front, side, 3/4, back)
- Expression variations (smile, serious, laugh, contemplative)
- Pose variations (standing, sitting, walking, action)
- Outfit variations (based on prompt themes)
- Lighting variations (studio, natural, dramatic, soft)

### 3. I2V (Image-to-Video)
**Input**: Source image + motion prompt
**Output**: Video(s)

Features:
- Single image + single prompt → N output videos
- Bulk: M images × P prompts × N outputs = M×P×N total videos
- Model selection (wan, kling, veo, sora variants)
- Duration selection (5s, 10s, etc.)
- Resolution selection (480p, 720p, 1080p)

---

## Pipeline Modes

### Mode 1: Step-by-Step (Manual)
User runs each step individually, reviews outputs, then proceeds.
```
1. Upload images → Review
2. Run prompt enhancer → Review/edit prompts
3. Run I2I → Review/select images
4. Run I2V → Review videos
```

### Mode 2: Auto-Chain (Hands-off)
User configures everything upfront, system runs entire pipeline.
```
Config:
  - Source: 3 images
  - Prompt enhancer: Generate 5 prompts each
  - I2I: Generate 2 images per prompt (3×5×2 = 30 images)
  - I2V: Generate 1 video per image (30 videos)

→ Click "Run Pipeline" → Wait → Get 30 videos
```

### Mode 3: Checkpoint Mode
Auto-run with pause points for review.
```
Config:
  - Checkpoint after: Prompt Enhancement ✓
  - Checkpoint after: I2I ✓
  - Checkpoint after: I2V ✗ (auto-complete)
```

---

## Data Model

### Pipeline
```
pipelines:
  id: INTEGER PK
  name: TEXT
  status: pending | running | paused | completed | failed
  mode: manual | auto | checkpoint
  checkpoints: JSON (which steps pause for review)
  created_at: DATETIME
  updated_at: DATETIME
```

### PipelineStep
```
pipeline_steps:
  id: INTEGER PK
  pipeline_id: FK → pipelines
  step_type: prompt_enhance | i2i | i2v
  step_order: INTEGER
  config: JSON (model, count, prompts, etc.)
  status: pending | running | review | completed | failed
  inputs: JSON (image_urls, prompts from previous step)
  outputs: JSON (generated prompts/images/videos)
  cost_estimate: DECIMAL
  cost_actual: DECIMAL
  created_at: DATETIME
  updated_at: DATETIME
```

### Config JSON Examples

Prompt Enhancer Config:
```json
{
  "input_prompts": ["woman in red dress"],
  "variations_per_prompt": 5,
  "target_type": "i2i",
  "style_hints": ["photorealistic", "fashion"],
  "theme_focus": "outfits"
}
```

I2I Config:
```json
{
  "model": "gpt-image-1.5",
  "images_per_prompt": 2,
  "set_mode": {
    "enabled": true,
    "variations": ["angles", "poses"],
    "count_per_variation": 2
  },
  "aspect_ratio": "9:16",
  "quality": "high"
}
```

I2V Config:
```json
{
  "model": "kling",
  "videos_per_image": 1,
  "resolution": "1080p",
  "duration_sec": 5
}
```

---

## Cost Calculation

### Pricing Data (from README)
```
I2I Models:
  gpt-image-1.5: $0.009-0.20/image (varies by quality)
  kling-image: $0.028/image
  nano-banana: $0.039/image
  nano-banana-pro: $0.15/image

I2V Models:
  wan (480p): $0.25/5s
  kling: $0.35/5s
  kling-master: $1.40/5s
  veo31-fast: $0.60/6s
  sora-2: $0.40/4s
  ...
```

### Cost Estimation Formula
```
Total Cost = Σ(step_cost)

step_cost(prompt_enhance) = num_prompts × $0.001 (negligible, use Claude/GPT)
step_cost(i2i) = num_images × model_price
step_cost(i2v) = num_videos × model_price × (duration/base_duration)
```

### Display Format
```
Pipeline Cost Estimate:
  ├─ Prompt Enhancement: 15 prompts × $0.001 = $0.02
  ├─ I2I Generation: 30 images × $0.028 = $0.84
  └─ I2V Generation: 30 videos × $0.35 = $10.50
  ─────────────────────────────────────────────
  Total: $11.36
```

---

## API Endpoints

### Pipeline Management
```
POST   /pipelines              Create new pipeline
GET    /pipelines              List pipelines
GET    /pipelines/{id}         Get pipeline details
PUT    /pipelines/{id}         Update pipeline config
DELETE /pipelines/{id}         Delete pipeline
POST   /pipelines/{id}/run     Start/resume pipeline
POST   /pipelines/{id}/pause   Pause at next checkpoint
POST   /pipelines/{id}/cancel  Cancel pipeline
```

### Step Management
```
GET    /pipelines/{id}/steps           List steps
GET    /pipelines/{id}/steps/{step_id} Get step details
PUT    /pipelines/{id}/steps/{step_id} Update step (review mode)
POST   /pipelines/{id}/steps/{step_id}/approve  Approve and continue
POST   /pipelines/{id}/steps/{step_id}/retry    Retry failed step
```

### Prompt Enhancement
```
POST   /prompts/enhance
{
  "prompts": ["woman in red dress"],
  "count": 5,
  "target": "i2i",
  "style": "photorealistic",
  "theme_focus": "outfits"
}
→ Returns enhanced prompts
```

### Cost Estimation
```
POST   /pipelines/estimate
{
  "steps": [...]
}
→ Returns cost breakdown
```

---

## UI Design Specification

### Design Philosophy
Leonardo.ai-inspired "playground" style:
- Clean, creator-friendly interface
- Central canvas for prompts/uploads
- Sidebar for models/parameters
- Real-time previews
- Workflow "blueprints" for chaining steps
- 2-3 click setups for bulk/chains
- Speed emphasis (queue multiple gens in ~2 minutes)
- Dark/light mode support
- Mobile-first responsive design

### Overall Layout

#### Top Bar
- Logo (left)
- Main tabs: "Playground" (main gen area), "Workflows" (bulk/chains), "Library" (assets/jobs)
- Right side:
  - Credits/$ usage meter (previews costs based on Fal.ai rates)
  - Profile dropdown (settings, API keys)
  - Upgrade button (if applicable)

#### Sidebar (Left, Collapsible)
- Model selector dropdown:
  - Video: Wan variants, Kling types, Veo/Sora
  - Image: GPT-Image, Kling-Image, Nano-Banana
- Quick parameters:
  - Resolution slider (480p-1080p)
  - Duration slider (4-12s)
  - Quality dropdown (low/med/high)
  - Aspect ratio selector
- "Enhance Prompt" button for one-click refinement
- Cost preview (updates in real-time as params change)

#### Central Canvas (Main Area)
- Large interactive zone:
  - Drag-drop zone for images/URLs
  - Big textarea for prompts with auto-suggest
  - Mode toggle: I2I / I2V / Full Pipeline
- Below canvas:
  - Output previews (gallery/carousel)
  - Hover play for video previews
  - Click to expand/download

#### Footer
- Real-time queue status: "3/20 gens complete – 1 min left"
- Help chat bubble
- Keyboard shortcuts hint

### Component Specifications

#### ImageUploadZone
```
Props:
  - multiple: boolean (allow multi-upload)
  - accept: string[] (file types)
  - onUpload: (files: File[]) => void
  - showLibrary: boolean (show "select from library" option)

Features:
  - Drag-drop with visual feedback
  - Paste URL support
  - ZIP/folder upload for bulk
  - Preview thumbnails
  - Remove/reorder uploads
```

#### PromptInput
```
Props:
  - value: string
  - onChange: (value: string) => void
  - onEnhance: () => void
  - showEnhanceButton: boolean
  - placeholder: string

Features:
  - Large textarea (3-5 lines default)
  - Auto-suggest as user types
  - "Enhance" button with loading state
  - Character count
  - Multi-prompt mode (paste multiple, separated by ---)
```

#### ModelSelector
```
Props:
  - type: 'i2i' | 'i2v'
  - value: string
  - onChange: (model: string) => void
  - showPricing: boolean

Features:
  - Grouped dropdown (by provider)
  - Price shown next to each model
  - Tooltip with model capabilities
  - "Recommended" badge on best value
```

#### SetModeModal (I2I Photo Sets)
```
Trigger: "Create Photo Set" button

Options:
  - Angles: Front, Side, 3/4, Back (checkboxes)
  - Expressions: Smile, Neutral, Surprise, Serious (checkboxes)
  - Poses: Standing, Sitting, Walking, Dancing (checkboxes)
  - Outfits: Text input for variations (e.g., "casual, formal, sporty")
  - Lighting: Studio, Natural, Dramatic, Soft (checkboxes)

Quantity:
  - "Generate X per variation" slider (1-5)

Preview:
  - Shows calculated total: "2 angles × 3 expressions = 6 images"
```

#### CostPreview
```
Props:
  - steps: PipelineStep[]
  - realTime: boolean

Display:
  - Tree breakdown by step
  - Per-model costs
  - Total with currency
  - "Estimate" badge (updates as config changes)

Example:
  ├─ Prompt Enhancement: 5 × $0.001 = $0.01
  ├─ I2I (kling-image): 10 × $0.028 = $0.28
  └─ I2V (kling): 10 × $0.35 = $3.50
  ────────────────────────────────
  Total: $3.79
```

#### ProgressMonitor
```
Props:
  - pipelineId: string
  - onComplete: () => void

Features:
  - Step-by-step progress bar
  - Current step highlighted
  - ETA based on model speeds
  - Live output previews as they complete
  - Pause/Cancel buttons
  - Error display with retry option
```

#### OutputGallery
```
Props:
  - outputs: Output[]
  - type: 'image' | 'video' | 'mixed'
  - selectable: boolean

Features:
  - Grid/masonry layout
  - Filter by step type, model, date
  - Bulk select for download
  - Hover preview (play for videos)
  - Click to expand full view
  - Download individual or ZIP
  - "Re-run" button on each output
```

### Page Flows

#### Flow 1: Playground (Quick Single Run)

**Step 1: Landing**
- Central prompt: "What do you want to create?"
- Three large cards:
  - "Edit Images" (I2I) - icon + description
  - "Animate Images" (I2V) - icon + description
  - "Full Pipeline" (I2I → I2V) - icon + description

**Step 2: Upload**
- ImageUploadZone centered
- "Or paste URL" input below
- "Select from Library" button
- Uploaded images show as thumbnails

**Step 3: Configure**
- PromptInput with enhance button
- If enhanced: shows variations in expandable list
- Sidebar params visible (model, resolution, etc.)
- SetModeModal trigger if I2I selected

**Step 4: Review Cost**
- CostPreview component
- Breakdown shown inline
- "Generate" button with total cost

**Step 5: Monitor**
- ProgressMonitor takes over canvas
- Real-time updates via WebSocket
- Outputs appear as they complete

**Step 6: Results**
- OutputGallery with all outputs
- Download all / selected
- "Run Again" with same config
- "Modify & Run" to adjust

#### Flow 2: Workflows (Bulk/Chains)

**Visual Builder (like Leonardo.ai Blueprints)**
- Flowchart-style canvas
- Drag-drop nodes:
  - "Upload Images" (start node)
  - "Enhance Prompts" (with config)
  - "Generate Images" (I2I with config)
  - "Generate Videos" (I2V with config)
- Connect nodes with arrows
- Each node shows:
  - Step type icon
  - Brief config summary
  - Estimated output count
  - Cost for this step

**Bulk Configuration**
- Multi-image upload (ZIP/folder)
- Multi-prompt input (text file or paste)
- Combination modes:
  - "All Combinations" (M × N)
  - "One-to-One" (paired)
  - "Dry Run" (preview only)

**Chain Preview**
- Tree view of entire pipeline:
  ```
  1 image → 5 enhanced prompts
    → 25 images (5 per prompt)
      → 125 videos (5 per image)
  Total: 125 videos = $62.50
  ```
- Edit quantities at any level
- "Simulate" button for dry-run

**Execution Options**
- "Auto-Run" (complete pipeline)
- "Manual Checkpoints" (pause after each step)
- Select which steps pause for review

#### Flow 3: Library

**Asset Management**
- Grid gallery of all uploads and outputs
- Filter by:
  - Type (image/video)
  - Source (uploaded/generated)
  - Date range
  - Pipeline/job
- Bulk actions:
  - Download selected
  - Delete selected
  - Use in new pipeline

**Job History**
- Table/list of past pipelines
- Status badges (completed/failed/in-progress)
- Click to view details:
  - Config used
  - Outputs generated
  - Cost incurred
  - Retry/clone options

### Real-Time Features

#### WebSocket Events
```
pipeline_status: { id, status, current_step }
step_progress: { step_id, progress_pct, outputs_so_far }
output_ready: { step_id, output_url, output_type }
cost_update: { pipeline_id, cost_actual }
error: { step_id, error_message, retryable }
```

#### Optimistic UI
- Show "Queuing..." immediately on submit
- Disable inputs during processing
- Update progress without full page reload
- Toast notifications for completions/errors

### Mobile Responsiveness

#### Layout Changes
- Sidebar becomes bottom sheet (swipe up)
- Canvas stacks vertically
- Gallery switches to single column
- Touch-optimized buttons (44px min)

#### Gestures
- Swipe to delete uploads
- Pinch to zoom gallery
- Pull to refresh job status

---

## Implementation Phases

### Phase 1: Core Pipeline Engine (Backend)
- [ ] Pipeline and PipelineStep models
- [ ] Pipeline state machine (pending → running → completed)
- [ ] Step execution engine
- [ ] Cost calculation service

### Phase 2: Prompt Enhancer (Backend)
- [ ] Integration with Claude/GPT API
- [ ] Prompt templates for I2I vs I2V
- [ ] Variation generation logic
- [ ] Caching for similar prompts

### Phase 3: Enhanced I2I/I2V (Backend)
- [ ] Set mode for I2I (variations)
- [ ] Bulk processing support
- [ ] Output-to-input chaining
- [ ] Progress tracking per step

### Phase 4: Playground UI (Frontend)
- [ ] New layout structure (top bar, sidebar, canvas, footer)
- [ ] ImageUploadZone component
- [ ] PromptInput with enhance integration
- [ ] ModelSelector with pricing
- [ ] CostPreview real-time calculator
- [ ] ProgressMonitor with WebSocket
- [ ] OutputGallery with filtering

### Phase 5: Workflows UI (Frontend)
- [ ] Visual pipeline builder (flowchart nodes)
- [ ] Bulk upload (ZIP/folder)
- [ ] Multi-prompt input
- [ ] Combination mode selector
- [ ] Chain preview tree
- [ ] Checkpoint configuration

### Phase 6: Library & Polish (Frontend)
- [ ] Asset library with filtering
- [ ] Job history table
- [ ] Mobile responsive layout
- [ ] Dark/light mode toggle
- [ ] Onboarding wizard (React Joyride)
- [ ] Keyboard shortcuts

### Phase 7: Advanced Features
- [ ] Templates/presets (save workflow configs)
- [ ] Scheduled runs
- [ ] Webhook notifications
- [ ] Public API with rate limiting

---

## Technical Notes

### Prompt Enhancement Implementation
Use Claude API (claude-3-haiku for cost efficiency):
```python
async def enhance_prompt(
    simple_prompt: str,
    target: Literal["i2i", "i2v"],
    count: int = 5,
    style: str = "photorealistic",
    theme_focus: str = None
) -> list[str]:
    system = f"""You are a prompt engineer for AI {target} generation.
    Given a simple prompt, create {count} detailed, varied prompts.
    Style: {style}
    {"Focus on: " + theme_focus if theme_focus else ""}
    Output as JSON array of strings."""

    response = await claude.messages.create(
        model="claude-3-haiku-20240307",
        messages=[{"role": "user", "content": simple_prompt}],
        system=system
    )
    return json.loads(response.content)
```

### Pipeline Execution
```python
async def execute_pipeline(pipeline_id: int):
    pipeline = get_pipeline(pipeline_id)

    for step in pipeline.steps:
        if pipeline.mode == "checkpoint" and step.type in pipeline.checkpoints:
            step.status = "review"
            await notify_user(pipeline_id, step.id)
            return  # Pause for review

        step.status = "running"
        await broadcast_status(pipeline_id, step.id, "running")

        if step.type == "prompt_enhance":
            outputs = await enhance_prompts(step.config)
        elif step.type == "i2i":
            outputs = await generate_images(step.inputs, step.config)
        elif step.type == "i2v":
            outputs = await generate_videos(step.inputs, step.config)

        step.outputs = outputs
        step.status = "completed"
        await broadcast_status(pipeline_id, step.id, "completed", outputs)

        # Chain outputs to next step's inputs
        next_step = get_next_step(pipeline, step)
        if next_step:
            next_step.inputs = outputs
```

### Frontend Tech Stack
```
React 18.3.1 + TypeScript
Vite 5.4.8 (build tool)
Tailwind CSS 3.4.14 (styling)
shadcn/ui components (base)
TanStack Query 5.59.0 (data fetching)
React Hook Form 7.53.0 + Zod 3.23.8 (forms)
Lucide React 0.451.0 (icons)
React Dropzone 14.2.3 (file uploads)
Socket.io-client 4.7.5 (real-time)
React Joyride 2.8.1 (onboarding)
Recharts 2.12.7 (cost charts if needed)
```

---

## Success Metrics

1. **Usability**: User can go from 1 image to multiple videos in < 5 clicks
2. **Speed**: Pipeline queues in < 2 seconds, feel instant
3. **Transparency**: Cost shown before any generation runs
4. **Flexibility**: Support for manual, auto, and hybrid workflows
5. **Scalability**: Handle bulk operations (100+ images) without timeout
6. **Reliability**: Resume interrupted pipelines, retry failed steps
7. **Mobile**: Full functionality on mobile devices
