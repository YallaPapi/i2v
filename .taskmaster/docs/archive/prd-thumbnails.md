# PRD: Fix Extremely Slow Image Loading in Results Grid

## Problem

Generated images in BulkResults take forever to load. The grid shows maybe 20+ images and it takes 10+ seconds for them all to appear. Normal websites show image grids instantly.

## Current Setup

- Images are generated via Fal.ai API (GPT Image, etc.)
- Generated images are stored on Fal CDN as full-resolution PNGs
- Image URLs look like: `https://fal.media/files/...`
- Frontend displays images in a grid using `<img src={url} />`
- We tried a server-side thumbnail proxy but it made things worse (extra hop)
- We added `loading="lazy"` and `decoding="async"` but still slow
- Each image is ~1-2MB PNG file

## What We Need

- Images should load fast in the preview grid (like normal websites)
- Full quality images still available for download
- Works with our existing Fal.ai integration

## Files Involved

- `frontend/src/components/pipeline/BulkResults.tsx` - displays image grid
- `frontend/src/components/pipeline/ImageLibrary.tsx` - displays image library
- `app/services/pipeline_executor.py` - executes pipeline steps
- `app/routers/pipelines.py` - API endpoints
- `app/fal_upload.py` - uploads to Fal storage
