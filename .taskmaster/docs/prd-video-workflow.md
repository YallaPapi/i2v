# PRD: Video Creation Workflow Discovery Issues

## Problem Statement

Users cannot find how to create videos from their generated images. The current UX has multiple discoverability problems that make the video creation workflow non-obvious and frustrating.

## User Pain Points

### 1. "Animate Selected" is Hidden and Non-Obvious

When a user generates images in the Playground, they want to then create videos from those images. The current workflow requires:
1. Generate images first
2. Scroll down to Results section
3. Click "Select Images" button (easy to miss)
4. Select individual images with checkboxes
5. Have video motion prompts ALREADY entered in the form above
6. Click "Animate Selected" button

Problems:
- The "Select Images" button is in the results area, not where the user expects it
- If they haven't entered motion prompts first, they get an error alert
- The workflow feels backwards (generate images, THEN go back up to enter motion prompts, THEN scroll down to select images)

### 2. Cannot Access Previously Generated Images

If a user closes the browser or navigates away, they lose access to their generated images for video creation. There is an `ImageLibrary` component that shows previously generated images, but it's NOT accessible in the Playground UI.

The user expects to:
- See a library of their past generated images
- Select images from that library for video creation
- Not have to regenerate images they already made

### 3. Jobs Page Shows 0 for Video/Image Jobs

The Jobs page has three tabs: Pipelines, Video Jobs, Image Jobs. The user generates content through the Playground (which uses the Pipeline system), but:
- All their content appears under "Pipelines"
- Video Jobs always shows (0)
- Image Jobs always shows (0)

This is confusing because the tabs suggest these are separate concepts when in reality the Playground only creates Pipelines.

## Expected Behavior

Users should be able to:
1. Generate images in Playground
2. Immediately see a clear option to "Create Videos from These"
3. Access previously generated images from any session
4. Understand where their generated content lives in the Jobs page

## Technical Context

- `ImageLibrary` component exists at `frontend/src/components/pipeline/ImageLibrary.tsx`
- `ImageSourceSelector` wrapper exists to switch between upload and library
- BulkResults has `onAnimateSelected` callback that works
- Playground.tsx doesn't import or use ImageLibrary
- Jobs page queries separate VideoJob/ImageJob models that aren't populated by Pipelines
