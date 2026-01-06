"""Migrate existing images/videos from Fal CDN to R2."""

import asyncio
import sqlite3
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.services.r2_cache import cache_image, cache_video, get_s3_client
from app.services.thumbnail import generate_thumbnail


async def migrate_step_outputs(step_id: int, outputs: dict) -> dict:
    """Migrate a single step's outputs to R2."""
    updated = False
    items = outputs.get("items", [])
    thumbnail_urls = outputs.get("thumbnail_urls", [])

    # Migrate items (images/videos)
    for i, item in enumerate(items):
        url = item.get("url", "")
        item_type = item.get("type", "image")

        # Skip if already on R2
        if "r2.dev" in url:
            print(f"  [skip] Item {i} already on R2")
            continue

        # Skip if not a fal URL
        if "fal.media" not in url and "fal.ai" not in url:
            print(f"  [skip] Item {i} not a fal URL: {url[:50]}")
            continue

        print(f"  [cache] Item {i} ({item_type}): {url[:60]}...")

        if item_type == "video":
            cached_url = await cache_video(url)
        else:
            cached_url = await cache_image(url)

        if cached_url:
            item["url"] = cached_url
            item["original_url"] = url  # Keep original as backup
            updated = True
            print(f"    -> {cached_url[:60]}...")
        else:
            print("    -> FAILED to cache")

    # Migrate/generate thumbnails
    new_thumbnail_urls = []
    for i, item in enumerate(items):
        if item.get("type") == "video":
            # Videos don't have thumbnails in current system
            if i < len(thumbnail_urls):
                new_thumbnail_urls.append(thumbnail_urls[i])
            continue

        # Check if thumbnail exists and is on R2
        if i < len(thumbnail_urls) and thumbnail_urls[i]:
            thumb_url = thumbnail_urls[i]
            if "r2.dev" in thumb_url:
                print(f"  [skip] Thumbnail {i} already on R2")
                new_thumbnail_urls.append(thumb_url)
                continue

        # Generate new thumbnail to R2
        original_url = item.get("original_url", item.get("url", ""))
        if original_url:
            print(f"  [thumb] Generating thumbnail for item {i}...")
            thumb_url = await generate_thumbnail(original_url)
            if thumb_url:
                new_thumbnail_urls.append(thumb_url)
                updated = True
                print(f"    -> {thumb_url[:60]}...")
            else:
                new_thumbnail_urls.append(
                    thumbnail_urls[i] if i < len(thumbnail_urls) else None
                )
                print("    -> FAILED")
        else:
            new_thumbnail_urls.append(None)

    if new_thumbnail_urls:
        outputs["thumbnail_urls"] = new_thumbnail_urls

    return outputs if updated else None


async def main():
    # Verify R2 is configured
    client = get_s3_client()
    if not client:
        print("ERROR: R2 is not configured. Check your .env file.")
        return

    print("R2 configured successfully.\n")

    # Connect to database
    conn = sqlite3.connect("wan_jobs.db")
    cursor = conn.cursor()

    # Get all steps with outputs
    cursor.execute(
        """
        SELECT ps.id, ps.pipeline_id, ps.outputs, p.name
        FROM pipeline_steps ps
        JOIN pipelines p ON ps.pipeline_id = p.id
        WHERE ps.outputs IS NOT NULL
        ORDER BY ps.id DESC
    """
    )

    rows = cursor.fetchall()
    print(f"Found {len(rows)} steps with outputs to migrate.\n")

    migrated_count = 0
    failed_count = 0

    for step_id, pipeline_id, outputs_json, pipeline_name in rows:
        outputs = json.loads(outputs_json)
        items_count = len(outputs.get("items", []))

        if items_count == 0:
            continue

        print(f"\n[Step {step_id}] Pipeline '{pipeline_name}' ({items_count} items)")

        try:
            updated_outputs = await migrate_step_outputs(step_id, outputs)

            if updated_outputs:
                # Update database
                cursor.execute(
                    "UPDATE pipeline_steps SET outputs = ? WHERE id = ?",
                    (json.dumps(updated_outputs), step_id),
                )
                conn.commit()
                migrated_count += 1
                print("  -> Updated in database")
            else:
                print("  -> No changes needed")

        except Exception as e:
            print(f"  -> ERROR: {e}")
            failed_count += 1

    conn.close()

    print(f"\n{'='*50}")
    print("Migration complete!")
    print(f"  Migrated: {migrated_count} steps")
    print(f"  Failed: {failed_count} steps")
    print(f"  Skipped: {len(rows) - migrated_count - failed_count} steps")


if __name__ == "__main__":
    asyncio.run(main())
