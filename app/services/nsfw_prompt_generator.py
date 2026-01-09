"""NSFW Prompt Generator using local Ollama models.

This module provides NSFW prompt generation using uncensored local LLMs
via Ollama. No content filters, completely private and local.

Recommended models:
- dolphin-mixtral (best quality, needs ~26GB VRAM)
- dolphin-llama3 (good quality, ~8GB VRAM)
- nous-hermes2 (fast, ~4GB VRAM)
"""

import os
import httpx
import structlog
import random
from typing import Literal

logger = structlog.get_logger()

OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# NSFW caption categories - explicit versions
NSFW_CAPTION_CATEGORIES = {
    "thirst_trap": """Create a thirst trap caption that's overtly sexual.
Examples:
- "come ruin me"
- "your face, my thighs, now"
- "i need to be used"
- "mount me like you mean it"
All lowercase, no periods. Direct and explicit.""",

    "pov_explicit": """Create a POV caption for an explicit scenario.
Examples:
- "pov: you're about to destroy me"
- "pov: i'm begging for round 3"
- "when he goes deeper than expected:"
- "pov: you found my onlyfans"
All lowercase, no periods. Sexual tension.""",

    "breeding": """Create a breeding/impregnation themed caption.
Examples:
- "put a baby in me challenge"
- "breed me like you hate me"
- "don't pull out this time"
- "make me a mom"
All lowercase, no periods. Primal energy.""",

    "submissive": """Create a submissive/degradation themed caption.
Examples:
- "use me however you want"
- "i'll be your good girl"
- "wreck me daddy"
- "treat me like i'm nothing"
All lowercase, no periods. Power exchange.""",

    "dominant": """Create a dominant/femdom themed caption.
Examples:
- "on your knees, now"
- "you'll cum when i say"
- "beg for it"
- "worship me"
All lowercase, no periods. Commanding tone.""",

    "exhibitionist": """Create an exhibitionist/public themed caption.
Examples:
- "anyone could walk in rn"
- "hope the neighbors are watching"
- "door's unlocked btw"
- "making content at work again"
All lowercase, no periods. Risky/public vibe.""",
}

# NSFW scene descriptions for different styles
NSFW_STYLES = {
    "lingerie": {
        "outfits": [
            "sheer black lace lingerie set",
            "red satin bra and thong",
            "white bridal lingerie with garter belt",
            "mesh bodysuit showing everything",
            "open-cup bra with crotchless panties",
            "leather harness over bare skin",
        ],
        "poses": [
            "on all fours on the bed",
            "spreading legs while lying back",
            "bent over showing ass",
            "hands bound above head",
            "straddling position",
            "kneeling with back arched",
        ],
    },
    "nude": {
        "outfits": [
            "completely nude",
            "nude with only thigh-high stockings",
            "nude with collar and leash",
            "nude covered only by hands",
            "nude with body oil glistening",
        ],
        "poses": [
            "full frontal standing",
            "lying on back legs spread",
            "doggy position from behind",
            "squatting position",
            "riding position on top",
        ],
    },
    "cosplay_lewd": {
        "outfits": [
            "slutty schoolgirl uniform barely covering anything",
            "lewd maid outfit with exposed breasts",
            "bunny suit with crotch cutout",
            "bikini version of character costume",
            "torn/destroyed cosplay showing skin",
        ],
        "poses": [
            "ahegao face tongue out",
            "on knees looking up",
            "bending over desk",
            "legs spread on bed",
            "riding position",
        ],
    },
}


async def check_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


async def list_ollama_models() -> list[str]:
    """List available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error("Failed to list Ollama models", error=str(e))
    return []


async def generate_nsfw_caption(
    model: str = "dolphin-llama3",
    category: str | None = None,
    character: str | None = None,
) -> str:
    """Generate an NSFW caption using Ollama."""

    if category is None:
        category = random.choice(list(NSFW_CAPTION_CATEGORIES.keys()))

    category_prompt = NSFW_CAPTION_CATEGORIES.get(category, NSFW_CAPTION_CATEGORIES["thirst_trap"])

    character_context = ""
    if character:
        character_context = f"\nThe caption should reference {character} from anime/games in a sexual context."

    prompt = f"""You are an expert at writing viral TikTok/Instagram captions for adult content creators.

{category_prompt}
{character_context}

Generate ONE caption only. No explanation, just the caption text.
Caption:"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.9,
                        "top_p": 0.95,
                    }
                }
            )
            if response.status_code == 200:
                data = response.json()
                caption = data.get("response", "").strip()
                # Clean up caption
                caption = caption.lower().replace(".", "").strip('"\'')
                return caption
    except Exception as e:
        logger.error("Failed to generate NSFW caption", error=str(e))

    return "come use me"  # Fallback


async def generate_nsfw_prompts(
    count: int = 5,
    style: Literal["lingerie", "nude", "cosplay_lewd"] = "lingerie",
    model: str = "dolphin-llama3",
    character: str | None = None,
    include_caption: bool = True,
) -> list[str]:
    """
    Generate NSFW image prompts using Ollama.

    Args:
        count: Number of prompts to generate
        style: Style category (lingerie, nude, cosplay_lewd)
        model: Ollama model to use
        character: Optional character name for cosplay
        include_caption: Whether to include TikTok-style caption

    Returns:
        List of NSFW prompts ready for Pony/SDXL
    """

    style_config = NSFW_STYLES.get(style, NSFW_STYLES["lingerie"])
    prompts = []

    for _ in range(count):
        outfit = random.choice(style_config["outfits"])
        pose = random.choice(style_config["poses"])

        # Build base prompt for Pony/SDXL
        if character and style == "cosplay_lewd":
            base = f"score_9, score_8_up, score_7_up, {character}, {outfit}, {pose}"
        else:
            base = f"score_9, score_8_up, score_7_up, 1girl, {outfit}, {pose}"

        # Add quality tags
        base += ", masterpiece, best quality, detailed skin, detailed face"
        base += ", photorealistic, 8k uhd, professional photo"

        # Add lighting
        lighting = random.choice([
            "soft bedroom lighting",
            "golden hour light through window",
            "neon pink and blue lighting",
            "dim mood lighting",
            "ring light selfie lighting",
        ])
        base += f", {lighting}"

        # Generate caption if requested
        if include_caption:
            caption = await generate_nsfw_caption(
                model=model,
                character=character if style == "cosplay_lewd" else None,
            )
            base += f", off-center TikTok-style caption written in Proxima Nova Semibold font white text with black outline reads: {caption}"

        prompts.append(base)

    logger.info("Generated NSFW prompts", count=len(prompts), style=style)
    return prompts


async def generate_single_nsfw_prompt(
    description: str,
    model: str = "dolphin-llama3",
    include_caption: bool = True,
) -> str:
    """
    Generate a single NSFW prompt from a text description.

    Args:
        description: Natural language description of what you want
        model: Ollama model to use
        include_caption: Whether to add a caption

    Returns:
        Formatted prompt for Pony/SDXL
    """

    prompt = f"""You are an expert at writing prompts for AI image generation of adult content.

Convert this description into a detailed image generation prompt for Pony/SDXL:
"{description}"

Requirements:
- Start with quality tags: score_9, score_8_up, score_7_up
- Include detailed outfit/clothing description
- Include pose and expression
- Include lighting and setting
- Be explicit and detailed about body/anatomy
- Use danbooru tag style (comma separated)

Output ONLY the prompt, no explanation.
Prompt:"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.8,
                    }
                }
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get("response", "").strip()

                # Add caption if requested
                if include_caption:
                    caption = await generate_nsfw_caption(model=model)
                    result += f", off-center TikTok-style caption written in Proxima Nova Semibold font white text with black outline reads: {caption}"

                return result
    except Exception as e:
        logger.error("Failed to generate NSFW prompt", error=str(e))

    return ""
