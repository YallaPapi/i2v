"""NSFW prompt generation endpoints using local Ollama."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

from app.services.nsfw_prompt_generator import (
    check_ollama_available,
    list_ollama_models,
    generate_nsfw_prompts,
    generate_single_nsfw_prompt,
    generate_nsfw_caption,
)

router = APIRouter(prefix="/nsfw", tags=["NSFW Generation"])


class NSFWPromptRequest(BaseModel):
    """Request to generate NSFW prompts."""
    count: int = 5
    style: Literal["lingerie", "nude", "cosplay_lewd"] = "lingerie"
    model: str = "dolphin-llama3"
    character: str | None = None
    include_caption: bool = True


class NSFWSinglePromptRequest(BaseModel):
    """Request to generate a single NSFW prompt from description."""
    description: str
    model: str = "dolphin-llama3"
    include_caption: bool = True


class NSFWCaptionRequest(BaseModel):
    """Request to generate an NSFW caption."""
    category: Literal[
        "thirst_trap", "pov_explicit", "breeding",
        "submissive", "dominant", "exhibitionist"
    ] | None = None
    model: str = "dolphin-llama3"
    character: str | None = None


@router.get("/status")
async def check_status() -> dict:
    """Check if Ollama is available for NSFW generation."""
    available = await check_ollama_available()
    models = await list_ollama_models() if available else []

    return {
        "ollama_available": available,
        "models": models,
        "recommended_models": [
            "dolphin-mixtral",
            "dolphin-llama3",
            "nous-hermes2",
        ],
    }


@router.get("/models")
async def get_models() -> dict:
    """List available Ollama models."""
    models = await list_ollama_models()
    return {"models": models}


@router.post("/prompts")
async def generate_prompts(request: NSFWPromptRequest) -> dict:
    """
    Generate multiple NSFW prompts.

    Uses local Ollama with uncensored models for explicit content.
    No content filters, completely private.
    """
    available = await check_ollama_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start Ollama with: ollama serve"
        )

    prompts = await generate_nsfw_prompts(
        count=request.count,
        style=request.style,
        model=request.model,
        character=request.character,
        include_caption=request.include_caption,
    )

    return {
        "prompts": prompts,
        "count": len(prompts),
        "style": request.style,
        "model": request.model,
    }


@router.post("/prompt")
async def generate_prompt(request: NSFWSinglePromptRequest) -> dict:
    """
    Generate a single NSFW prompt from natural language description.

    Example: "anime girl in maid outfit bent over table"
    """
    available = await check_ollama_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start Ollama with: ollama serve"
        )

    prompt = await generate_single_nsfw_prompt(
        description=request.description,
        model=request.model,
        include_caption=request.include_caption,
    )

    if not prompt:
        raise HTTPException(status_code=500, detail="Failed to generate prompt")

    return {
        "prompt": prompt,
        "model": request.model,
    }


@router.post("/caption")
async def generate_caption(request: NSFWCaptionRequest) -> dict:
    """Generate an NSFW TikTok-style caption."""
    available = await check_ollama_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start Ollama with: ollama serve"
        )

    caption = await generate_nsfw_caption(
        model=request.model,
        category=request.category,
        character=request.character,
    )

    return {
        "caption": caption,
        "category": request.category,
    }
