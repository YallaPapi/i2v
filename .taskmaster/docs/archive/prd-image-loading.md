# PRD: Fix Slow Image Loading in Pipeline Results

## Problem Statement

Generated images in the BulkResults component are loading very slowly. The current implementation fetches full-resolution PNG images (~1.3MB each) from the Fal CDN for previews. A thumbnail proxy was added but it's making things worse because:

1. Each thumbnail request must first fetch the full image from Fal CDN
2. Then resize it server-side
3. Then send the resized version to the browser
4. This adds latency instead of reducing it

## Current State

- Generated images are stored on Fal CDN as full-resolution PNGs
- BulkResults.tsx now uses `/api/thumbnail?url=...` for previews
- The thumbnail endpoint fetches the full image, resizes with Pillow, caches in memory
- But the initial load is SLOWER than just loading the original because of the extra hop

## Requirements

### Must Have

1. **Fast preview loading** - Images should appear quickly in the grid (< 1 second)
2. **Full quality on click** - When user clicks, they get the full resolution image
3. **No quality loss** - Downloaded/exported images must be original quality

### Should Have

1. Works without requiring additional storage infrastructure
2. Minimal changes to existing code

## Proposed Solutions

### Option A: Progressive Loading (Recommended)

Instead of using a server-side thumbnail proxy:
1. Use native browser lazy loading (`loading="lazy"`)
2. Use small placeholder blur while loading
3. Load images directly from Fal CDN (they have good edge caching)
4. Use `srcset` for responsive images if Fal supports it

**Pros:** No server changes, uses CDN edge caching, simpler
**Cons:** First load still slow, but subsequent loads cached by browser

### Option B: Remove Thumbnail Proxy, Use CSS Optimization

1. Remove the `/api/thumbnail` usage from BulkResults
2. Use `object-fit: cover` with fixed dimensions (already done)
3. Add `decoding="async"` to img tags
4. Keep `loading="lazy"` for below-fold images
5. Consider using intersection observer for smarter loading

**Pros:** Simple, no extra requests, uses browser optimizations
**Cons:** Large images still load

### Option C: Pre-generate Thumbnails During Pipeline Execution

1. When i2i step completes, generate thumbnails server-side
2. Store thumbnail URLs alongside full-resolution URLs in step outputs
3. Use thumbnail URLs for previews, full URLs for downloads

**Pros:** Fastest loading, thumbnails ready when needed
**Cons:** More complex, requires storage, changes pipeline logic

## Implementation Tasks

### Phase 1: Quick Fix (Option B)

1. Remove thumbnail proxy usage from BulkResults.tsx
2. Add proper image loading attributes (`decoding="async"`, `loading="lazy"`)
3. Verify images load directly from Fal CDN
4. Test performance improvement

### Phase 2: Consider Pre-generation (Option C) if needed

Only if Phase 1 doesn't provide acceptable performance.

## Success Criteria

- Images in BulkResults grid load visibly within 2 seconds on first view
- Opening a group shows images within 1 second (using lazy loading)
- Full-resolution images available on click
- No additional API calls that slow things down

## Files to Modify

- `frontend/src/components/pipeline/BulkResults.tsx`
- `frontend/src/components/pipeline/ImageLibrary.tsx`
- Possibly remove or simplify `/api/thumbnail` endpoint in `app/main.py`
