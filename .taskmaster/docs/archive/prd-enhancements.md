# PRD: Pipeline Categorization & Prompt Enhancement Improvements

## Overview

Two major enhancements to improve usability:
1. **Pipeline Categorization** - Ability to tag, filter, and organize pipeline runs for demos and organization
2. **Prompt Enhancement Overhaul** - Better prompts with category-based expansion options

---

## Feature 1: Pipeline Categorization & Tagging

### Problem
- Users cannot organize or filter their pipeline runs
- No way to hide certain runs or show only specific ones for demos
- All pipelines shown in a flat list with only status filtering

### Requirements

#### 1.1 Database Changes
- Add `tags` field to Pipeline model (JSON array of strings)
- Add `is_favorite` boolean field for quick access
- Add `is_hidden` boolean field to hide from default view
- Add `description` optional text field
- Create migration for new fields

#### 1.2 API Changes
- Update `GET /api/pipelines` to support:
  - `tag` query param for filtering by tag
  - `hidden` query param (default: false) to include hidden pipelines
  - `favorites` query param to show only favorites
- Add `PUT /api/pipelines/{id}/tags` endpoint to update tags
- Add `PUT /api/pipelines/{id}/favorite` toggle endpoint
- Add `PUT /api/pipelines/{id}/hide` toggle endpoint

#### 1.3 Frontend Changes (Jobs.tsx)
- Add tag filter dropdown/chips in header
- Add favorite/star button on each pipeline card
- Add hide button on each pipeline card
- Add "Show Hidden" toggle
- Add inline tag editor (click to add tags)
- Display tags as colored chips on pipeline cards
- Add "Demo Mode" toggle that shows only favorites and hides all others

#### 1.4 Suggested Default Tags
- Provide quick-add for common tags: "demo", "test", "production", "work-in-progress", "best"

---

## Feature 2: Prompt Enhancement Overhaul

### Problem
Current prompt expansion produces overly specific, TikTok-focused prompts with too much irrelevant detail. Example:
- Input: "the woman smiles and waves to the camera"
- Output: "TikTok-style video of the same woman from the image, standing in her room and facing a stationary phone camera..."

The expanded prompts add unwanted context (TikTok, phone camera, tripod, room) instead of just enhancing the motion description.

### Requirements

#### 2.1 New System Prompt for i2v
Replace current generic prompt with motion-focused guidance:
- Focus ONLY on describing the motion/action in more detail
- Keep the same subject from the input image
- Don't add location/setting unless user specifies
- Don't assume camera type or platform (no "TikTok", "phone camera")
- Add natural movement details: speed, arc, gesture nuances
- Keep prompts concise (1-2 sentences max)

#### 2.2 Category-Based Enhancement Options
Add optional checkboxes for enhancement categories:

**For i2v (video):**
- [ ] Camera Movement (add camera pan, zoom, tracking descriptions)
- [ ] Motion Intensity (add speed, smoothness, energy level)
- [ ] Facial Expression (enhance expression transitions)
- [ ] Body Language (detailed gesture/posture descriptions)
- [ ] Environment Interaction (if interacting with surroundings)

**For i2i (image):**
- [ ] Lighting (natural, studio, dramatic, golden hour)
- [ ] Outfit/Clothing (describe attire variations)
- [ ] Pose (standing, sitting, action poses)
- [ ] Background (keep same, blur, change)
- [ ] Style (photorealistic, artistic, vintage)

#### 2.3 Enhancement Modes
Add mode selector:
1. **Quick Improve** - Just make the prompt more descriptive without adding categories
2. **Category-Based** - Use selected checkboxes to guide enhancement
3. **Raw (No Enhancement)** - Use prompt as-is

#### 2.4 Frontend Changes (PromptInput.tsx or Playground.tsx)
- Add enhancement mode selector (Quick/Category/Raw)
- Show category checkboxes when Category mode selected
- Update API call to include selected categories
- Preview enhanced prompt before generation

#### 2.5 Backend Changes (prompt_enhancer.py)
- Update system prompt to be more focused
- Accept `categories` parameter (list of selected categories)
- Generate prompts that only expand on selected aspects
- Reduce verbosity - max 2 sentences per enhanced prompt

#### 2.6 Example of Better Enhancement
**Input:** "the woman smiles and waves to the camera"
**Categories selected:** [Motion Intensity, Facial Expression]

**Better output:**
- "She breaks into a warm, genuine smile and gives a slow, friendly wave with her right hand, the motion gentle and relaxed"
- "Her face lights up with a bright smile as she waves enthusiastically, her hand moving in a wide, cheerful arc"
- "A soft smile spreads across her face as she raises her hand in a casual wave, the gesture natural and unhurried"

---

## Technical Notes

### Files to Modify
- `app/models.py` - Add Pipeline fields (tags, is_favorite, is_hidden, description)
- `app/schemas.py` - Update Pipeline schemas
- `app/routers/pipelines.py` - Add filtering and toggle endpoints
- `app/services/prompt_enhancer.py` - Overhaul system prompts and add category support
- `frontend/src/pages/Jobs.tsx` - Add tag filtering, favorites, hide, demo mode
- `frontend/src/components/pipeline/PromptInput.tsx` - Add enhancement mode and category UI

### Migration Required
- Alembic migration for new Pipeline columns with defaults

---

## Success Criteria
1. Users can tag pipelines and filter by tags
2. Users can mark favorites and use "Demo Mode" to show only those
3. Users can hide pipelines from default view
4. Prompt enhancement produces focused, motion-centric prompts
5. Category checkboxes allow fine-grained control over what gets enhanced
6. Enhanced prompts are concise (1-2 sentences) not verbose paragraphs
