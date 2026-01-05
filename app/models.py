from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index, Text, Numeric, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import json

from app.database import Base


# ============== Pipeline Enums ==============

class PipelineStatus(str, enum.Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineMode(str, enum.Enum):
    """Pipeline execution mode."""
    MANUAL = "manual"
    AUTO = "auto"
    CHECKPOINT = "checkpoint"


class StepType(str, enum.Enum):
    """Pipeline step types."""
    PROMPT_ENHANCE = "prompt_enhance"
    I2I = "i2i"
    I2V = "i2v"


class StepStatus(str, enum.Enum):
    """Pipeline step status."""
    PENDING = "pending"
    RUNNING = "running"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


# ============== Pipeline Models ==============

class Pipeline(Base):
    """Pipeline model for chaining generation steps."""

    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default=PipelineStatus.PENDING.value)
    mode = Column(String(20), nullable=False, default=PipelineMode.MANUAL.value)
    checkpoints = Column(Text, nullable=True)  # JSON array of step types that pause

    # Categorization fields
    tags = Column(Text, nullable=True)  # JSON array of tag strings
    is_favorite = Column(Integer, nullable=False, default=0)  # SQLite uses INTEGER for bool
    is_hidden = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships - lazy='select' prevents eager loading in list views
    steps = relationship("PipelineStep", back_populates="pipeline", order_by="PipelineStep.step_order", cascade="all, delete-orphan", lazy="select")

    __table_args__ = (
        Index("idx_pipeline_status", "status"),
        Index("idx_pipeline_favorite", "is_favorite"),
        Index("idx_pipeline_hidden", "is_hidden"),
        Index("idx_pipeline_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Pipeline(id={self.id}, name={self.name}, status={self.status})>"

    def get_checkpoints(self) -> list:
        """Parse checkpoints JSON."""
        if self.checkpoints:
            return json.loads(self.checkpoints)
        return []

    def set_checkpoints(self, checkpoints: list):
        """Set checkpoints as JSON."""
        self.checkpoints = json.dumps(checkpoints)

    def get_tags(self) -> list:
        """Parse tags JSON."""
        if self.tags:
            return json.loads(self.tags)
        return []

    def set_tags(self, tags: list):
        """Set tags as JSON."""
        self.tags = json.dumps(tags)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "mode": self.mode,
            "checkpoints": self.get_checkpoints(),
            "tags": self.get_tags(),
            "is_favorite": bool(self.is_favorite),
            "is_hidden": bool(self.is_hidden),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "steps": [step.to_dict() for step in self.steps] if self.steps else [],
        }


class PipelineStep(Base):
    """Individual step within a pipeline."""

    __tablename__ = "pipeline_steps"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    step_type = Column(String(20), nullable=False)  # prompt_enhance, i2i, i2v
    step_order = Column(Integer, nullable=False)
    config = Column(Text, nullable=True)  # JSON config
    status = Column(String(20), nullable=False, default=StepStatus.PENDING.value)
    inputs = Column(Text, nullable=True)  # JSON inputs (image_urls, prompts)
    outputs = Column(Text, nullable=True)  # JSON outputs (generated content)
    cost_estimate = Column(Numeric(10, 4), nullable=True)
    cost_actual = Column(Numeric(10, 4), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="steps")

    __table_args__ = (
        Index("idx_step_pipeline", "pipeline_id"),
        Index("idx_step_status", "status"),
        Index("idx_step_order", "pipeline_id", "step_order"),
    )

    def __repr__(self) -> str:
        return f"<PipelineStep(id={self.id}, type={self.step_type}, order={self.step_order}, status={self.status})>"

    def get_config(self) -> dict:
        """Parse config JSON."""
        if self.config:
            return json.loads(self.config)
        return {}

    def set_config(self, config: dict):
        """Set config as JSON."""
        self.config = json.dumps(config)

    def get_inputs(self) -> dict:
        """Parse inputs JSON."""
        if self.inputs:
            return json.loads(self.inputs)
        return {}

    def set_inputs(self, inputs: dict):
        """Set inputs as JSON."""
        self.inputs = json.dumps(inputs)

    def get_outputs(self) -> dict:
        """Parse outputs JSON."""
        if self.outputs:
            return json.loads(self.outputs)
        return {}

    def set_outputs(self, outputs: dict):
        """Set outputs as JSON."""
        self.outputs = json.dumps(outputs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "step_type": self.step_type,
            "step_order": self.step_order,
            "config": self.get_config(),
            "status": self.status,
            "inputs": self.get_inputs(),
            "outputs": self.get_outputs(),
            "cost_estimate": float(self.cost_estimate) if self.cost_estimate else None,
            "cost_actual": float(self.cost_actual) if self.cost_actual else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UploadCache(Base):
    """Cache for uploaded images to Fal CDN."""

    __tablename__ = "upload_cache"

    id = Column(Integer, primary_key=True, index=True)
    local_path = Column(String, unique=True, nullable=False)
    file_hash = Column(String, nullable=False, index=True)
    fal_url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_upload_cache_path", "local_path"),
        Index("idx_upload_cache_hash", "file_hash"),
    )

    def __repr__(self) -> str:
        return f"<UploadCache(id={self.id}, path={self.local_path}, url={self.fal_url[:50]}...)>"


class Job(Base):
    """SQLAlchemy model for video generation jobs."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    motion_prompt = Column(String, nullable=False)
    negative_prompt = Column(String, nullable=True)
    resolution = Column(String, nullable=False, default="1080p")
    duration_sec = Column(Integer, nullable=False, default=5)
    model = Column(String, nullable=False, default="wan")

    # Wan/Fal tracking
    wan_request_id = Column(String, nullable=True)
    wan_status = Column(String, nullable=False, default="pending")
    wan_video_url = Column(String, nullable=True)
    local_video_path = Column(String, nullable=True)  # Path to downloaded video
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, status={self.wan_status}, created={self.created_at})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "image_url": self.image_url,
            "motion_prompt": self.motion_prompt,
            "negative_prompt": self.negative_prompt,
            "resolution": self.resolution,
            "duration_sec": self.duration_sec,
            "model": self.model,
            "wan_request_id": self.wan_request_id,
            "wan_status": self.wan_status,
            "wan_video_url": self.wan_video_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ImageJob(Base):
    """SQLAlchemy model for image generation jobs."""

    __tablename__ = "image_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_image_url = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    negative_prompt = Column(String, nullable=True)
    model = Column(String, nullable=False, default="gpt-image-1.5")
    aspect_ratio = Column(String, nullable=False, default="9:16")
    quality = Column(String, nullable=False, default="high")
    num_images = Column(Integer, nullable=False, default=1)

    # Fal tracking
    request_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    result_image_urls = Column(String, nullable=True)  # JSON array of URLs
    local_image_paths = Column(String, nullable=True)  # JSON array of local paths
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<ImageJob(id={self.id}, model={self.model}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary for JSON serialization."""
        import json
        return {
            "id": self.id,
            "source_image_url": self.source_image_url,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "model": self.model,
            "aspect_ratio": self.aspect_ratio,
            "quality": self.quality,
            "num_images": self.num_images,
            "request_id": self.request_id,
            "status": self.status,
            "result_image_urls": json.loads(self.result_image_urls) if self.result_image_urls else None,
            "local_image_paths": json.loads(self.local_image_paths) if self.local_image_paths else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
