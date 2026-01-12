"""
Test script to verify Vast.ai instance creation with RTX 5090 + CUDA 12.8.

This script:
1. Searches for RTX 5090 offers on Vast.ai
2. Creates an instance with nvidia/cuda:12.8.0-runtime-ubuntu22.04
3. Waits for it to reach "running" status
4. Reports the instance details

Run with: python test_vastai_instance.py
"""

import os
import asyncio
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

VASTAI_API_URL = "https://console.vast.ai/api/v0"
DOCKER_IMAGE = "nvidia/cuda:12.8.0-runtime-ubuntu22.04"


async def main():
    api_key = os.getenv("VASTAI_API_KEY")
    if not api_key:
        print("ERROR: VASTAI_API_KEY not set in .env")
        print("Add: VASTAI_API_KEY=your_key_here")
        return

    print(f"API Key: {api_key[:10]}...")
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Search for RTX 5090 offers
        print("\n=== STEP 1: Searching for RTX 5090 offers ===")

        query = {
            "gpu_name": {"eq": "RTX 5090"},
            "gpu_ram": {"gte": 30 * 1024},  # 30GB+ (5090 has ~32GB)
            "disk_space": {"gte": 80},
            "dph_total": {"lte": 1.50},  # Max $1.50/hr
            "rentable": {"eq": True},
            # Note: RTX 5090 is new, many aren't verified yet
        }

        response = await client.get(
            f"{VASTAI_API_URL}/bundles/",
            headers=headers,
            params={"q": json.dumps(query)},
        )

        if response.status_code != 200:
            print(f"ERROR: Failed to search offers: {response.status_code}")
            print(response.text)
            return

        data = response.json()
        offers = data.get("offers", [])

        if not offers:
            print("No RTX 5090 offers found at this price point.")
            print("Trying without verified filter and higher price...")

            # Try with higher price
            query["dph_total"] = {"lte": 2.00}
            response = await client.get(
                f"{VASTAI_API_URL}/bundles/",
                headers=headers,
                params={"q": json.dumps(query)},
            )
            data = response.json()
            offers = data.get("offers", [])

        if not offers:
            print("Still no RTX 5090 offers. Checking what GPUs ARE available...")
            # Search for any high-VRAM GPU
            query_any = {
                "gpu_ram": {"gte": 24 * 1024},
                "rentable": {"eq": True},
                "dph_total": {"lte": 1.00},
            }
            response = await client.get(
                f"{VASTAI_API_URL}/bundles/",
                headers=headers,
                params={"q": json.dumps(query_any)},
            )
            data = response.json()
            any_offers = data.get("offers", [])[:10]
            print(f"Available GPUs (24GB+, <$1/hr):")
            for o in any_offers:
                print(f"  - {o.get('gpu_name')}: ${o.get('dph_total'):.2f}/hr, {o.get('gpu_ram')/1024:.0f}GB VRAM")
            return

        # Sort by price
        offers.sort(key=lambda x: x.get("dph_total", 999))

        print(f"Found {len(offers)} RTX 5090 offers:")
        for i, offer in enumerate(offers[:5]):
            print(f"  {i+1}. ID={offer['id']}, ${offer.get('dph_total', 0):.2f}/hr, "
                  f"{offer.get('gpu_ram', 0)/1024:.0f}GB VRAM, "
                  f"verified={offer.get('verified', False)}")

        # Step 2: Create instance with cheapest offer
        print("\n=== STEP 2: Creating instance with CUDA 12.8 ===")

        offer = offers[0]
        offer_id = offer["id"]

        print(f"Selected offer: ID={offer_id}, ${offer.get('dph_total'):.2f}/hr")
        print(f"Docker image: {DOCKER_IMAGE}")

        # Simple onstart script - just verify CUDA works
        onstart_script = """#!/bin/bash
echo "=== i2v Instance Starting ==="
echo "Checking NVIDIA driver..."
nvidia-smi
echo "CUDA version:"
nvcc --version 2>/dev/null || echo "nvcc not in PATH (runtime image)"
echo "=== Instance ready for SwarmUI installation ==="
"""

        payload = {
            "client_id": "i2v-test",
            "image": DOCKER_IMAGE,
            "disk": 80,
            "runtype": "ssh_direc",  # Direct SSH access
            "onstart": onstart_script,
        }

        print(f"Creating instance...")
        response = await client.put(
            f"{VASTAI_API_URL}/asks/{offer_id}/",
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            print(f"ERROR: Failed to create instance: {response.status_code}")
            print(response.text)
            return

        data = response.json()
        instance_id = data.get("new_contract")

        if not instance_id:
            print(f"ERROR: No instance ID in response: {data}")
            return

        print(f"Instance created! ID: {instance_id}")

        # Step 3: Wait for instance to be running
        print("\n=== STEP 3: Waiting for instance to start ===")
        print("Polling every 10 seconds...")

        max_wait = 300  # 5 minutes
        elapsed = 0
        poll_interval = 10

        while elapsed < max_wait:
            response = await client.get(
                f"{VASTAI_API_URL}/instances/{instance_id}/",
                headers=headers,
            )

            if response.status_code != 200:
                print(f"  [{elapsed}s] Error checking status: {response.status_code}")
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                continue

            data = response.json()
            if "instances" in data:
                data = data["instances"]

            status = data.get("actual_status", "unknown")
            status_msg = data.get("status_msg", "")

            print(f"  [{elapsed}s] Status: {status} - {status_msg[:50] if status_msg else 'no message'}")

            if status == "running":
                print("\n=== SUCCESS: Instance is running! ===")
                print(f"  Instance ID: {instance_id}")
                print(f"  GPU: {data.get('gpu_name', 'Unknown')}")
                print(f"  Public IP: {data.get('public_ipaddr', 'N/A')}")
                print(f"  SSH Host: {data.get('ssh_host', 'N/A')}")
                print(f"  SSH Port: {data.get('ssh_port', 'N/A')}")
                print(f"  Ports: {data.get('ports', {})}")
                print(f"  Price: ${data.get('dph_total', 0):.2f}/hr")

                # Print SSH command
                ssh_host = data.get('ssh_host')
                ssh_port = data.get('ssh_port')
                if ssh_host and ssh_port:
                    print(f"\nSSH command:")
                    print(f"  ssh root@{ssh_host} -p {ssh_port}")

                print("\n=== INSTANCE IS READY ===")
                print("To destroy when done:")
                print(f"  curl -X DELETE -H 'Authorization: Bearer {api_key[:10]}...' {VASTAI_API_URL}/instances/{instance_id}/")
                return

            if status in ("exited", "error"):
                print(f"\nERROR: Instance failed to start: {status}")
                print(f"Message: {status_msg}")
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        print(f"\nTIMEOUT: Instance did not reach 'running' status within {max_wait}s")
        print("Check Vast.ai console for details.")


if __name__ == "__main__":
    asyncio.run(main())
