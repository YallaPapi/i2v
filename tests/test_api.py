import pytest
from fastapi import status


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestCreateJob:
    def test_create_job_success(self, client):
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Camera zoom in slowly",
            "resolution": "1080p",
            "duration_sec": 5,
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        assert data["id"] == 1
        assert data["image_url"] == job_data["image_url"]
        assert data["motion_prompt"] == job_data["motion_prompt"]
        assert data["resolution"] == "1080p"
        assert data["duration_sec"] == 5
        assert data["wan_status"] == "pending"
        assert data["wan_video_url"] is None

    def test_create_job_with_defaults(self, client):
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Pan right",
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        assert data["resolution"] == "1080p"  # default
        assert data["duration_sec"] == 5  # default

    def test_create_job_invalid_resolution(self, client):
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
            "resolution": "4K",  # invalid
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_job_invalid_duration(self, client):
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
            "duration_sec": 15,  # invalid, only 5 or 10 allowed
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetJob:
    def test_get_job_success(self, client):
        # Create a job first
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test prompt",
        }
        create_response = client.post("/jobs", json=job_data)
        job_id = create_response.json()["id"]

        # Get the job
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == job_id

    def test_get_job_not_found(self, client):
        response = client.get("/jobs/999")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListJobs:
    def test_list_jobs_empty(self, client):
        response = client.get("/jobs")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_jobs_with_data(self, client):
        # Create some jobs
        for i in range(3):
            client.post("/jobs", json={
                "image_url": f"https://example.com/test{i}.jpg",
                "motion_prompt": f"Prompt {i}",
            })

        response = client.get("/jobs")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 3

    def test_list_jobs_filter_by_status(self, client):
        # Create a job (will be pending)
        client.post("/jobs", json={
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
        })

        # Filter by pending
        response = client.get("/jobs?status=pending")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1

        # Filter by completed (none)
        response = client.get("/jobs?status=completed")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_list_jobs_pagination(self, client):
        # Create 5 jobs
        for i in range(5):
            client.post("/jobs", json={
                "image_url": f"https://example.com/test{i}.jpg",
                "motion_prompt": f"Prompt {i}",
            })

        # Get first 2
        response = client.get("/jobs?limit=2&offset=0")
        assert len(response.json()) == 2

        # Get next 2
        response = client.get("/jobs?limit=2&offset=2")
        assert len(response.json()) == 2

        # Get last 1
        response = client.get("/jobs?limit=2&offset=4")
        assert len(response.json()) == 1
