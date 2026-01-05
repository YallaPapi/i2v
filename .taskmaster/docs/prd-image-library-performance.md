# PRD: Image Library Performance Optimization

## Problem Statement
The image library selector in the Playground loads too slowly. Users have to wait an unacceptable amount of time (minutes) to browse and select source images. Current lazy loading implementation is insufficient.

## Goals
- Library should display usable thumbnails within 1-2 seconds
- Scrolling through hundreds of images should be smooth
- Selecting images should be instant

## Technical Solutions to Implement

### 1. Server-Side Thumbnail Generation
Generate small thumbnail versions (150x150px or 200px max dimension) when images are first stored/created.

**Implementation:**
- Add `thumbnail_url` field to the database schema for pipeline outputs
- When saving image URLs from Fal or GPT-image results, also generate a thumbnail
- Use Python Pillow or similar to resize images server-side
- Store thumbnails locally or upload to same storage as originals
- API endpoints that return image lists should include `thumbnail_url`

**Database changes:**
- Add `thumbnail_url` column to relevant tables (pipeline_step_outputs or similar)

### 2. Frontend Virtualization with react-window
Only render images that are currently visible in the viewport. If there are 500 images, only render ~20-30 at a time.

**Implementation:**
- Install `react-window` package
- Replace the current grid of images with a virtualized grid
- Use `FixedSizeGrid` or `VariableSizeGrid` from react-window
- Each cell renders one thumbnail
- As user scrolls, react-window efficiently recycles DOM elements

### 3. Thumbnail-First Loading Strategy
Frontend should request and display thumbnails, not full images, in the library selector.

**Implementation:**
- Update the library API response to include both `url` (full) and `thumbnail_url` (small)
- Image selector component uses `thumbnail_url` for display
- Only load full `url` when user actually selects an image for use
- If `thumbnail_url` is null/missing (legacy images), fall back to full `url` with CSS constraints

### 4. Pagination / Infinite Scroll
Don't load all images metadata at once. Load in batches.

**Implementation:**
- API endpoint accepts `limit` and `offset` parameters
- Frontend loads first 50-100 images initially
- As user scrolls near bottom, fetch next batch
- Or implement "Load More" button

### 5. Image Compression for Thumbnails
Thumbnails should be heavily compressed JPEGs, not PNGs.

**Specifications:**
- Format: JPEG
- Quality: 60-70%
- Max dimension: 200px (maintain aspect ratio)
- Target file size: <20KB per thumbnail

## API Changes

### GET /api/library/images
Current response:
```json
{
  "images": [
    {"url": "https://...", "created_at": "..."}
  ]
}
```

New response:
```json
{
  "images": [
    {
      "url": "https://full-image...",
      "thumbnail_url": "https://thumbnail...",
      "created_at": "..."
    }
  ],
  "total": 500,
  "limit": 50,
  "offset": 0
}
```

### POST /api/library/generate-thumbnails (admin/migration)
One-time migration endpoint to generate thumbnails for existing images that don't have them.

## Frontend Component Changes

### ImageSourceSelector / Library Component
- Use react-window FixedSizeGrid for virtualization
- Display `thumbnail_url` in grid cells
- Implement infinite scroll or pagination
- Show skeleton/placeholder while thumbnails load
- Clicking selects the full `url` for use in pipeline

## Migration Plan
1. Add database column for thumbnail_url
2. Update image creation flow to generate thumbnails
3. Create migration script for existing images
4. Update API to return thumbnail_url
5. Update frontend to use virtualization and thumbnails

## Success Metrics
- Initial library load: <2 seconds to show first thumbnails
- Scroll performance: 60fps, no jank
- Memory usage: Stable even with 1000+ images in library

## Priority
HIGH - This is blocking efficient workflow usage.
