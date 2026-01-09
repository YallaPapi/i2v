"""Templates router for generation recipe management."""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from app.database import get_db
from app.models import User, Template, TemplateCategory, TemplateOutputType
from app.core.security import get_current_user, require_role

logger = structlog.get_logger()

router = APIRouter(prefix="/templates", tags=["templates"])


# ============== Schemas ==============


class VariablesSchema(BaseModel):
    """Schema for template variables."""
    costume: Optional[List[str]] = None
    pose: Optional[List[str]] = None
    setting: Optional[List[str]] = None
    expression: Optional[List[str]] = None
    lighting: Optional[List[str]] = None
    # Allow additional custom variables
    class Config:
        extra = "allow"


class TemplateCreate(BaseModel):
    """Request to create a template."""
    id: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = Field(default="social_sfw")
    output_type: str = Field(default="image")
    base_prompt: str = Field(...)
    negative_prompt: Optional[str] = None
    variables: Optional[dict] = None
    caption_templates: Optional[List[str]] = None
    recommended_model: Optional[str] = None
    video_model: Optional[str] = None
    aspect_ratio: str = Field(default="9:16")
    duration_sec: Optional[int] = None
    quality: str = Field(default="high")
    slides: Optional[List[dict]] = None
    tier_required: str = Field(default="starter")
    is_nsfw: bool = Field(default=False)
    is_featured: bool = Field(default=False)
    tags: Optional[List[str]] = None


class TemplateUpdate(BaseModel):
    """Request to update a template."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    output_type: Optional[str] = None
    base_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    variables: Optional[dict] = None
    caption_templates: Optional[List[str]] = None
    recommended_model: Optional[str] = None
    video_model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    duration_sec: Optional[int] = None
    quality: Optional[str] = None
    slides: Optional[List[dict]] = None
    tier_required: Optional[str] = None
    is_nsfw: Optional[bool] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    tags: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    """Response for a template."""
    id: str
    name: str
    description: Optional[str]
    category: str
    output_type: str
    base_prompt: str
    negative_prompt: Optional[str]
    variables: dict
    caption_templates: List[str]
    recommended_model: Optional[str]
    video_model: Optional[str]
    aspect_ratio: str
    duration_sec: Optional[int]
    quality: str
    slides: List[dict]
    tier_required: str
    is_nsfw: bool
    is_active: bool
    is_featured: bool
    usage_count: int
    tags: List[str]
    created_at: str
    updated_at: str


class TemplateListResponse(BaseModel):
    """Response for template list."""
    templates: List[TemplateResponse]
    total: int


class TemplateSummary(BaseModel):
    """Summary view of template for listing."""
    id: str
    name: str
    description: Optional[str]
    category: str
    output_type: str
    recommended_model: Optional[str]
    tier_required: str
    is_nsfw: bool
    is_featured: bool
    usage_count: int
    tags: List[str]


# ============== Public Endpoints ==============


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    output_type: Optional[str] = Query(None, description="Filter by output type"),
    featured: Optional[bool] = Query(None, description="Filter featured only"),
    nsfw: Optional[bool] = Query(None, description="Filter by NSFW status"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List available templates.

    - Filters by category, output_type, featured status
    - Only shows active templates
    - Respects user tier for access
    """
    query = db.query(Template).filter(Template.is_active == 1)

    # Apply filters
    if category:
        query = query.filter(Template.category == category)
    if output_type:
        query = query.filter(Template.output_type == output_type)
    if featured is not None:
        query = query.filter(Template.is_featured == (1 if featured else 0))
    if nsfw is not None:
        query = query.filter(Template.is_nsfw == (1 if nsfw else 0))
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Template.name.ilike(search_term)) |
            (Template.description.ilike(search_term))
        )

    # Filter by user tier if authenticated
    if user:
        tier_order = {"free": 0, "starter": 1, "pro": 2, "agency": 3}
        user_tier_level = tier_order.get(user.tier, 1)
        # Show templates up to user's tier
        allowed_tiers = [t for t, level in tier_order.items() if level <= user_tier_level]
        query = query.filter(Template.tier_required.in_(allowed_tiers))

    total = query.count()
    templates = query.order_by(Template.is_featured.desc(), Template.usage_count.desc()).offset(offset).limit(limit).all()

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category,
                output_type=t.output_type,
                base_prompt=t.base_prompt,
                negative_prompt=t.negative_prompt,
                variables=t.get_variables(),
                caption_templates=t.get_caption_templates(),
                recommended_model=t.recommended_model,
                video_model=t.video_model,
                aspect_ratio=t.aspect_ratio,
                duration_sec=t.duration_sec,
                quality=t.quality,
                slides=t.get_slides(),
                tier_required=t.tier_required,
                is_nsfw=bool(t.is_nsfw),
                is_active=bool(t.is_active),
                is_featured=bool(t.is_featured),
                usage_count=t.usage_count,
                tags=t.get_tags(),
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in templates
        ],
        total=total,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific template by ID."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.is_active:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check tier access
    if user:
        tier_order = {"free": 0, "starter": 1, "pro": 2, "agency": 3}
        user_tier = tier_order.get(user.tier, 1)
        template_tier = tier_order.get(template.tier_required, 1)
        if user_tier < template_tier:
            raise HTTPException(
                status_code=403,
                detail=f"This template requires {template.tier_required} tier or higher"
            )

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_type=template.output_type,
        base_prompt=template.base_prompt,
        negative_prompt=template.negative_prompt,
        variables=template.get_variables(),
        caption_templates=template.get_caption_templates(),
        recommended_model=template.recommended_model,
        video_model=template.video_model,
        aspect_ratio=template.aspect_ratio,
        duration_sec=template.duration_sec,
        quality=template.quality,
        slides=template.get_slides(),
        tier_required=template.tier_required,
        is_nsfw=bool(template.is_nsfw),
        is_active=bool(template.is_active),
        is_featured=bool(template.is_featured),
        usage_count=template.usage_count,
        tags=template.get_tags(),
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.get("/categories/list")
async def list_categories():
    """List available template categories."""
    return {
        "categories": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in TemplateCategory
        ]
    }


# ============== Admin Endpoints ==============


@router.post("/admin", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to create a new template."""
    # Check ID doesn't exist
    existing = db.query(Template).filter(Template.id == request.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Template ID already exists")

    template = Template(
        id=request.id,
        name=request.name,
        description=request.description,
        category=request.category,
        output_type=request.output_type,
        base_prompt=request.base_prompt,
        negative_prompt=request.negative_prompt,
        recommended_model=request.recommended_model,
        video_model=request.video_model,
        aspect_ratio=request.aspect_ratio,
        duration_sec=request.duration_sec,
        quality=request.quality,
        tier_required=request.tier_required,
        is_nsfw=1 if request.is_nsfw else 0,
        is_featured=1 if request.is_featured else 0,
        is_active=1,
        created_by=admin.id,
    )

    if request.variables:
        template.set_variables(request.variables)
    if request.caption_templates:
        template.set_caption_templates(request.caption_templates)
    if request.slides:
        template.set_slides(request.slides)
    if request.tags:
        template.set_tags(request.tags)

    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info("Template created", template_id=template.id, admin_id=admin.id)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_type=template.output_type,
        base_prompt=template.base_prompt,
        negative_prompt=template.negative_prompt,
        variables=template.get_variables(),
        caption_templates=template.get_caption_templates(),
        recommended_model=template.recommended_model,
        video_model=template.video_model,
        aspect_ratio=template.aspect_ratio,
        duration_sec=template.duration_sec,
        quality=template.quality,
        slides=template.get_slides(),
        tier_required=template.tier_required,
        is_nsfw=bool(template.is_nsfw),
        is_active=bool(template.is_active),
        is_featured=bool(template.is_featured),
        usage_count=template.usage_count,
        tags=template.get_tags(),
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.patch("/admin/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to update a template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Update fields
    update_data = request.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "variables" and value is not None:
            template.set_variables(value)
        elif field == "caption_templates" and value is not None:
            template.set_caption_templates(value)
        elif field == "slides" and value is not None:
            template.set_slides(value)
        elif field == "tags" and value is not None:
            template.set_tags(value)
        elif field in ["is_nsfw", "is_active", "is_featured"]:
            setattr(template, field, 1 if value else 0)
        elif hasattr(template, field):
            setattr(template, field, value)

    db.commit()
    db.refresh(template)

    logger.info("Template updated", template_id=template_id, admin_id=admin.id)

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        output_type=template.output_type,
        base_prompt=template.base_prompt,
        negative_prompt=template.negative_prompt,
        variables=template.get_variables(),
        caption_templates=template.get_caption_templates(),
        recommended_model=template.recommended_model,
        video_model=template.video_model,
        aspect_ratio=template.aspect_ratio,
        duration_sec=template.duration_sec,
        quality=template.quality,
        slides=template.get_slides(),
        tier_required=template.tier_required,
        is_nsfw=bool(template.is_nsfw),
        is_active=bool(template.is_active),
        is_featured=bool(template.is_featured),
        usage_count=template.usage_count,
        tags=template.get_tags(),
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.delete("/admin/{template_id}")
async def delete_template(
    template_id: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Admin endpoint to delete (deactivate) a template."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Soft delete - just deactivate
    template.is_active = 0
    db.commit()

    logger.info("Template deleted", template_id=template_id, admin_id=admin.id)
    return {"success": True, "message": "Template deactivated"}
