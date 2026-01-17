#!/usr/bin/env python3
"""
Combined post-processor for video caption overlay and spoofing.

Pipeline:
1. Add text caption overlay (optional)
2. Apply spoofing transformations (crop, scale, trim, metadata)

Usage:
    python post_process.py --input video.mp4 --caption "Your text" --output out.mp4
    python post_process.py --input video.mp4 --spoof-only --output out.mp4
    python post_process.py --input video.mp4 --caption "Text" --no-spoof --output out.mp4
"""

import argparse
import subprocess
import json
import random
import string
import os
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# Import caption overlay module
sys.path.insert(0, str(Path(__file__).parent))
from add_caption import (
    add_caption_to_video,
    get_video_info,
)


# Spoof configuration (from reeld/spoof_videos.py)
CROP_W_MIN, CROP_W_MAX = 0.93, 0.97   # keep 93-97% width (3-7% crop)
CROP_H_MIN, CROP_H_MAX = 0.95, 0.98   # keep 95-98% height (2-5% crop)
TRIM_MIN, TRIM_MAX = 0.03, 0.08       # 3-8% trim/extend (tail-only)
VBIT_MIN, VBIT_MAX = 3000, 17000      # kbps video
ABIT_MIN, ABIT_MAX = 128, 264         # kbps audio
SCALE_FACTORS = [round(1.0 + 0.1 * i, 1) for i in range(0, 11)]  # 1.0 to 2.0
ENCODER_TAGS = ["Lavf58.76.100", "Lavf60.3.100", "Lavf62.6.100"]


def generate_random_metadata() -> dict:
    """Generate random metadata for spoofed video."""
    days_ago = random.randint(1, 730)
    random_date = datetime.now() - timedelta(days=days_ago)
    cameras = ["iPhone 14 Pro", "iPhone 13", "Samsung Galaxy S23", "Pixel 7", "iPhone 15"]
    return {
        "creation_time": random_date.strftime("%Y-%m-%d %H:%M:%S"),
        "title": f"Video_{random.randint(1000, 9999)}",
        "comment": f"Processed_{random.randint(10000, 99999)}",
        "make": random.choice(["Apple", "Samsung", "Google"]),
        "model": random.choice(cameras),
    }


def spoof_video(
    input_path: str,
    output_path: str,
    use_nvenc: bool = True,
    seed: Optional[int] = None,
) -> dict:
    """
    Apply spoofing transformations to video.

    Args:
        input_path: Input video file
        output_path: Output video file
        use_nvenc: Use NVIDIA NVENC for encoding (faster, requires GPU)
        seed: Random seed for reproducibility

    Returns:
        Dict with spoof parameters applied
    """
    if seed is not None:
        random.seed(seed)

    # Get video info
    video_info = get_video_info(input_path)
    duration = video_info["duration"]

    # Randomize spoof parameters
    w_keep = random.uniform(CROP_W_MIN, CROP_W_MAX)
    h_keep = random.uniform(CROP_H_MIN, CROP_H_MAX)
    trim_pct = random.uniform(TRIM_MIN, TRIM_MAX)
    action = random.choice(["trim", "extend"])

    new_duration = duration
    tpad_filter = ""

    if action == "trim":
        cut_total = duration * trim_pct
        new_duration = max(duration - cut_total, 0.1)
    else:
        extend = duration * trim_pct
        tpad_filter = f",tpad=stop_mode=clone:stop_duration={extend:.3f}"

    v_bitrate = random.randint(VBIT_MIN, VBIT_MAX)
    a_bitrate = random.randint(ABIT_MIN, ABIT_MAX)
    encoder_tag = random.choice(ENCODER_TAGS)
    scale_factor = random.choice(SCALE_FACTORS)

    # Build filter chain
    crop_filter = (
        f"crop=iw*{w_keep:.4f}:ih*{h_keep:.4f}:"
        f"(iw-iw*{w_keep:.4f})/2:(ih-ih*{h_keep:.4f})/2"
    )
    scale_filter = (
        f"scale=trunc(iw*{scale_factor:.1f}/2)*2:"
        f"trunc(ih*{scale_factor:.1f}/2)*2:flags=lanczos"
    )

    vf_parts = [crop_filter, scale_filter]
    if tpad_filter:
        vf_parts.append(tpad_filter.lstrip(","))
    vf_chain = ",".join(vf_parts)

    # Generate metadata
    metadata = generate_random_metadata()

    # Build ffmpeg command
    if use_nvenc:
        # NVENC encoding (faster, requires NVIDIA GPU)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", f"{new_duration:.3f}",
            "-vf", vf_chain,
            "-c:v", "h264_nvenc",
            "-preset", "p5",
            "-bf", "0",
            "-g", "250",
            "-pix_fmt", "yuv420p",
            "-tune", "hq",
            "-b:v", f"{v_bitrate}k",
            "-maxrate", f"{v_bitrate}k",
            "-bufsize", f"{v_bitrate * 2}k",
            "-c:a", "aac",
            "-b:a", f"{a_bitrate}k",
            "-movflags", "+faststart",
            "-metadata", f"encoder={encoder_tag}",
            "-metadata", f"creation_time={metadata['creation_time']}",
            "-metadata", f"title={metadata['title']}",
            "-metadata", f"comment={metadata['comment']}",
            "-metadata", f"make={metadata['make']}",
            "-metadata", f"model={metadata['model']}",
            output_path,
        ]
    else:
        # Software encoding (works everywhere)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", f"{new_duration:.3f}",
            "-vf", vf_chain,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", f"{a_bitrate}k",
            "-movflags", "+faststart",
            "-metadata", f"encoder={encoder_tag}",
            "-metadata", f"creation_time={metadata['creation_time']}",
            "-metadata", f"title={metadata['title']}",
            "-metadata", f"comment={metadata['comment']}",
            "-metadata", f"make={metadata['make']}",
            "-metadata", f"model={metadata['model']}",
            output_path,
        ]

    print(f"Running spoof transform...")
    print(f"  Crop: {100 * (1 - w_keep):.1f}%w / {100 * (1 - h_keep):.1f}%h")
    print(f"  {action.title()}: {trim_pct * 100:.1f}%")
    print(f"  Scale: {scale_factor}x")
    print(f"  Bitrate: {v_bitrate}k video, {a_bitrate}k audio")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Spoof failed: {result.stderr}")
        return {"success": False, "error": result.stderr}

    return {
        "success": True,
        "crop_w_pct": 100 * (1 - w_keep),
        "crop_h_pct": 100 * (1 - h_keep),
        "action": action,
        "trim_pct": trim_pct,
        "scale_factor": scale_factor,
        "v_bitrate_k": v_bitrate,
        "a_bitrate_k": a_bitrate,
        "encoder": encoder_tag,
        "metadata": metadata,
    }


def post_process_video(
    input_path: str,
    output_path: str,
    caption: Optional[str] = None,
    font_path: Optional[str] = None,
    apply_spoof: bool = True,
    use_nvenc: bool = False,
    seed: Optional[int] = None,
) -> dict:
    """
    Full post-processing pipeline: caption + spoof.

    Args:
        input_path: Input video file
        output_path: Final output video file
        caption: Caption text to overlay (None to skip)
        font_path: Path to font file
        apply_spoof: Whether to apply spoofing transforms
        use_nvenc: Use NVENC encoding for spoof step
        seed: Random seed for reproducibility

    Returns:
        Dict with processing results
    """
    results = {
        "input": input_path,
        "output": output_path,
        "caption_applied": False,
        "spoof_applied": False,
    }

    current_input = input_path
    temp_files = []

    try:
        # Step 1: Caption overlay (if requested)
        if caption:
            if apply_spoof:
                # Need intermediate file
                temp_caption = tempfile.NamedTemporaryFile(
                    suffix=".mp4", delete=False
                ).name
                temp_files.append(temp_caption)
                caption_output = temp_caption
            else:
                caption_output = output_path

            print(f"\n=== Step 1: Caption Overlay ===")
            success = add_caption_to_video(
                input_path=current_input,
                output_path=caption_output,
                caption=caption,
                font_path=font_path or str(
                    Path(__file__).parent / "fonts" / "ProximaNova-Semibold.ttf"
                ),
                position_seed=seed,
            )

            if not success:
                results["error"] = "Caption overlay failed"
                return results

            results["caption_applied"] = True
            results["caption_text"] = caption
            current_input = caption_output

        # Step 2: Spoofing transforms (if requested)
        if apply_spoof:
            print(f"\n=== Step 2: Spoof Transforms ===")
            spoof_result = spoof_video(
                input_path=current_input,
                output_path=output_path,
                use_nvenc=use_nvenc,
                seed=(seed + 1000) if seed is not None else None,
            )

            if not spoof_result.get("success"):
                results["error"] = f"Spoof failed: {spoof_result.get('error')}"
                return results

            results["spoof_applied"] = True
            results["spoof_params"] = spoof_result

        results["success"] = True
        print(f"\n=== Post-processing complete ===")
        print(f"Output: {output_path}")

    finally:
        # Clean up temp files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Post-process video with caption overlay and spoofing"
    )
    parser.add_argument("--input", "-i", required=True, help="Input video path")
    parser.add_argument("--output", "-o", required=True, help="Output video path")
    parser.add_argument("--caption", "-c", help="Caption text to overlay")
    parser.add_argument(
        "--font", "-f",
        help="Path to font file (default: ProximaNova-Semibold.ttf)"
    )
    parser.add_argument(
        "--no-spoof",
        action="store_true",
        help="Skip spoofing transforms (caption only)"
    )
    parser.add_argument(
        "--spoof-only",
        action="store_true",
        help="Skip caption (spoof only)"
    )
    parser.add_argument(
        "--nvenc",
        action="store_true",
        help="Use NVIDIA NVENC encoder (faster, requires GPU)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(2)

    # Determine what to do
    apply_caption = args.caption and not args.spoof_only
    apply_spoof = not args.no_spoof

    if args.spoof_only and args.no_spoof:
        print("Error: Cannot use both --spoof-only and --no-spoof")
        sys.exit(2)

    if not apply_caption and not apply_spoof:
        print("Error: Nothing to do (need --caption or spoof enabled)")
        sys.exit(2)

    # Run post-processing
    seed = args.seed if args.seed is not None else random.randint(0, 999999)
    print(f"Seed: {seed}")

    result = post_process_video(
        input_path=args.input,
        output_path=args.output,
        caption=args.caption if apply_caption else None,
        font_path=args.font,
        apply_spoof=apply_spoof,
        use_nvenc=args.nvenc,
        seed=seed,
    )

    if result.get("success"):
        print(f"\nDone!")
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)
    else:
        print(f"\nFailed: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
