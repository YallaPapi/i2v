# UX Implementation PRD - i2v Frontend Improvements

## Overview

This PRD defines implementation tasks derived from the UX Evaluation Report. The improvements are prioritized by impact and effort, with critical issues addressed first.

## Goals

1. Fix critical UX issues that cause user confusion and potential financial loss
2. Improve system visibility and user control
3. Enhance efficiency for power users
4. Polish consistency and reduce cognitive load

## Priority 1: Critical Fixes

### Task 1: Add Generation Confirmation Modal

**Problem**: Users can accidentally trigger expensive ($50+) generations with a single click.

**Implementation**:
- Create a `ConfirmGenerationModal` component in `frontend/src/components/pipeline/`
- Show modal when user clicks "Create Photos/Videos/Both" button
- Display:
  - Total estimated cost (from `bulkCostEstimate`)
  - Number of outputs to generate
  - Breakdown: X photos, Y videos
  - Source images count
- Add checkbox: "Don't ask again for jobs under $X"
- Store preference in localStorage
- Only show modal if cost > $1 (configurable threshold)

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add modal trigger before `handleBulkGenerate`
- Create `frontend/src/components/pipeline/ConfirmGenerationModal.tsx`

**Acceptance criteria**:
- Modal appears before generation starts
- Shows accurate cost breakdown
- User can dismiss and not see again for small jobs
- Cancel button returns to editing

---

### Task 2: Fix Prompt Builder Flow - Add Visual Warning

**Problem**: Users generate prompts in AI Prompt Builder but forget to click "Add to Photo Prompts", causing old prompts to be sent instead.

**Implementation**:
- Add a warning banner when generated prompts exist but haven't been added
- Show banner above the "Create" button in sidebar
- Banner text: "You have X generated prompts that haven't been added to your photo descriptions"
- Add "Add Now" button in the banner
- Optionally: Auto-add prompts with a toast notification showing "Added X prompts to queue"

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add conditional warning near generate button
- Style warning prominently (yellow/orange background)

**Acceptance criteria**:
- Warning visible when `generatedPrompts.length > 0` and prompts not in `bulkI2iPrompts`
- One-click "Add Now" transfers prompts
- Warning disappears after adding

---

### Task 3: Fix Jobs Page Status Filter (Bug)

**Problem**: Status filter dropdown exists but `statusFilter` state is never used in API query.

**Implementation**:
- Pass `statusFilter` to `usePipelines` query params
- Update backend if needed to support status filtering

**Files to modify**:
- `frontend/src/pages/Jobs.tsx` line ~358-364 - Add `status: statusFilter || undefined` to queryParams

**Acceptance criteria**:
- Selecting "Completed" shows only completed jobs
- Selecting "Failed" shows only failed jobs
- "All Statuses" shows everything

---

## Priority 2: Major Improvements

### Task 4: Add Cancel Button During Generation

**Problem**: Once generation starts, users cannot cancel. They must wait or refresh.

**Implementation**:
- Add `isCancelling` state to track cancellation
- Add "Cancel" button to `BulkProgress` component
- Create `/api/pipelines/{id}/cancel` endpoint on backend
- When cancelled:
  - Stop polling for new results
  - Mark pipeline as "cancelled" status
  - Show partial results that completed
  - Toast: "Generation cancelled. X items completed before cancellation."

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add cancel handler
- `frontend/src/components/pipeline/BulkProgress.tsx` - Add cancel button
- `app/routers/pipelines.py` - Add cancel endpoint
- Backend pipeline executor - Support cancellation flag

**Acceptance criteria**:
- Cancel button visible during generation
- Cancellation stops further API calls
- Partial results still accessible

---

### Task 5: Improve Generation Progress Visibility

**Problem**: Users only see "Processing..." with no details about current step or time remaining.

**Implementation**:
- Enhance `BulkProgress` to show:
  - Current step: "Generating photo 3 of 12..."
  - Step type icon (camera for I2I, video for I2V)
  - Progress bar (completed/total)
  - Estimated time remaining
  - Live thumbnails of completed outputs (last 4)
- Poll for step-level status updates

**Files to modify**:
- `frontend/src/components/pipeline/BulkProgress.tsx` - Major enhancement
- `frontend/src/pages/Playground.tsx` - Pass additional props

**Acceptance criteria**:
- Step-by-step progress visible
- Thumbnails appear as outputs complete
- Time estimate updates in real-time

---

### Task 6: Add Search to Jobs Page

**Problem**: Users with many jobs cannot search, must scroll through all.

**Implementation**:
- Add search input in Jobs page header
- Search by:
  - Pipeline name
  - Prompt text (first_prompt field)
- Debounce search input (300ms)
- Pass search query to backend
- Add `/api/pipelines?search=` query param support

**Files to modify**:
- `frontend/src/pages/Jobs.tsx` - Add search input and state
- `frontend/src/hooks/useJobs.ts` - Update query to include search
- `app/routers/pipelines.py` - Add search query param handling

**Acceptance criteria**:
- Search filters jobs in real-time
- Searches both name and prompt content
- Clear button resets search

---

### Task 7: Simplify Model Selector

**Problem**: 11+ models with technical names cause analysis paralysis.

**Implementation**:
- Add use-case groupings to model selector:
  - "Recommended" (top picks)
  - "Budget-Friendly"
  - "Highest Quality"
  - "Fastest"
- Add visual quality indicator (1-5 stars or quality bar)
- Add "Compare Models" expandable section showing side-by-side
- Highlight "Best Value" badge more prominently

**Files to modify**:
- `frontend/src/components/pipeline/ModelSelector.tsx` - Restructure groupings

**Acceptance criteria**:
- Models grouped by use case
- Quality indicators visible
- Easy to identify best option for user's needs

---

### Task 8: Hide FLUX Settings in Advanced Section

**Problem**: 5-7 FLUX sliders overwhelm users who don't need them.

**Implementation**:
- Wrap FLUX settings in collapsible "Advanced Settings" accordion
- Collapsed by default
- Add "Presets" dropdown above: "Balanced", "Quality First", "Speed First"
- Presets auto-fill slider values

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Wrap FLUX settings in Collapsible
- Add presets data and handler

**Acceptance criteria**:
- FLUX settings hidden by default
- "Advanced Settings" toggle reveals them
- Presets provide one-click configuration

---

## Priority 3: Minor Improvements

### Task 9: Add Upload Progress Indicator

**Problem**: Multi-file upload shows only "Uploading..." with no progress.

**Implementation**:
- Track upload progress: `uploadProgress: { current: number, total: number }`
- Show "Uploading 3 of 10 images..." text
- Add progress bar below upload zone

**Files to modify**:
- `frontend/src/components/pipeline/ImageUploadZone.tsx`

---

### Task 10: Add Undo for Clear All Prompts

**Problem**: Clear All instantly deletes prompts with no undo.

**Implementation**:
- Store last prompts before clear in ref
- Show toast: "Cleared X prompts. Undo?"
- Undo button restores from ref
- Toast auto-dismisses after 5 seconds

**Files to modify**:
- `frontend/src/components/pipeline/MultiPromptInput.tsx`
- Add toast notification system if not exists

---

### Task 11: Auto-Scroll to Results

**Problem**: Results appear below the fold; users may miss them.

**Implementation**:
- When `pipelineStatus` changes to 'completed', scroll to results
- Use `scrollIntoView({ behavior: 'smooth' })`
- Also show toast: "Generation complete! X outputs ready"

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add effect for completion

---

### Task 12: Rename Demo Mode to Favorites Only

**Problem**: "Demo Mode" naming is confusing.

**Implementation**:
- Change button text from "Demo Mode" to "Favorites Only"
- Update icon to filled star when active
- Add tooltip explaining behavior

**Files to modify**:
- `frontend/src/pages/Jobs.tsx` - Update button text

---

### Task 13: Add Tooltip to Health Indicator

**Problem**: Colored dot in header has no explanation.

**Implementation**:
- Wrap health indicator in Tooltip component
- Show: "Backend Status: Connected" (green) or "Backend Status: Disconnected" (red)
- Add suggestion if disconnected: "Try restarting the server"

**Files to modify**:
- `frontend/src/components/Layout.tsx`

---

### Task 14: Show Recent Prompts by Default

**Problem**: Recent prompts hidden behind toggle, users forget they exist.

**Implementation**:
- Show last 3 recent prompts inline (collapsed format)
- "Show more" expands full list
- Style as subtle chips below prompt input

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Adjust recent prompts display

---

### Task 15: Add Generation Preview Summary

**Problem**: Users don't see all combinations before generating.

**Implementation**:
- Add summary card below prompts: "Will generate:"
- List: "12 photos (4 images × 3 descriptions)"
- For 'both' mode: "12 photos, 36 videos"
- Truncate if too many combinations

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add summary component
- Or enhance `BulkPreview` component

---

## Priority 4: Polish

### Task 16: Standardize Terminology

**Problem**: Inconsistent use of "prompt/description", "photo/image", "create/generate".

**Implementation**:
- Global find/replace in user-facing strings:
  - "Image" → "Photo" (user-facing)
  - "Prompt" → "Description" (user-facing labels)
  - "Generate" → "Create" (button labels)
- Keep technical terms in code/API

**Files to modify**:
- Multiple frontend files - UI strings only

---

### Task 17: Add Aspect Ratio Visual Preview

**Problem**: Users see "9:16 (Portrait)" but no visual.

**Implementation**:
- Add small aspect ratio icons next to dropdown options
- Or show preview box that changes shape on selection

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Aspect ratio selector

---

### Task 18: Mobile Generate Button Positioning

**Problem**: Generate button scrolls out of view on mobile.

**Implementation**:
- Add sticky footer on mobile with generate button
- Use `lg:hidden` for mobile-only sticky bar
- Include cost estimate in sticky bar

**Files to modify**:
- `frontend/src/pages/Playground.tsx` - Add sticky mobile footer

---

## Technical Notes

### Shared Components to Create
- `ConfirmGenerationModal` - Reusable confirmation dialog
- `ProgressToast` - Toast with progress bar
- `UndoToast` - Toast with undo action

### State Management
- Consider using React Context for global toast/notification state
- Cancel generation requires WebSocket or polling enhancement

### Backend Changes Required
- Task 3: Status filter query param (may already exist)
- Task 4: Cancel endpoint
- Task 6: Search endpoint

## Success Metrics

1. **Reduced support requests** about "wrong prompts being used"
2. **Fewer accidental expensive generations** (track confirmation modal usage)
3. **Improved time-to-first-result** (users find generate button faster)
4. **Higher completion rate** (fewer abandoned generations)

## Dependencies

- Tasks 1-3 can be done independently (no dependencies)
- Task 4 (cancel) requires backend work
- Task 5 (progress) depends on backend providing step-level status
- Tasks 9-18 are independent polish items

## Estimated Effort

| Priority | Tasks | Total Effort |
|----------|-------|--------------|
| P1 (Critical) | 3 tasks | ~4-6 hours |
| P2 (Major) | 5 tasks | ~8-12 hours |
| P3 (Minor) | 6 tasks | ~4-6 hours |
| P4 (Polish) | 3 tasks | ~2-3 hours |

**Total: ~18-27 hours of development work**
