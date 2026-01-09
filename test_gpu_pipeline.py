"""
Test script for the GPU pipeline.
Tests vast.ai instance creation, model availability, and image generation.
"""

import asyncio
import os
import sys
import time

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.services.vastai_client import get_vastai_client, upload_image_to_comfyui
from app.services.nsfw_image_executor import generate_nsfw_image, NSFW_MODELS
import httpx


async def test_pipeline():
    """Test the full GPU pipeline."""
    client = get_vastai_client()

    print("=" * 60)
    print("GPU PIPELINE TEST")
    print("=" * 60)

    # Step 1: Check vast.ai connection and balance
    print("\n[1] Checking vast.ai connection...")
    try:
        offers = await client.search_offers(gpu_ram_min=12, max_price=0.50)
        print(f"    Found {len(offers)} available GPU offers")
        if offers:
            cheapest = min(offers, key=lambda x: x.get("dph_total", 999))
            print(f"    Cheapest: {cheapest.get('gpu_name')} @ ${cheapest.get('dph_total', 0):.3f}/hr")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Step 2: Check for existing instances
    print("\n[2] Checking existing instances...")
    try:
        instances = await client.list_instances()
        print(f"    Found {len(instances)} existing instances")
        for inst in instances:
            print(f"    - ID {inst.id}: {inst.gpu_name} ({inst.status})")
            if inst.api_port:
                print(f"      API: http://{inst.public_ip}:{inst.api_port}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Step 3: Get or create instance
    print("\n[3] Getting/creating GPU instance...")
    try:
        instance = await client.get_or_create_instance(
            workload="image",
            max_price=0.35,
        )
        if not instance:
            print("    ERROR: Failed to get/create instance")
            return False
        print(f"    Instance ID: {instance.id}")
        print(f"    GPU: {instance.gpu_name}")
        print(f"    Status: {instance.status}")
        print(f"    Price: ${instance.dph_total:.3f}/hr")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Wait for instance to be ready
    print("\n[4] Waiting for instance to be ready...")
    max_wait = 300  # 5 minutes
    start = time.time()

    while time.time() - start < max_wait:
        try:
            instance = await client.get_instance(instance.id)
            if not instance:
                print("    ERROR: Instance disappeared")
                return False

            print(f"    Status: {instance.status} (waited {int(time.time() - start)}s)")

            if instance.status == "running" and instance.api_port and instance.public_ip:
                print(f"    Instance ready! API at http://{instance.public_ip}:{instance.api_port}")
                break

            await asyncio.sleep(10)
        except Exception as e:
            print(f"    Error checking status: {e}")
            await asyncio.sleep(10)
    else:
        print("    TIMEOUT: Instance not ready after 5 minutes")
        return False

    # Step 5: Check ComfyUI is responding
    print("\n[5] Checking ComfyUI API...")
    comfyui_url = f"http://{instance.public_ip}:{instance.api_port}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(f"{comfyui_url}/system_stats")
            if resp.status_code == 200:
                stats = resp.json()
                print(f"    ComfyUI is running!")
                print(f"    VRAM: {stats.get('devices', [{}])[0].get('vram_total', 0) / 1e9:.1f} GB")
            else:
                print(f"    WARNING: ComfyUI returned {resp.status_code}")
    except Exception as e:
        print(f"    ERROR: ComfyUI not responding: {e}")
        print("    (May still be starting up or downloading models)")

    # Step 6: Check available models
    print("\n[6] Checking available models...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(f"{comfyui_url}/object_info/CheckpointLoaderSimple")
            if resp.status_code == 200:
                data = resp.json()
                ckpts = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {})
                models = ckpts.get("ckpt_name", [[]])[0]
                print(f"    Available checkpoints: {len(models)}")
                for m in models[:5]:
                    print(f"    - {m}")
                if len(models) > 5:
                    print(f"    ... and {len(models) - 5} more")
            else:
                print(f"    WARNING: Could not get model list ({resp.status_code})")
    except Exception as e:
        print(f"    ERROR: {e}")

    # Step 7: Test image upload
    print("\n[7] Testing image upload to ComfyUI...")
    test_image_url = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=512"

    try:
        filename = await upload_image_to_comfyui(
            image_url=test_image_url,
            comfyui_base_url=comfyui_url,
        )
        print(f"    Upload successful! Filename: {filename}")
    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 8: Test actual generation
    print("\n[8] Testing image generation...")
    try:
        result = await generate_nsfw_image(
            source_image_url=test_image_url,
            prompt="professional portrait photo, high quality, detailed",
            model="sdxl-base",  # Use base SDXL which should be available
            denoise=0.5,
            steps=20,
        )

        if result["status"] == "completed":
            print(f"    SUCCESS! Generated in {result['generation_time']:.1f}s")
            print(f"    Result URL: {result['result_url']}")
        else:
            print(f"    FAILED: {result.get('error_message')}")
            return False

    except Exception as e:
        print(f"    ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)

    # Ask about cleanup
    print(f"\nInstance {instance.id} is still running at ${instance.dph_total:.3f}/hr")
    print("Remember to destroy it when done testing!")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_pipeline())
    sys.exit(0 if success else 1)
