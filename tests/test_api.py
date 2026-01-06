from fastapi import status


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    def test_api_health_returns_ok(self, client):
        """Test /api/health endpoint for frontend connectivity."""
        response = client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestStatusEndpoint:
    def test_api_status_returns_counts(self, client):
        """Test /api/status returns job counts by status."""
        response = client.get("/api/status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "jobs" in data
        assert "pending" in data["jobs"]
        assert "completed" in data["jobs"]

    def test_api_status_counts_jobs(self, client):
        """Test /api/status counts jobs correctly."""
        # Create some jobs
        for i in range(3):
            client.post("/jobs", json={
                "image_url": f"https://example.com/test{i}.jpg",
                "motion_prompt": f"Test {i}",
            })

        response = client.get("/api/status")
        data = response.json()
        assert data["jobs"]["pending"] == 3


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

    def test_create_job_model_resolution_validation(self, client):
        """Test that model-specific resolution validation works."""
        # wan21 only supports 480p and 720p, not 1080p
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
            "model": "wan21",
            "resolution": "1080p",  # invalid for wan21
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_job_valid_model_resolution(self, client):
        """Test valid model/resolution combinations work."""
        # wan21 with valid 720p
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
            "model": "wan21",
            "resolution": "720p",
        }
        response = client.post("/jobs", json=job_data)
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_job_veo2_only_720p(self, client):
        """Test veo2 only accepts 720p."""
        # veo2 only supports 720p
        job_data = {
            "image_url": "https://example.com/test.jpg",
            "motion_prompt": "Test",
            "model": "veo2",
            "resolution": "1080p",  # invalid for veo2
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
