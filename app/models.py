from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Index,
    Text,
    Numeric,
    ForeignKey,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import json

from app.database import Base


# ============== User Model ==============


class UserRole(str, enum.Enum):
    """User roles for access control."""
    ADMIN = "admin"
    MANAGER = "manager"  # OF manager (primary user type)
    USER = "user"  # Basic user


class UserTier(str, enum.Enum):
    """User subscription tiers."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    AGENCY = "agency"


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Profile
    name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Role and tier
    role = Column(String(20), default=UserRole.MANAGER.value, nullable=False)
    tier = Column(String(20), default=UserTier.STARTER.value, nullable=False)

    # Credits
    credits_balance = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    model_profiles = relationship("ModelProfile", back_populates="user", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_role", "role"),
        Index("idx_user_tier", "tier"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role}, tier={self.tier})>"

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "is_active": self.is_active,
            "role": self.role,
            "tier": self.tier,
            "credits_balance": self.credits_balance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }
        if include_sensitive:
            data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data


class ModelProfile(Base):
    """Model profile for storing face references and identity settings."""

    __tablename__ = "model_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Face reference images (JSON array of R2 URLs)
    face_images = Column(Text, nullable=True)

    # Style preferences (JSON)
    body_type = Column(String(50), nullable=True)
    style_preferences = Column(Text, nullable=True)  # JSON

    # Voice clone (for future audio features)
    voice_clone_id = Column(String(255), nullable=True)

    # Verification status (for real-person content)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_status = Column(String(20), default="unverified", nullable=False)  # unverified, pending, approved, rejected

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="model_profiles")

    __table_args__ = (
        Index("idx_model_profile_user", "user_id"),
        Index("idx_model_profile_verified", "is_verified"),
    )

    def __repr__(self) -> str:
        return f"<ModelProfile(id={self.id}, name={self.name}, user_id={self.user_id})>"

    def get_face_images(self) -> list:
        """Parse face_images JSON."""
        if self.face_images:
            return json.loads(self.face_images)
        return []

    def set_face_images(self, images: list):
        """Set face_images as JSON."""
        self.face_images = json.dumps(images)

    def get_style_preferences(self) -> dict:
        """Parse style_preferences JSON."""
        if self.style_preferences:
            return json.loads(self.style_preferences)
        return {}

    def set_style_preferences(self, prefs: dict):
        """Set style_preferences as JSON."""
        self.style_preferences = json.dumps(prefs)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "face_images": self.get_face_images(),
            "body_type": self.body_type,
            "style_preferences": self.get_style_preferences(),
            "voice_clone_id": self.voice_clone_id,
            "is_verified": self.is_verified,
            "verification_status": self.verification_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CreditTransaction(Base):
    """Credit transaction ledger for tracking all credit changes."""

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Transaction details
    amount = Column(Integer, nullable=False)  # Positive = credit, negative = debit
    balance_after = Column(Integer, nullable=False)  # Balance after this transaction
    description = Column(String(500), nullable=False)

    # Reference to what caused this transaction
    source = Column(String(50), nullable=False)  # payment, job, manual, promo, refund
    reference_id = Column(String(255), nullable=True)  # job_id, payment_id, etc.

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="credit_transactions")

    __table_args__ = (
        Index("idx_credit_tx_user", "user_id"),
        Index("idx_credit_tx_source", "source"),
        Index("idx_credit_tx_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CreditTransaction(id={self.id}, user_id={self.user_id}, amount={self.amount})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "description": self.description,
            "source": self.source,
            "reference_id": self.reference_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============== Batch Job Models ==============


class BatchJobStatus(str, enum.Enum):
    """Batch job status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class BatchJobOutputType(str, enum.Enum):
    """Type of output for batch job."""
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    PIPELINE = "pipeline"  # Full image → video → audio → lipsync


class BatchJob(Base):
    """Batch generation job for bulk content creation (100+ items)."""

    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID string
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Job configuration
    template_id = Column(String(255), nullable=True)  # Reference to template
    model_profile_id = Column(Integer, ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True)
    output_type = Column(String(20), default=BatchJobOutputType.IMAGE.value, nullable=False)
    quantity = Column(Integer, nullable=False)

    # Generation settings (JSON)
    config = Column(Text, nullable=True)  # model, quality, aspect_ratio, duration, etc.

    # Status and progress
    status = Column(String(20), default=BatchJobStatus.QUEUED.value, nullable=False)
    completed_items = Column(Integer, default=0, nullable=False)
    failed_items = Column(Integer, default=0, nullable=False)
    pending_items = Column(Integer, default=0, nullable=False)

    # Cost tracking
    credits_charged = Column(Integer, default=0, nullable=False)
    credits_refunded = Column(Integer, default=0, nullable=False)

    # ETA and timing
    estimated_completion = Column(DateTime, nullable=True)
    avg_item_duration_ms = Column(Integer, nullable=True)  # Moving average

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="batch_jobs")
    model_profile = relationship("ModelProfile", backref="batch_jobs")
    items = relationship("BatchJobItem", back_populates="batch_job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_batch_job_user", "user_id"),
        Index("idx_batch_job_status", "status"),
        Index("idx_batch_job_created", "created_at"),
        Index("idx_batch_job_uuid", "job_id"),
    )

    def __repr__(self) -> str:
        return f"<BatchJob(id={self.id}, job_id={self.job_id}, status={self.status}, progress={self.completed_items}/{self.quantity})>"

    def get_config(self) -> dict:
        """Parse config JSON."""
        if self.config:
            return json.loads(self.config)
        return {}

    def set_config(self, config: dict):
        """Set config as JSON."""
        self.config = json.dumps(config)

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.quantity == 0:
            return 100.0
        return round((self.completed_items + self.failed_items) / self.quantity * 100, 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "template_id": self.template_id,
            "model_profile_id": self.model_profile_id,
            "output_type": self.output_type,
            "quantity": self.quantity,
            "config": self.get_config(),
            "status": self.status,
            "completed_items": self.completed_items,
            "failed_items": self.failed_items,
            "pending_items": self.pending_items,
            "progress_percent": self.progress_percent,
            "credits_charged": self.credits_charged,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error_message": self.error_message,
        }


class BatchJobItemStatus(str, enum.Enum):
    """Individual item status within a batch job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchJobItem(Base):
    """Individual item within a batch job."""

    __tablename__ = "batch_job_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_job_id = Column(Integer, ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False)
    item_index = Column(Integer, nullable=False)  # 0-based index within batch

    # Item-specific config (variations from template)
    prompt = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    variation_params = Column(Text, nullable=True)  # JSON for costume, pose, etc.

    # Status
    status = Column(String(20), default=BatchJobItemStatus.PENDING.value, nullable=False)

    # Result
    result_url = Column(String(1000), nullable=True)  # R2/fal.ai URL
    thumbnail_url = Column(String(1000), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    batch_job = relationship("BatchJob", back_populates="items")

    __table_args__ = (
        Index("idx_batch_item_job", "batch_job_id"),
        Index("idx_batch_item_status", "status"),
        Index("idx_batch_item_index", "batch_job_id", "item_index"),
    )

    def __repr__(self) -> str:
        return f"<BatchJobItem(id={self.id}, job={self.batch_job_id}, idx={self.item_index}, status={self.status})>"

    def get_variation_params(self) -> dict:
        """Parse variation_params JSON."""
        if self.variation_params:
            return json.loads(self.variation_params)
        return {}

    def set_variation_params(self, params: dict):
        """Set variation_params as JSON."""
        self.variation_params = json.dumps(params)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_job_id": self.batch_job_id,
            "item_index": self.item_index,
            "prompt": self.prompt,
            "caption": self.caption,
            "variation_params": self.get_variation_params(),
            "status": self.status,
            "result_url": self.result_url,
            "thumbnail_url": self.thumbnail_url,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


# ============== Template Models ==============


class TemplateCategory(str, enum.Enum):
    """Template categories."""
    SOCIAL_SFW = "social_sfw"  # Instagram/TikTok safe content
    NSFW = "nsfw"  # Adult content
    BRAINROT = "brainrot"  # Viral/meme content
    CAROUSEL = "carousel"  # Multi-slide posts


class TemplateOutputType(str, enum.Enum):
    """Template output types."""
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    PIPELINE = "pipeline"  # Full image → video → audio → lipsync


class Template(Base):
    """Template model for generation recipes/presets."""

    __tablename__ = "templates"

    id = Column(String(100), primary_key=True)  # Slug like "cosplay-thirst-trap"
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(20), default=TemplateCategory.SOCIAL_SFW.value, nullable=False)
    output_type = Column(String(20), default=TemplateOutputType.IMAGE.value, nullable=False)

    # Generation settings
    base_prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    variables = Column(Text, nullable=True)  # JSON: {costume: [...], pose: [...], setting: [...]}
    caption_templates = Column(Text, nullable=True)  # JSON array of caption strings with {var} placeholders

    # Model recommendations
    recommended_model = Column(String(100), nullable=True)  # For image: flux-2-pro, gpt-image-1.5
    video_model = Column(String(100), nullable=True)  # For video output: kling, wan

    # Output settings
    aspect_ratio = Column(String(10), default="9:16", nullable=False)
    duration_sec = Column(Integer, nullable=True)  # For video templates
    quality = Column(String(20), default="high", nullable=False)

    # Carousel-specific (JSON)
    slides = Column(Text, nullable=True)  # JSON array of slide configs for carousel templates

    # Access control
    tier_required = Column(String(20), default="starter", nullable=False)  # Min tier to use
    is_nsfw = Column(Integer, default=0, nullable=False)  # SQLite bool
    is_active = Column(Integer, default=1, nullable=False)
    is_featured = Column(Integer, default=0, nullable=False)

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    tags = Column(Text, nullable=True)  # JSON array

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_template_category", "category"),
        Index("idx_template_output", "output_type"),
        Index("idx_template_active", "is_active"),
        Index("idx_template_featured", "is_featured"),
        Index("idx_template_tier", "tier_required"),
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, name={self.name}, category={self.category})>"

    def get_variables(self) -> dict:
        """Parse variables JSON."""
        if self.variables:
            return json.loads(self.variables)
        return {}

    def set_variables(self, variables: dict):
        """Set variables as JSON."""
        self.variables = json.dumps(variables)

    def get_caption_templates(self) -> list:
        """Parse caption_templates JSON."""
        if self.caption_templates:
            return json.loads(self.caption_templates)
        return []

    def set_caption_templates(self, captions: list):
        """Set caption_templates as JSON."""
        self.caption_templates = json.dumps(captions)

    def get_slides(self) -> list:
        """Parse slides JSON for carousel templates."""
        if self.slides:
            return json.loads(self.slides)
        return []

    def set_slides(self, slides: list):
        """Set slides as JSON."""
        self.slides = json.dumps(slides)

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
            "description": self.description,
            "category": self.category,
            "output_type": self.output_type,
            "base_prompt": self.base_prompt,
            "negative_prompt": self.negative_prompt,
            "variables": self.get_variables(),
            "caption_templates": self.get_caption_templates(),
            "recommended_model": self.recommended_model,
            "video_model": self.video_model,
            "aspect_ratio": self.aspect_ratio,
            "duration_sec": self.duration_sec,
            "quality": self.quality,
            "slides": self.get_slides(),
            "tier_required": self.tier_required,
            "is_nsfw": bool(self.is_nsfw),
            "is_active": bool(self.is_active),
            "is_featured": bool(self.is_featured),
            "usage_count": self.usage_count,
            "tags": self.get_tags(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


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
    is_favorite = Column(
        Integer, nullable=False, default=0
    )  # SQLite uses INTEGER for bool
    is_hidden = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships - lazy='select' prevents eager loading in list views
    steps = relationship(
        "PipelineStep",
        back_populates="pipeline",
        order_by="PipelineStep.step_order",
        cascade="all, delete-orphan",
        lazy="select",
    )

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
    pipeline_id = Column(
        Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
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
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

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
    provider = Column(String, nullable=False, default="fal")  # 'fal' or 'runpod'

    # Wan/Fal tracking
    wan_request_id = Column(String, nullable=True)
    wan_status = Column(String, nullable=False, default="pending")
    wan_video_url = Column(String, nullable=True)
    local_video_path = Column(String, nullable=True)  # Path to downloaded video
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id}, status={self.wan_status}, created={self.created_at})>"
        )

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
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

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
            "result_image_urls": (
                json.loads(self.result_image_urls) if self.result_image_urls else None
            ),
            "local_image_paths": (
                json.loads(self.local_image_paths) if self.local_image_paths else None
            ),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
