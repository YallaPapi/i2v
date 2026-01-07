# UX Evaluation Report - i2v Frontend

## Executive Summary

- **Total issues found**: 28
- **Critical (4)**: 2
- **Major (3)**: 8
- **Minor (2)**: 12
- **Cosmetic (1)**: 6
- **Top 3 priority fixes**:
  1. Two-stage prompt flow confusion (Generated vs Active prompts)
  2. No confirmation before expensive generation operations
  3. Missing progress details during generation

---

## Detailed Findings

### Playground Page

---

#### Issue 1: Two-Stage Prompt Flow is Confusing

- **Heuristic**: H1 (Visibility of System Status), H6 (Recognition over Recall)
- **Severity**: 4 (Critical)
- **Location**: AI Prompt Builder section → Photo Prompts section
- **Problem**: Users generate prompts in the "AI Prompt Builder" collapsible section, but these prompts are NOT automatically added to the actual prompt queue. Users must click "Add to Photo Prompts" to transfer them. The generated prompts appear in a read-only textarea that looks like the final output, leading users to believe generation will use these prompts.
- **Impact**: Users expect their generated prompts to be used but end up with OLD prompts being sent to the API. This caused a real user confusion incident where prompts said "cozy bedroom" but images showed NYC because old prompts were still in the active queue.
- **Recommendation**:
  - Option A: Auto-add generated prompts to the queue with a toast notification
  - Option B: Make the visual distinction much stronger - generated prompts should appear in a "staging" state with obvious visual treatment (different background, prominent warning)
  - Option C: Add a confirmation dialog if user tries to generate without adding staged prompts
- **Effort**: Medium

---

#### Issue 2: No Confirmation Before Expensive Operations

- **Heuristic**: H5 (Error Prevention)
- **Severity**: 4 (Critical)
- **Location**: "Create Photos + Videos" button
- **Problem**: Clicking generate immediately starts the pipeline with no confirmation. Users can accidentally trigger $50+ generations with a single click. The cost estimate is shown in a separate card but there's no "Are you sure?" prompt.
- **Impact**: Accidental expensive API calls, potential financial loss, anxiety about clicking the generate button.
- **Recommendation**: Add a confirmation modal for generations over $1 showing: total cost, number of outputs, and breakdown by type. Include a "Don't ask again for small jobs" checkbox.
- **Effort**: Low

---

#### Issue 3: Upload Progress Not Granular

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 3 (Major)
- **Location**: ImageUploadZone component
- **Problem**: When uploading multiple files, user only sees a generic "Uploading images..." spinner. No indication of how many files uploaded, which one is processing, or estimated time remaining.
- **Impact**: Users don't know if upload is stuck, how long to wait, or if they can continue adding more files.
- **Recommendation**: Show progress like "Uploading 3 of 10 images..." with a progress bar and estimated time remaining.
- **Effort**: Low

---

#### Issue 4: Generation Progress Lacks Details

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 3 (Major)
- **Location**: BulkProgress component during generation
- **Problem**: During generation, users see "Processing..." but don't know: which step is running (I2I vs I2V), how many completed, estimated time remaining, or if any errors occurred.
- **Impact**: Users can't assess if generation is proceeding normally or stuck. Anxiety during long-running jobs.
- **Recommendation**: Show detailed progress: "Step 3 of 12: Generating video from photo 2... (est. 2 min remaining)". Show real-time thumbnails of completed outputs.
- **Effort**: Medium

---

#### Issue 5: Model Differences Not Clear to New Users

- **Heuristic**: H2 (Match Between System and Real World)
- **Severity**: 3 (Major)
- **Location**: ModelSelector dropdown
- **Problem**: Users see 11 I2I models and 13 I2V models with technical names like "FLUX.2 Dev", "Kling v2.5 Turbo Pro", "Nano Banana". The only context is a one-line description and price. Users can't easily understand which model to choose for their use case.
- **Impact**: Analysis paralysis, suboptimal model selection, or just sticking with defaults without understanding alternatives.
- **Recommendation**:
  - Add model comparison tooltip or modal showing: quality samples, speed comparison, best use cases
  - Group models by use case ("Best for portraits", "Budget-friendly", "Fastest")
  - Show visual quality indicators (stars, sample outputs)
- **Effort**: Medium

---

#### Issue 6: FLUX Settings Overwhelming

- **Heuristic**: H8 (Aesthetic and Minimalist Design), H7 (Flexibility and Efficiency)
- **Severity**: 2 (Minor)
- **Location**: FLUX Settings panel in sidebar
- **Problem**: When a FLUX model is selected, users see 5-7 technical sliders (Strength, Guidance Scale, Inference Steps, Seed, Scheduler, Acceleration, Prompt Expansion). Most users don't understand these parameters.
- **Impact**: Cognitive overload, fear of breaking settings, or ignoring advanced controls entirely.
- **Recommendation**:
  - Hide advanced settings behind "Advanced Options" toggle, collapsed by default
  - Add presets: "Quality First", "Speed First", "Balanced"
  - Show a "?" tooltip with simple explanations for each parameter
- **Effort**: Low

---

#### Issue 7: No Way to Cancel Running Generation

- **Heuristic**: H3 (User Control and Freedom)
- **Severity**: 3 (Major)
- **Location**: During generation (BulkProgress)
- **Problem**: Once generation starts, there's no cancel button. Users must wait for completion or refresh the page (losing state).
- **Impact**: Users are trapped if they made a mistake or need to stop. Wasted API costs on unwanted generations.
- **Recommendation**: Add a "Cancel Generation" button that stops further API calls. Show warning about partial results.
- **Effort**: Medium

---

#### Issue 8: Undo/Clear Operations Are Destructive

- **Heuristic**: H3 (User Control and Freedom)
- **Severity**: 2 (Minor)
- **Location**: MultiPromptInput "Clear All" button, Image delete buttons
- **Problem**: Clicking the trash icon clears all prompts instantly with no confirmation. Deleting uploaded images is also instant. No undo functionality.
- **Impact**: Accidental loss of carefully crafted prompts or uploaded images.
- **Recommendation**:
  - Add confirmation for "Clear All" operations
  - Implement undo toast: "Cleared 5 prompts. Undo?"
  - For images, show "X images deleted" with undo option
- **Effort**: Low

---

#### Issue 9: Terminology Inconsistency

- **Heuristic**: H4 (Consistency and Standards)
- **Severity**: 2 (Minor)
- **Location**: Throughout Playground
- **Problem**: Mixed terminology:
  - "Prompts" vs "Descriptions" vs "Motions"
  - "Photo" vs "Image" vs "I2I"
  - "Create" vs "Generate"
  - "Run Name" vs "Pipeline Name" vs "Job Name"
- **Impact**: Cognitive load, confusion about whether different terms mean different things.
- **Recommendation**: Standardize terminology:
  - Use "Photo" for images, "Video" for videos
  - Use "Description" for user-facing, reserve "Prompt" for technical contexts
  - Use "Create" consistently for the action button
- **Effort**: Low

---

#### Issue 10: Prompt Count Feedback Only at Bottom

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 2 (Minor)
- **Location**: MultiPromptInput component
- **Problem**: The "X prompts" badge is shown at the top-right of the card header, but the count calculation ("Will create X photos") is at the bottom after the textarea. Users entering prompts don't immediately see the output count changing.
- **Impact**: Users must scroll down to see the impact of their changes, breaking flow.
- **Recommendation**: Show live count near the prompt input area, or use a sticky footer showing total outputs.
- **Effort**: Low

---

#### Issue 11: Results Appear Below the Fold

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 2 (Minor)
- **Location**: BulkResults component
- **Problem**: When generation completes, results appear at the bottom of the main content area. Users must scroll down to see outputs, especially if they were watching the settings sidebar.
- **Impact**: Users may not notice generation completed, miss results, or think something failed.
- **Recommendation**:
  - Auto-scroll to results when generation completes
  - Show a toast notification: "Generation complete! 12 outputs ready" with "View Results" button
- **Effort**: Low

---

#### Issue 12: No Keyboard Shortcuts

- **Heuristic**: H7 (Flexibility and Efficiency)
- **Severity**: 2 (Minor)
- **Location**: Global
- **Problem**: No keyboard shortcuts for common actions (generate, clear, undo, navigate tabs).
- **Impact**: Power users must use mouse for everything, slower workflow.
- **Recommendation**: Add shortcuts:
  - Cmd/Ctrl + Enter: Start generation
  - Cmd/Ctrl + Z: Undo last action
  - Tab: Navigate between input sections
  - Esc: Cancel current operation
- **Effort**: Medium

---

#### Issue 13: Recent Prompts Hidden by Default

- **Heuristic**: H6 (Recognition over Recall)
- **Severity**: 2 (Minor)
- **Location**: "Recent" button on prompt cards
- **Problem**: Recent prompts are hidden behind a toggle button. Users must remember they exist and click to expand. The button shows an up/down chevron which isn't immediately recognizable as "show history".
- **Impact**: Users re-type prompts they've used before instead of reusing.
- **Recommendation**:
  - Show last 2-3 recent prompts by default, with "Show more" link
  - Use clearer icon (clock with "5 recent" label)
- **Effort**: Low

---

#### Issue 14: No Help Text for Empty States

- **Heuristic**: H10 (Help and Documentation)
- **Severity**: 2 (Minor)
- **Location**: Empty prompt textareas, empty image upload zone
- **Problem**: Placeholder text exists but no in-context help explaining what good prompts look like or what image formats work best.
- **Impact**: New users don't know how to write effective prompts.
- **Recommendation**: Add expandable "Tips for better prompts" section or tooltip with examples of good vs bad prompts.
- **Effort**: Low

---

#### Issue 15: No Preview of What Will Be Generated

- **Heuristic**: H5 (Error Prevention)
- **Severity**: 3 (Major)
- **Location**: Before generation
- **Problem**: Users see source images and prompts separately but can't preview the combinations that will be generated. For "Both" mode, the multiplication (images × photo prompts × video prompts) is opaque.
- **Impact**: Unexpected outputs, wasted generations, confusion about what was created.
- **Recommendation**: Add a "Preview Matrix" showing all combinations before generation, or at minimum a clear summary: "Will generate: Photo 1 × Prompt 1, Photo 1 × Prompt 2, ..."
- **Effort**: Medium

---

#### Issue 16: Aspect Ratio Selection Not Visual

- **Heuristic**: H6 (Recognition over Recall)
- **Severity**: 1 (Cosmetic)
- **Location**: Aspect ratio dropdown
- **Problem**: Users see text options like "9:16 (Portrait)" but no visual preview of what that looks like.
- **Impact**: Users must mentally visualize aspect ratios.
- **Recommendation**: Show aspect ratio icons/previews next to each option.
- **Effort**: Low

---

#### Issue 17: Settings Not Persisted Across Sessions

- **Heuristic**: H7 (Flexibility and Efficiency)
- **Severity**: 1 (Cosmetic)
- **Location**: Various settings (prompts, some models)
- **Problem**: While some settings (mode, FLUX params) are persisted to localStorage, prompts and uploaded images are not. Users lose work on page refresh.
- **Impact**: Lost work, frustration when accidentally refreshing.
- **Recommendation**:
  - Auto-save draft state every 30 seconds
  - Show "Unsaved changes" indicator
  - Prompt before leaving page with unsaved work
- **Effort**: Medium

---

### Jobs Page

---

#### Issue 18: Status Filter Not Applied

- **Heuristic**: H4 (Consistency and Standards), H5 (Error Prevention)
- **Severity**: 3 (Major)
- **Location**: Status filter dropdown in Jobs page header
- **Problem**: The status filter dropdown exists but examining the code shows `statusFilter` is stored in state but never passed to the `usePipelines` query params (line 358-364). The filter is a no-op.
- **Impact**: Users expect filtering to work, but it doesn't. Silent failure.
- **Recommendation**: Actually implement the status filter by passing it to the query params.
- **Effort**: Low (Bug fix)

---

#### Issue 19: Hover Preview Only for Images

- **Heuristic**: H4 (Consistency and Standards)
- **Severity**: 2 (Minor)
- **Location**: Output grid hover behavior
- **Problem**: Image outputs show a hover preview (full-res popup), but video outputs don't have an equivalent preview behavior. Videos play on hover but in-grid at small size.
- **Impact**: Inconsistent experience between image and video outputs.
- **Recommendation**: Add video preview popup on hover with larger playback area, or a "Quick Preview" overlay.
- **Effort**: Medium

---

#### Issue 20: Demo Mode Naming Confusing

- **Heuristic**: H2 (Match Between System and Real World)
- **Severity**: 2 (Minor)
- **Location**: "Demo Mode" button
- **Problem**: "Demo Mode" actually means "Show Favorites Only". The name suggests some kind of demonstration or preview mode.
- **Impact**: Users don't understand what the button does until they click it.
- **Recommendation**: Rename to "Favorites Only" with a star icon and tooltip.
- **Effort**: Low

---

#### Issue 21: Hidden Jobs Toggle Ambiguous

- **Heuristic**: H2 (Match Between System and Real World)
- **Severity**: 1 (Cosmetic)
- **Location**: "Hidden" / "Showing Hidden" button
- **Problem**: Button label changes between "Hidden" (when hidden jobs are NOT shown) and "Showing Hidden" (when they are shown). The EyeOff/Eye icons add clarity but the text is still confusing.
- **Impact**: Users may not understand the current state.
- **Recommendation**: Use consistent labels: "Show Hidden Jobs" (checkbox style) or "Include Hidden" toggle.
- **Effort**: Low

---

#### Issue 22: No Bulk Actions for Multiple Pipelines

- **Heuristic**: H7 (Flexibility and Efficiency)
- **Severity**: 2 (Minor)
- **Location**: Pipeline list
- **Problem**: Users can select outputs within a pipeline but cannot select multiple pipelines for bulk operations (delete, tag, export).
- **Impact**: Tedious one-by-one operations when managing many jobs.
- **Recommendation**: Add pipeline-level checkboxes with bulk actions: "Delete Selected", "Tag Selected", "Export Selected".
- **Effort**: Medium

---

#### Issue 23: Download Progress Not Visible Enough

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 2 (Minor)
- **Location**: Download button during multi-file download
- **Problem**: Download progress shows "Downloading 3/10" inline in the button, which is small and easy to miss. No progress bar.
- **Impact**: Users may click again thinking nothing happened.
- **Recommendation**: Show a modal or toast with download progress bar and file list.
- **Effort**: Low

---

#### Issue 24: No Search Functionality

- **Heuristic**: H7 (Flexibility and Efficiency)
- **Severity**: 3 (Major)
- **Location**: Jobs page
- **Problem**: No way to search jobs by name, prompt content, or date range. Users with many jobs must scroll through all of them.
- **Impact**: Finding specific jobs is time-consuming with large history.
- **Recommendation**: Add search bar with filters for: name, prompt text, date range, model used.
- **Effort**: Medium

---

#### Issue 25: Tag Input UX Issues

- **Heuristic**: H3 (User Control and Freedom)
- **Severity**: 1 (Cosmetic)
- **Location**: Tag input inline editing
- **Problem**: Tag input field is very small (w-20), appears inline with quick tag buttons. Easy to miss or accidentally dismiss.
- **Impact**: Frustrating tag creation experience.
- **Recommendation**: Use a dropdown/popover for tag management with larger input area.
- **Effort**: Low

---

### Global UI

---

#### Issue 26: No Loading State for Navigation

- **Heuristic**: H1 (Visibility of System Status)
- **Severity**: 1 (Cosmetic)
- **Location**: Navigation between pages
- **Problem**: No loading indicator when navigating between Playground and Jobs pages.
- **Impact**: On slow connections, users may not know if click registered.
- **Recommendation**: Add route transition loading indicator (top progress bar or spinner).
- **Effort**: Low

---

#### Issue 27: Health Status Indicator Not Explained

- **Heuristic**: H2 (Match Between System and Real World)
- **Severity**: 1 (Cosmetic)
- **Location**: Header health status dot
- **Problem**: There's a colored dot in the header indicating backend health, but no label or tooltip explaining what it means.
- **Impact**: Users see red dot but don't know what action to take.
- **Recommendation**: Add tooltip: "Backend Status: Connected" or "Backend Status: Disconnected - Some features may not work".
- **Effort**: Low

---

#### Issue 28: Mobile Responsiveness Limited

- **Heuristic**: H8 (Aesthetic and Minimalist Design)
- **Severity**: 2 (Minor)
- **Location**: Playground page on mobile
- **Problem**: The 3-column layout (`lg:grid-cols-3`) collapses to single column on mobile, but the sidebar (model settings, cost preview, generate button) moves to the bottom. Users must scroll past all inputs to find the generate button.
- **Impact**: Poor mobile experience, generate button not accessible.
- **Recommendation**: Make generate button sticky on mobile, or add floating action button.
- **Effort**: Medium

---

## User Flow Analysis

### Primary Flow: Upload → Generate → Review

```
1. User lands on Playground
2. User uploads images OR selects from library
   - Issue: No indication of optimal image size/format
3. User selects bulk mode (Photos/Videos/Both)
   - Good: Clear visual distinction between options
4. User enters prompts
   - Issue: May use AI Prompt Builder but forget to add to queue
5. User selects models and settings
   - Issue: Model selection overwhelming
   - Issue: FLUX settings visible but rarely needed
6. User reviews cost estimate
   - Good: Cost shown clearly in sidebar
7. User clicks Generate
   - Issue: No confirmation for expensive jobs
8. User waits for generation
   - Issue: Limited progress visibility
   - Issue: No cancel option
9. User reviews results
   - Issue: Results below the fold
10. User downloads outputs
    - Good: Batch download available
```

### Friction Points Identified

| Step | Friction | Severity | Fix |
|------|----------|----------|-----|
| 4 | Generated prompts not auto-added | Critical | Auto-add or clear warning |
| 5 | Too many model options | Major | Group by use case |
| 5 | FLUX settings visible by default | Minor | Hide in "Advanced" |
| 7 | No confirmation before generate | Critical | Add confirmation modal |
| 8 | No cancel button | Major | Add cancel functionality |
| 9 | Must scroll to see results | Minor | Auto-scroll or toast |

---

## Prioritized Recommendations

### Quick Wins (Low Effort, High Impact)

1. **Add confirmation modal for generation** - Prevents expensive mistakes
2. **Fix status filter bug on Jobs page** - Currently non-functional
3. **Rename "Demo Mode" to "Favorites Only"** - Clarity
4. **Add upload progress indicator** - "Uploading 3/10..."
5. **Add undo for Clear All prompts** - Prevent accidental loss
6. **Show results notification** - Toast when generation completes
7. **Add tooltip to health indicator** - Explain backend status

### Medium Effort Improvements

1. **Redesign prompt builder flow** - Auto-add or clear visual separation
2. **Add cancel button during generation** - User control
3. **Improve model selector** - Group by use case, add previews
4. **Add search to Jobs page** - Find jobs by name/prompt
5. **Hide FLUX settings in "Advanced"** - Reduce cognitive load
6. **Auto-scroll to results** - Better visibility
7. **Add generation preview matrix** - Show all combinations

### Major Overhauls

1. **Implement keyboard shortcuts system** - Power user efficiency
2. **Add draft auto-save** - Prevent lost work
3. **Mobile-first redesign** - Sticky generate button
4. **Bulk operations for Jobs** - Multi-select pipelines
5. **Model comparison feature** - Help users choose

---

## Implementation Priority Matrix

| Priority | Issue # | Title | Effort | Impact |
|----------|---------|-------|--------|--------|
| P1 | 1 | Two-stage prompt flow | Medium | Critical |
| P1 | 2 | No confirmation for generate | Low | Critical |
| P1 | 18 | Status filter broken | Low | Major |
| P2 | 4 | Generation progress details | Medium | Major |
| P2 | 7 | No cancel button | Medium | Major |
| P2 | 5 | Model differences unclear | Medium | Major |
| P2 | 24 | No search in Jobs | Medium | Major |
| P2 | 15 | No preview matrix | Medium | Major |
| P3 | 3 | Upload progress | Low | Minor |
| P3 | 6 | FLUX settings overwhelming | Low | Minor |
| P3 | 8 | Destructive clear | Low | Minor |
| P3 | 11 | Results below fold | Low | Minor |
| P3 | 13 | Recent prompts hidden | Low | Minor |
| P3 | 20 | Demo Mode naming | Low | Minor |

---

## Appendix: Files Analyzed

- `frontend/src/pages/Playground.tsx` - Main generation interface (1809 lines)
- `frontend/src/pages/Jobs.tsx` - Pipeline history (503 lines)
- `frontend/src/components/pipeline/ModelSelector.tsx` - Model selection (320 lines)
- `frontend/src/components/pipeline/ImageUploadZone.tsx` - Image upload (251 lines)
- `frontend/src/components/pipeline/MultiPromptInput.tsx` - Prompt input (118 lines)
- `frontend/src/components/Layout.tsx` - Global layout/nav
- `frontend/src/App.tsx` - Routing

---

*Report generated: 2026-01-07*
*Evaluation framework: Nielsen's 10 Usability Heuristics*
