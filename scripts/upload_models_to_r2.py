#!/usr/bin/env python3
"""
Upload local SwarmUI models to R2 for fast deployment to vast.ai.

Usage:
    python scripts/upload_models_to_r2.py

This will upload:
- Wan 2.2 I2V GGUF model
- LightX2V 4-step LoRA

After upload, vast.ai instances can download from R2 instead of CivitAI.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.r2_cache import upload_model_to_r2, get_model_urls


# Common SwarmUI model locations on Windows
SWARMUI_PATHS = [
    Path(os.environ.get("SWARMUI_PATH", "")) / "Models",
    Path.home() / "SwarmUI" / "Models",
    Path("C:/SwarmUI/Models"),
    Path("D:/SwarmUI/Models"),
]

# Models to upload
MODELS = {
    "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf": [
        "unet",  # SwarmUI puts GGUF models in unet folder
        "Stable-Diffusion",  # Or here
    ],
    "wan2.2_i2v_lightx2v_4steps_lora.safetensors": [
        "Lora",
        "loras",
    ],
}


def find_model(model_name: str, subfolders: list[str]) -> Path | None:
    """Find a model file in common SwarmUI locations."""
    for base_path in SWARMUI_PATHS:
        if not base_path.exists():
            continue
        for subfolder in subfolders:
            model_path = base_path / subfolder / model_name
            if model_path.exists():
                return model_path
            # Try without subfolder
            model_path = base_path / model_name
            if model_path.exists():
                return model_path
    return None


def main():
    print("=" * 60)
    print("Upload SwarmUI Models to R2")
    print("=" * 60)

    # Check R2 configuration
    if not os.getenv("R2_ACCESS_KEY_ID"):
        print("ERROR: R2 not configured. Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT, R2_PUBLIC_DOMAIN in .env")
        sys.exit(1)

    uploaded = []
    failed = []

    for model_name, subfolders in MODELS.items():
        print(f"\nLooking for: {model_name}")

        model_path = find_model(model_name, subfolders)

        if not model_path:
            # Ask user for path
            print(f"  Not found in common locations.")
            user_path = input(f"  Enter full path to {model_name} (or skip): ").strip()
            if user_path and Path(user_path).exists():
                model_path = Path(user_path)
            else:
                print(f"  Skipping {model_name}")
                failed.append(model_name)
                continue

        print(f"  Found: {model_path}")
        print(f"  Size: {model_path.stat().st_size / (1024**3):.2f} GB")

        # Upload
        print(f"  Uploading to R2...")
        url = upload_model_to_r2(str(model_path), model_name)

        if url:
            print(f"  SUCCESS: {url}")
            uploaded.append((model_name, url))
        else:
            print(f"  FAILED to upload")
            failed.append(model_name)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if uploaded:
        print("\nUploaded:")
        for name, url in uploaded:
            print(f"  - {name}")
            print(f"    {url}")

    if failed:
        print("\nFailed/Skipped:")
        for name in failed:
            print(f"  - {name}")

    if uploaded:
        print("\n" + "=" * 60)
        print("R2 Model URLs (use these in vast.ai startup script):")
        print("=" * 60)
        urls = get_model_urls()
        for key, url in urls.items():
            print(f"{key}: {url}")


if __name__ == "__main__":
    main()
