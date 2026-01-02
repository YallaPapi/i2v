import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Job


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestJobModel:
    def test_create_job(self, db_session):
        job = Job(
            image_url="https://example.com/test.jpg",
            motion_prompt="Camera zoom",
            resolution="1080p",
            duration_sec=5,
        )
        db_session.add(job)
        db_session.commit()

        assert job.id is not None
        assert job.wan_status == "pending"
        assert job.created_at is not None

    def test_job_defaults(self, db_session):
        job = Job(
            image_url="https://example.com/test.jpg",
            motion_prompt="Test",
        )
        db_session.add(job)
        db_session.commit()

        assert job.wan_status == "pending"
        assert job.wan_request_id is None
        assert job.wan_video_url is None
        assert job.error_message is None

    def test_job_repr(self, db_session):
        job = Job(
            image_url="https://example.com/test.jpg",
            motion_prompt="Test",
        )
        db_session.add(job)
        db_session.commit()

        repr_str = repr(job)
        assert "Job" in repr_str
        assert str(job.id) in repr_str
        assert job.wan_status in repr_str

    def test_job_to_dict(self, db_session):
        job = Job(
            image_url="https://example.com/test.jpg",
            motion_prompt="Test prompt",
            resolution="480p",
            duration_sec=10,
        )
        db_session.add(job)
        db_session.commit()

        job_dict = job.to_dict()

        assert job_dict["id"] == job.id
        assert job_dict["image_url"] == "https://example.com/test.jpg"
        assert job_dict["motion_prompt"] == "Test prompt"
        assert job_dict["resolution"] == "480p"
        assert job_dict["duration_sec"] == 10
        assert job_dict["wan_status"] == "pending"
        assert "created_at" in job_dict
        assert "updated_at" in job_dict

    def test_job_status_update(self, db_session):
        job = Job(
            image_url="https://example.com/test.jpg",
            motion_prompt="Test",
        )
        db_session.add(job)
        db_session.commit()

        original_updated_at = job.updated_at

        # Update status
        job.wan_status = "submitted"
        job.wan_request_id = "req_12345"
        db_session.commit()

        assert job.wan_status == "submitted"
        assert job.wan_request_id == "req_12345"
