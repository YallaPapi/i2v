#!/usr/bin/env python
"""Bulk video generation from local images folder and prompts file."""
import argparse
import asyncio
import itertools
import httpx
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.fal_upload import upload_image, scan_images_dir
import structlog

logger = structlog.get_logger()


def load_prompts(prompts_file: Path) -> list[str]:
    """Load prompts from file. Each prompt separated by blank line or ---."""
    content = prompts_file.read_text(encoding="utf-8")

    # Split by --- or double newline
    if "---" in content:
        prompts = [p.strip() for p in content.split("---")]
    else:
        # Split by double newline
        prompts = [p.strip() for p in content.split("\n\n")]

    # Filter empty and comments
    return [p for p in prompts if p and not p.startswith("#")]


def submit_job(api_url: str, image_url: str, prompt: str, resolution: str,
               duration: int, model: str) -> dict:
    """Submit a single job to the API."""
    payload = {
        "image_url": image_url,
        "motion_prompt": prompt,
        "resolution": resolution,
        "duration_sec": duration,
        "model": model,
    }
    response = httpx.post(f"{api_url}/jobs", json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


async def process_images_dir(images_dir: Path, prompts: list[str],
                              one_to_one: bool) -> list[tuple[str, str, Path]]:
    """
    Scan images dir, upload to Fal CDN, and pair with prompts.

    Returns list of (fal_url, prompt, local_path) tuples.
    """
    images = scan_images_dir(images_dir)

    if not images:
        raise ValueError(f"No images found in {images_dir}")

    print(f"Found {len(images)} images in {images_dir}")

    # Validate one-to-one mode
    if one_to_one:
        if len(images) != len(prompts):
            raise ValueError(
                f"One-to-one mode requires equal counts: "
                f"{len(images)} images vs {len(prompts)} prompts"
            )
        pairs = list(zip(images, prompts))
    else:
        # All combinations (cartesian product)
        pairs = list(itertools.product(images, prompts))

    print(f"Will create {len(pairs)} jobs ({'one-to-one' if one_to_one else 'all combinations'})")

    # Upload images and build final list
    result = []
    uploaded = {}  # Cache: local_path -> fal_url

    for img_path, prompt in pairs:
        img_str = str(img_path)
        if img_str not in uploaded:
            print(f"  Uploading {img_path.name}...")
            fal_url = await upload_image(img_path)
            uploaded[img_str] = fal_url
        result.append((uploaded[img_str], prompt, img_path))

    print(f"Uploaded {len(uploaded)} unique images")
    return result


async def async_main(args):
    """Async main entry point."""
    # Load prompts
    prompts = load_prompts(args.prompts_file)
    print(f"Loaded {len(prompts)} prompts from {args.prompts_file}\n")

    if not prompts:
        print("Error: No prompts found")
        sys.exit(1)

    # Build job pairs
    if args.images_dir:
        # Local folder mode - upload images first
        pairs = await process_images_dir(
            args.images_dir, prompts, args.one_to_one
        )
    elif args.image_url:
        # Single URL mode (backward compatible)
        pairs = [(args.image_url, p, None) for p in prompts]
    else:
        print("Error: Must specify --images-dir or --image-url")
        sys.exit(1)

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for i, (url, prompt, local) in enumerate(pairs, 1):
            src = local.name if local else url[:50]
            print(f"[{i}] {src} -> {prompt[:60]}...")
        print(f"\nWould submit {len(pairs)} jobs")
        return

    # Submit jobs
    print(f"\nSubmitting {len(pairs)} jobs...")
    jobs = []
    for i, (fal_url, prompt, local_path) in enumerate(pairs, 1):
        src = local_path.name if local_path else fal_url[:40]
        print(f"[{i}/{len(pairs)}] {src} ({args.model}): {prompt[:40]}...")
        try:
            job = submit_job(
                args.api_url, fal_url, prompt,
                args.resolution, args.duration, args.model
            )
            jobs.append(job)
            print(f"    -> Job ID: {job['id']}")
        except Exception as e:
            print(f"    -> Error: {e}")

    print(f"\n{len(jobs)}/{len(pairs)} jobs submitted successfully")
    if jobs:
        print(f"Job IDs: {[j['id'] for j in jobs]}")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk generate videos from local images and prompts"
    )
    parser.add_argument("prompts_file", type=Path, help="Path to prompts file")

    # Image source (one required)
    img_group = parser.add_mutually_exclusive_group(required=True)
    img_group.add_argument(
        "--images-dir", type=Path,
        help="Local directory containing images (jpg/png/webp)"
    )
    img_group.add_argument(
        "--image-url",
        help="Single image URL to use for all prompts"
    )

    # Pairing mode
    parser.add_argument(
        "--one-to-one", action="store_true",
        help="Pair images with prompts 1:1 instead of all combinations"
    )

    # Job options
    parser.add_argument(
        "--resolution", default="1080p",
        choices=["480p", "720p", "1080p"]
    )
    parser.add_argument(
        "--duration", type=int, default=5,
        choices=[5, 10]
    )
    parser.add_argument(
        "--model", default="wan",
        choices=["wan", "wan21", "wan22", "wan-pro", "kling", "veo2", "veo31-fast", "veo31", "veo31-flf", "veo31-fast-flf"],
        help="Model to use"
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List available models with pricing and exit"
    )

    # Other options
    parser.add_argument(
        "--api-url", default="http://127.0.0.1:8000",
        help="API base URL"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be submitted without actually submitting"
    )

    args = parser.parse_args()

    # List models and exit
    if args.list_models:
        print("Available models and pricing:\n")
        print("MODEL          | PRICING")
        print("---------------|------------------------------------------")
        print("wan            | 480p=$0.05/s, 720p=$0.10/s, 1080p=$0.15/s")
        print("wan21          | 480p=$0.20/vid, 720p=$0.40/vid")
        print("wan22          | 480p=$0.04/s, 580p=$0.06/s, 720p=$0.08/s")
        print("wan-pro        | 1080p=$0.16/s (~$0.80/5s)")
        print("kling          | $0.35/5s + $0.07/extra sec")
        print("veo2           | $0.50/s (720p only)")
        print("veo31-fast     | $0.10/s (no audio), $0.15/s (audio)")
        print("veo31          | $0.20/s (no audio), $0.40/s (audio)")
        print("veo31-flf      | $0.20/s - First/Last Frame (2 images)")
        print("veo31-fast-flf | $0.10/s - First/Last Frame (2 images)")
        print("\nExample: python scripts/bulk_generate.py prompts.txt --images-dir ./imgs --model wan22")
        return

    # Validate paths
    if not args.prompts_file.exists():
        print(f"Error: Prompts file not found: {args.prompts_file}")
        sys.exit(1)

    if args.images_dir and not args.images_dir.exists():
        print(f"Error: Images directory not found: {args.images_dir}")
        sys.exit(1)

    # Run async main
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
