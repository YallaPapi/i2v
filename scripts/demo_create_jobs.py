#!/usr/bin/env python
"""
Demo script to create video generation jobs.

Usage:
    python scripts/demo_create_jobs.py --file jobs.jsonl
    python scripts/demo_create_jobs.py --file jobs.csv --format csv
"""
import argparse
import json
import csv
import httpx


def load_jobs_jsonl(filepath: str) -> list[dict]:
    """Load jobs from JSONL file (one JSON object per line)."""
    jobs = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
    return jobs


def load_jobs_csv(filepath: str) -> list[dict]:
    """Load jobs from CSV file."""
    jobs = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job = {
                "image_url": row["image_url"],
                "motion_prompt": row["motion_prompt"],
                "resolution": row.get("resolution", "1080p"),
                "duration_sec": int(row.get("duration_sec", 5)),
            }
            jobs.append(job)
    return jobs


def create_job(client: httpx.Client, base_url: str, job_data: dict) -> dict:
    """Create a single job via the API."""
    response = client.post(f"{base_url}/jobs", json=job_data)
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Create video generation jobs")
    parser.add_argument("--file", "-f", required=True, help="Input file path")
    parser.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="Input file format (default: jsonl)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    # Load jobs
    if args.format == "jsonl":
        jobs = load_jobs_jsonl(args.file)
    else:
        jobs = load_jobs_csv(args.file)

    print(f"Loaded {len(jobs)} jobs from {args.file}")

    # Create jobs
    created_ids = []
    with httpx.Client(timeout=30.0) as client:
        for i, job_data in enumerate(jobs):
            try:
                result = create_job(client, args.url, job_data)
                created_ids.append(result["id"])
                print(
                    f"[{i+1}/{len(jobs)}] Created job {result['id']}: {job_data['image_url'][:50]}..."
                )
            except httpx.HTTPStatusError as e:
                print(
                    f"[{i+1}/{len(jobs)}] Failed: {e.response.status_code} - {e.response.text}"
                )
            except Exception as e:
                print(f"[{i+1}/{len(jobs)}] Error: {e}")

    print(f"\nCreated {len(created_ids)} jobs: {created_ids}")


if __name__ == "__main__":
    main()
