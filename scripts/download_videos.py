#!/usr/bin/env python
"""Download completed videos from the database."""
import argparse
import httpx
import sqlite3
import zipfile
from pathlib import Path
from datetime import datetime


def get_completed_jobs(db_path: str, job_ids: list[int] | None = None) -> list[dict]:
    """Get completed jobs from database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if job_ids:
        placeholders = ",".join("?" * len(job_ids))
        c.execute(f"""
            SELECT id, model, motion_prompt, wan_video_url, created_at
            FROM jobs
            WHERE wan_status = 'completed' AND wan_video_url IS NOT NULL
            AND id IN ({placeholders})
            ORDER BY id
        """, job_ids)
    else:
        c.execute("""
            SELECT id, model, motion_prompt, wan_video_url, created_at
            FROM jobs
            WHERE wan_status = 'completed' AND wan_video_url IS NOT NULL
            ORDER BY id
        """)

    jobs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jobs


def download_video(url: str, output_path: Path) -> bool:
    """Download a video from URL."""
    try:
        with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"    Error downloading: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download completed videos")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("downloads"),
                       help="Output directory for videos")
    parser.add_argument("--job-ids", "-j", type=str, default=None,
                       help="Comma-separated job IDs to download (default: all)")
    parser.add_argument("--zip", "-z", action="store_true",
                       help="Create a zip file instead of individual files")
    parser.add_argument("--db", type=str, default="wan_jobs.db",
                       help="Path to database file")
    parser.add_argument("--list", "-l", action="store_true",
                       help="List completed jobs without downloading")

    args = parser.parse_args()

    # Parse job IDs if provided
    job_ids = None
    if args.job_ids:
        job_ids = [int(x.strip()) for x in args.job_ids.split(",")]

    # Get jobs
    jobs = get_completed_jobs(args.db, job_ids)

    if not jobs:
        print("No completed jobs found")
        return

    if args.list:
        print(f"Found {len(jobs)} completed videos:\n")
        for job in jobs:
            prompt_preview = job["motion_prompt"][:50] + "..." if len(job["motion_prompt"]) > 50 else job["motion_prompt"]
            print(f"  Job {job['id']} ({job['model']}): {prompt_preview}")
        return

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(jobs)} videos...\n")

    downloaded = []
    for job in jobs:
        filename = f"job_{job['id']}_{job['model']}.mp4"
        output_path = args.output_dir / filename

        print(f"[{job['id']}] Downloading {filename}...")

        if download_video(job["wan_video_url"], output_path):
            downloaded.append(output_path)
            print(f"    -> Saved to {output_path}")
        else:
            print(f"    -> Failed")

    print(f"\nDownloaded {len(downloaded)}/{len(jobs)} videos to {args.output_dir}")

    # Create zip if requested
    if args.zip and downloaded:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = args.output_dir / f"videos_{timestamp}.zip"

        print(f"\nCreating zip: {zip_path}")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for video_path in downloaded:
                zf.write(video_path, video_path.name)

        print(f"Zip created: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
