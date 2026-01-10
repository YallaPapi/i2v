#!/usr/bin/env python3
"""
Test script for Vast.ai ComfyUI template-based instance creation.

This tests the official Vast.ai ComfyUI template (hash: 2188dfd3e0a0b83691bb468ddae0a4e5)
which properly configures:
- Docker image: vastai/comfy:@vastai-automatic-tag
- Port 8188 for ComfyUI API
- Proper startup via entrypoint.sh

Usage:
    python test_vast_comfy_template.py

Environment variables required:
    VASTAI_API_KEY - Your Vast.ai API key
"""

import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.vastai_client import (
    VastAIClient,
    build_comfyui_url,
    COMFYUI_TEMPLATE_HASH,
)


async def test_search_offers():
    """Test searching for GPU offers."""
    print("\n=== Testing search_offers ===")
    client = VastAIClient()

    offers = await client.search_offers(
        gpu_ram_min=12,
        disk_space_min=50,
        max_price=0.50,
        verified=True,
    )

    if not offers:
        print("ERROR: No offers found. Check GPU availability or price limits.")
        return None

    print(f"Found {len(offers)} offers")
    print(f"Cheapest: {offers[0].get('gpu_name')} @ ${offers[0].get('dph_total'):.3f}/hr")
    print(f"Offer ID: {offers[0].get('id')}")

    return offers[0]


async def test_create_instance_from_template(offer_id: int):
    """Test creating an instance using the official ComfyUI template."""
    print("\n=== Testing create_instance_from_template ===")
    print(f"Using template hash: {COMFYUI_TEMPLATE_HASH}")
    print(f"Offer ID: {offer_id}")

    client = VastAIClient()

    instance = await client.create_instance_from_template(
        offer_id=offer_id,
        disk_space=50,
    )

    if not instance:
        print("ERROR: Failed to create instance")
        return None

    print(f"Instance created successfully!")
    print(f"  ID: {instance.id}")
    print(f"  Status: {instance.status}")
    print(f"  GPU: {instance.gpu_name}")
    print(f"  Public IP: {instance.public_ip}")
    print(f"  API Port: {instance.api_port}")

    return instance


async def test_comfyui_health(instance):
    """Test that ComfyUI API is accessible."""
    print("\n=== Testing ComfyUI API Health ===")

    if not instance.public_ip or not instance.api_port:
        print("ERROR: Instance missing public_ip or api_port")
        return False

    api_url = build_comfyui_url(instance)
    print(f"ComfyUI URL: {api_url}")

    # Wait for ComfyUI to be ready (it takes time to start)
    max_retries = 30
    retry_delay = 10

    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries}: Checking {api_url}/system_stats")
                response = await client.get(f"{api_url}/system_stats")

                if response.status_code == 200:
                    data = response.json()
                    print("SUCCESS! ComfyUI API is responding")
                    print(f"  System stats: {data}")
                    return True
                else:
                    print(f"  Got status {response.status_code}, retrying...")
            except httpx.ConnectError:
                print(f"  Connection refused, ComfyUI may still be starting...")
            except httpx.ReadTimeout:
                print(f"  Read timeout, ComfyUI may be busy...")
            except Exception as e:
                print(f"  Error: {e}")

            if attempt < max_retries - 1:
                print(f"  Waiting {retry_delay}s before retry...")
                await asyncio.sleep(retry_delay)

    print("ERROR: ComfyUI API did not become available")
    return False


async def test_list_and_cleanup():
    """List all instances and optionally clean them up."""
    print("\n=== Listing All Instances ===")
    client = VastAIClient()

    instances = await client.list_instances()

    if not instances:
        print("No instances found")
        return

    print(f"Found {len(instances)} instance(s):")
    for inst in instances:
        print(f"  ID: {inst.id}, Status: {inst.status}, GPU: {inst.gpu_name}, IP: {inst.public_ip}, Port: {inst.api_port}")

    # Ask if user wants to destroy instances
    response = input("\nDestroy all instances? (y/N): ").strip().lower()
    if response == 'y':
        for inst in instances:
            print(f"Destroying instance {inst.id}...")
            await client.destroy_instance(inst.id)
        print("All instances destroyed")


async def main():
    """Main test runner."""
    print("=" * 60)
    print("Vast.ai ComfyUI Template Test")
    print("=" * 60)

    # Check API key
    if not os.getenv("VASTAI_API_KEY"):
        print("ERROR: VASTAI_API_KEY environment variable not set")
        sys.exit(1)

    print(f"Template hash: {COMFYUI_TEMPLATE_HASH}")

    # Menu
    print("\nSelect test to run:")
    print("1. Search offers only (safe, no cost)")
    print("2. Full test: Create instance + test API (costs money!)")
    print("3. List instances and cleanup")
    print("4. Test ComfyUI health on existing instance")

    choice = input("\nChoice (1-4): ").strip()

    if choice == "1":
        await test_search_offers()

    elif choice == "2":
        # Search for offer
        offer = await test_search_offers()
        if not offer:
            return

        # Confirm before creating instance (costs money)
        price = offer.get('dph_total', 0)
        print(f"\nWARNING: Creating instance will cost ~${price:.3f}/hr")
        confirm = input("Proceed? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Aborted")
            return

        # Create instance from template
        instance = await test_create_instance_from_template(offer['id'])
        if not instance:
            return

        # Test ComfyUI health
        success = await test_comfyui_health(instance)

        # Cleanup prompt
        if instance:
            cleanup = input("\nDestroy instance? (y/N): ").strip().lower()
            if cleanup == 'y':
                client = VastAIClient()
                await client.destroy_instance(instance.id)
                print("Instance destroyed")

    elif choice == "3":
        await test_list_and_cleanup()

    elif choice == "4":
        instance_id = input("Enter instance ID: ").strip()
        if not instance_id:
            print("No instance ID provided")
            return

        client = VastAIClient()
        instance = await client.get_instance(int(instance_id))
        if not instance:
            print(f"Instance {instance_id} not found")
            return

        print(f"Instance {instance.id}: {instance.status}")
        print(f"  GPU: {instance.gpu_name}")
        print(f"  Public IP: {instance.public_ip}")
        print(f"  API Port: {instance.api_port}")

        if instance.status == "running":
            await test_comfyui_health(instance)
        else:
            print(f"Instance is not running (status: {instance.status})")

    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
