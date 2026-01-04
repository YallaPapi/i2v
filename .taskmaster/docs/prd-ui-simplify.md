# PRD: Simplify Playground UI Tabs

## Problem Statement

The Playground has 5 tabs:
- Edit Image (i2i)
- Animate (i2v)
- Full Pipeline (pipeline)
- Bulk
- Carousel

The Bulk tab makes the first 3 tabs redundant because:
- Bulk "Just Photos" = Edit Image functionality
- Bulk "Just Videos" = Animate functionality
- Bulk "Photos + Videos" = Full Pipeline functionality

Having all these tabs is confusing and unnecessary.

## Requirements

### Must Have

1. Remove redundant tabs (i2i, i2v, pipeline)
2. Keep Bulk as the main generation tab
3. Keep Carousel as a separate specialized mode
4. Rename "Bulk" to something more user-friendly like "Create" or "Generate"

### Should Have

1. Default to the simplified Bulk mode
2. Clean up any unused code from removed modes

## Implementation Tasks

1. Remove "Edit Image" (i2i) tab from Playground.tsx
2. Remove "Animate" (i2v) tab from Playground.tsx
3. Remove "Full Pipeline" (pipeline) tab from Playground.tsx
4. Rename "Bulk" tab to "Create" or "Generate"
5. Remove unused mode-specific code (handleGenerate for non-bulk modes)
6. Keep Carousel tab for story content creation
7. Set "bulk" as the only/default mode
8. Restart frontend to verify changes

## Files to Modify

- `frontend/src/pages/Playground.tsx`

## Success Criteria

- Only 2 tabs visible: Create/Generate and Carousel
- All photo/video generation works through the streamlined UI
- No console errors
- Code is cleaner and easier to maintain
