#!/usr/bin/env python3
"""
Add text caption overlay to video using FFmpeg.

Uses Proxima Nova Semibold font with controlled random positioning.
Includes Claude Vision verification for quality assurance.

Usage:
    python add_caption.py --input video.mp4 --caption "Your text here" --output output.mp4
    python add_caption.py --input video.mp4 --caption "Your text here" --font /path/to/ProximaNova-Semibold.ttf
"""

import argparse
import subprocess
import json
import random
import sys
import os
import base64
import textwrap
from pathlib import Path
from typing import Optional, Tuple

# Try to import anthropic for verification (optional)
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def get_video_info(video_path: str) -> dict:
    """Get video resolution and duration using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    # Find video stream
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise RuntimeError("No video stream found")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    duration = float(data.get("format", {}).get("duration", 0))

    return {
        "width": width,
        "height": height,
        "duration": duration,
        "is_vertical": height > width
    }


def calculate_font_size(width: int, height: int) -> int:
    """Calculate optimal font size based on resolution."""
    # For vertical 9:16 videos
    if height > width:
        # Base on width since that's the limiting factor
        if width >= 1080:
            return 58  # 1080x1920
        elif width >= 720:
            return 42  # 720x1280
        else:
            return 32  # smaller
    else:
        # Horizontal videos
        if height >= 1080:
            return 54
        elif height >= 720:
            return 38
        else:
            return 28


def calculate_style_variations(seed: Optional[int] = None) -> dict:
    """
    Calculate random style variations for caption.

    Returns dict with:
        - x_jitter: horizontal offset in pixels (positive = right)
        - stroke_width: border width in pixels
    """
    if seed is not None:
        random.seed(seed)

    # Horizontal jitter: -5% to +5% of typical width (~720px)
    # This gives roughly -36 to +36 pixels offset
    x_jitter = random.randint(-40, 40)

    # Stroke width variation: 2-4 pixels
    stroke_width = random.choice([2, 2, 2, 3, 3, 4])  # Weighted toward 2-3

    return {
        "x_jitter": x_jitter,
        "stroke_width": stroke_width
    }


def calculate_position(width: int, height: int, text_lines: int, font_size: int, seed: Optional[int] = None) -> Tuple[str, str]:
    """
    Calculate caption position with controlled randomness.

    Position is primarily slightly below center, with some variation.
    Returns ffmpeg x and y expressions.
    """
    if seed is not None:
        random.seed(seed)

    # Estimate text height (line height = font_size * 1.3)
    line_height = font_size * 1.3
    total_text_height = text_lines * line_height

    # Safe zones (percentage of dimension)
    x_safe_margin = 0.05  # 5% from left/right edges
    y_safe_top = 0.20     # 20% from top
    y_safe_bottom = 0.15  # 15% from bottom

    # Y position: primarily below center with controlled randomness
    # Range: 45% to 65% of height (biased slightly below center which is 50%)
    y_center_offset = random.uniform(-0.05, 0.15)  # -5% to +15% from center (biased down)
    y_base = 0.50 + y_center_offset

    # Clamp to safe zone
    y_min = y_safe_top
    y_max = 1.0 - y_safe_bottom - (total_text_height / height)
    y_base = max(y_min, min(y_max, y_base))

    # X position: slight horizontal variation (mostly centered)
    x_offset = random.uniform(-0.08, 0.08)  # +/- 8% from center

    # FFmpeg expressions
    # x: center text with slight random offset
    x_expr = f"(w-text_w)/2+{int(width * x_offset)}"

    # y: calculated position
    y_pixel = int(height * y_base)
    y_expr = str(y_pixel)

    return x_expr, y_expr


def wrap_text(text: str, max_chars_per_line: int = 35) -> str:
    """Wrap text to fit within video frame."""
    lines = textwrap.wrap(text, width=max_chars_per_line)
    return "\n".join(lines)


def escape_text_for_ffmpeg(text: str) -> str:
    """Escape special characters for ffmpeg drawtext filter."""
    # Escape characters that have special meaning in ffmpeg
    text = text.replace("\\", "\\\\")  # Backslash first
    text = text.replace(":", "\\:")
    # In FFmpeg single-quoted strings, double the apostrophe to escape
    text = text.replace("'", "''")
    text = text.replace("%", "\\%")
    return text


def escape_path_for_ffmpeg(path: str) -> str:
    """Escape file path for ffmpeg filter on Windows."""
    # Convert to forward slashes
    path = path.replace("\\", "/")
    # Escape colons (e.g., C: -> C\\:)
    path = path.replace(":", "\\:")
    return path


def add_caption_to_video(
    input_path: str,
    output_path: str,
    caption: str,
    font_path: str,
    font_size: Optional[int] = None,
    position_seed: Optional[int] = None,
    font_color: str = "white",
    shadow_color: str = "black",
    shadow_offset: int = 2,
) -> bool:
    """
    Add caption overlay to video using ffmpeg.

    Returns True if successful.
    """
    # Get video info
    video_info = get_video_info(input_path)
    width = video_info["width"]
    height = video_info["height"]

    print(f"Video: {width}x{height}, duration: {video_info['duration']:.1f}s")

    # Calculate font size if not specified
    if font_size is None:
        font_size = calculate_font_size(width, height)

    print(f"Font size: {font_size}")

    # Wrap text
    max_chars = 30 if width < 1000 else 40
    wrapped_text = wrap_text(caption, max_chars)
    text_lines = len(wrapped_text.split("\n"))

    print(f"Caption ({text_lines} lines): {wrapped_text[:50]}...")

    # Calculate position
    x_expr, y_expr = calculate_position(width, height, text_lines, font_size, position_seed)

    # Calculate style variations (jitter, rotation, stroke width)
    # Use seed+1 to get different randomness from position
    style_seed = position_seed + 1 if position_seed is not None else None
    style = calculate_style_variations(style_seed)

    print(f"Position: x={x_expr}, y={y_expr}")
    print(f"Style: jitter={style['x_jitter']}px, stroke={style['stroke_width']}px")

    # Escape font path for ffmpeg
    escaped_font_path = escape_path_for_ffmpeg(font_path)

    # Build separate drawtext filter for each line (for proper centering)
    lines = wrapped_text.split("\n")
    line_height = int(font_size * 1.4)  # Line height with spacing

    # Calculate base Y position (from calculate_position, but we need the numeric value)
    base_y = int(y_expr) if y_expr.isdigit() else int(height * 0.55)

    # Apply horizontal jitter to x position
    x_jitter = style["x_jitter"]

    # Build filter chain - one drawtext per line, each centered with jitter
    filters = []
    for i, line in enumerate(lines):
        escaped_line = escape_text_for_ffmpeg(line)
        line_y = base_y + (i * line_height)

        # X position with jitter: center + jitter offset
        x_pos = f"(w-text_w)/2+{x_jitter}"

        # Build drawtext filter
        drawtext_parts = [
            f"drawtext=fontfile='{escaped_font_path}'",
            f"text='{escaped_line}'",
            f"fontsize={font_size}",
            f"fontcolor={font_color}",
            f"borderw={style['stroke_width']}",
            f"bordercolor={shadow_color}",
            f"x={x_pos}",
            f"y={line_y}",
        ]

        drawtext = ":".join(drawtext_parts)
        filters.append(drawtext)

    # Combine filters
    drawtext_filter = ",".join(filters)

    # FFmpeg command
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", input_path,
        "-vf", drawtext_filter,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "medium",
        "-c:a", "copy",  # Copy audio without re-encoding
        "-pix_fmt", "yuv420p",
        output_path
    ]

    print(f"\nRunning ffmpeg...")
    print(f"Filter: {drawtext_filter[:100]}...")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}")
        return False

    print(f"Output saved to: {output_path}")
    return True


def extract_frame(video_path: str, output_path: str, position: float = 0.5) -> bool:
    """Extract a frame from video at given position (0.0-1.0)."""
    video_info = get_video_info(video_path)
    timestamp = video_info["duration"] * position

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def verify_caption_with_vision(frame_path: str, expected_caption: str) -> dict:
    """
    Use Claude Vision to verify caption is present and looks correct.

    Returns dict with:
        - present: bool - is caption visible?
        - readable: bool - is text readable?
        - natural: bool - does positioning look natural?
        - details: str - explanation
        - passed: bool - overall pass/fail
    """
    if not ANTHROPIC_AVAILABLE:
        return {
            "present": None,
            "readable": None,
            "natural": None,
            "details": "anthropic package not installed - skipping verification",
            "passed": None
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "present": None,
            "readable": None,
            "natural": None,
            "details": "ANTHROPIC_API_KEY not set - skipping verification",
            "passed": None
        }

    # Read and encode image
    with open(frame_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Analyze this video frame and verify the text caption overlay.

Expected caption text (approximately): "{expected_caption[:100]}"

Check these criteria:
1. PRESENT: Is there visible text caption on the image?
2. READABLE: Is the text clear and readable (not blurry, not too small)?
3. NATURAL: Does the caption positioning look natural? (not cut off at edges, not covering important content, reasonable size)

Respond with JSON only:
{{"present": true/false, "readable": true/false, "natural": true/false, "details": "brief explanation"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    # Parse response
    response_text = response.content[0].text.strip()

    # Try to extract JSON
    try:
        # Handle markdown code blocks
        if "```" in response_text:
            json_str = response_text.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
            json_str = json_str.strip()
        else:
            json_str = response_text

        result = json.loads(json_str)
        result["passed"] = all([
            result.get("present", False),
            result.get("readable", False),
            result.get("natural", False)
        ])
        return result
    except json.JSONDecodeError:
        return {
            "present": None,
            "readable": None,
            "natural": None,
            "details": f"Failed to parse response: {response_text}",
            "passed": False
        }


def main():
    parser = argparse.ArgumentParser(
        description="Add text caption to video with controlled positioning"
    )
    parser.add_argument("--input", "-i", required=True, help="Input video path")
    parser.add_argument("--output", "-o", default=None, help="Output video path (auto-generated if not specified)")
    parser.add_argument("--caption", "-c", required=True, help="Caption text")
    parser.add_argument(
        "--font", "-f",
        default=None,
        help="Path to Proxima Nova Semibold .ttf file"
    )
    parser.add_argument(
        "--font-size",
        type=int,
        default=None,
        help="Font size (auto-calculated if not specified)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for position (for reproducibility)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify output with Claude Vision"
    )
    parser.add_argument(
        "--font-color",
        default="white",
        help="Font color (default: white)"
    )
    parser.add_argument(
        "--shadow-color",
        default="black",
        help="Shadow color (default: black)"
    )
    parser.add_argument(
        "--shadow-offset",
        type=int,
        default=2,
        help="Shadow offset in pixels (default: 2)"
    )

    args = parser.parse_args()

    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(2)

    # Auto-generate short output filename if not specified
    if args.output is None:
        import time
        timestamp = int(time.time()) % 10000  # Last 4 digits
        output_dir = Path(args.input).parent
        args.output = str(output_dir / f"cap_{timestamp}.mp4")
        print(f"Output: {args.output}")

    # Find font
    font_path = args.font
    if font_path is None:
        # Check common locations
        possible_paths = [
            Path(__file__).parent / "fonts" / "ProximaNova-Semibold.ttf",
            Path(__file__).parent.parent / "fonts" / "ProximaNova-Semibold.ttf",
            Path("C:/Windows/Fonts/ProximaNova-Semibold.ttf"),
            Path.home() / "AppData/Local/Microsoft/Windows/Fonts/ProximaNova-Semibold.ttf",
        ]
        for p in possible_paths:
            if p.exists():
                font_path = str(p)
                break

    if font_path is None or not os.path.exists(font_path):
        print("Error: Proxima Nova Semibold font not found.")
        print("Please provide path with --font /path/to/ProximaNova-Semibold.ttf")
        print("\nExpected locations:")
        print("  - scripts/fonts/ProximaNova-Semibold.ttf")
        print("  - C:/Windows/Fonts/ProximaNova-Semibold.ttf")
        sys.exit(2)

    print(f"Using font: {font_path}")

    # Generate random seed if not provided
    seed = args.seed
    if seed is None:
        seed = random.randint(0, 999999)

    print(f"Position seed: {seed}")

    # Add caption
    success = add_caption_to_video(
        input_path=args.input,
        output_path=args.output,
        caption=args.caption,
        font_path=font_path,
        font_size=args.font_size,
        position_seed=seed,
        font_color=args.font_color,
        shadow_color=args.shadow_color,
        shadow_offset=args.shadow_offset,
    )

    if not success:
        print("\nCaption overlay failed!")
        sys.exit(1)

    # Verify if requested
    if args.verify:
        print("\n--- Verification ---")

        # Extract middle frame
        frame_path = args.output.rsplit(".", 1)[0] + "_verify.jpg"
        if extract_frame(args.output, frame_path, position=0.5):
            print(f"Extracted frame: {frame_path}")

            result = verify_caption_with_vision(frame_path, args.caption)
            print(f"Verification result: {json.dumps(result, indent=2)}")

            # Clean up frame
            try:
                os.remove(frame_path)
            except:
                pass

            if result.get("passed") is False:
                print("\nVerification FAILED - caption may need adjustment")
                sys.exit(1)
            elif result.get("passed") is True:
                print("\nVerification PASSED")
            else:
                print("\nVerification skipped (no API key or package)")
        else:
            print("Failed to extract frame for verification")

    print("\nDone!")
    sys.exit(0)


if __name__ == "__main__":
    main()
