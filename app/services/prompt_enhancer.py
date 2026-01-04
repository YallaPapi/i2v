"""Prompt enhancement service using Claude API."""

import json
import hashlib
from typing import List, Literal, Optional
import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()

# Simple in-memory cache for prompt enhancement results
_prompt_cache: dict[str, List[str]] = {}

# Category definitions for enhancement
I2V_CATEGORIES = {
    "camera_movement": "Add camera motion (slow pan, gentle zoom, tracking shot)",
    "motion_intensity": "Describe motion speed and energy (slow, smooth, energetic, subtle)",
    "facial_expression": "Detail expression changes and transitions",
    "body_language": "Describe gestures, posture, and body movement",
    "environment_interaction": "Include interaction with surroundings if relevant",
}

I2I_CATEGORIES = {
    "lighting": "Specify lighting conditions (natural, studio, dramatic, golden hour)",
    "outfit": "Describe clothing and attire variations",
    "pose": "Detail body positioning and stance",
    "background": "Describe background treatment (blur, change, keep same)",
    "style": "Specify visual style (photorealistic, artistic, vintage, cinematic)",
}


class PromptEnhancer:
    """Service for enhancing prompts using Claude API."""

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.api_key = settings.anthropic_api_key
        if not self.api_key:
            logger.warning("No Anthropic API key configured - prompt enhancement will use fallback")

    def _get_cache_key(
        self,
        prompt: str,
        target: str,
        count: int,
        style: str,
        theme_focus: Optional[str],
        mode: str = "quick_improve",
        categories: Optional[List[str]] = None
    ) -> str:
        """Generate cache key for prompt enhancement request."""
        cat_str = ",".join(sorted(categories)) if categories else ""
        key_data = f"{prompt}:{target}:{count}:{style}:{theme_focus or ''}:{mode}:{cat_str}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_system_prompt(
        self,
        target: Literal["i2i", "i2v"],
        count: int,
        style: str,
        theme_focus: Optional[str],
        mode: str = "quick_improve",
        categories: Optional[List[str]] = None
    ) -> str:
        """Generate system prompt for Claude."""

        if target == "i2v":
            # Motion-focused prompt for video
            if mode == "quick_improve":
                system = f"""You are a motion description expert for image-to-video AI.
Enhance the user's prompt to be more descriptive. Generate {count} variations.

CRITICAL RULES:
- Focus ONLY on describing the motion/action in more detail
- Keep the exact same subject from the input - do not add new characters or change who is shown
- Add natural movement details: speed, arc, gesture nuances, timing
- Keep prompts concise: 1-2 sentences maximum
- Do NOT add: locations, settings, camera types, platforms (no "TikTok", "phone camera", "tripod")
- Do NOT add: room descriptions, background details, lighting unless motion-related
- Do NOT assume context that wasn't specified

GOOD example:
Input: "the woman smiles and waves"
Output: "She breaks into a warm smile and raises her hand in a slow, friendly wave, her fingers gently spreading"

BAD example (too much context):
Input: "the woman smiles and waves"
Output: "TikTok-style video of the woman in her room with a phone camera..." <- WRONG, too much added context

Output format: Return ONLY a valid JSON array of {count} strings, no other text.
Example: ["prompt 1", "prompt 2", "prompt 3"]"""
            else:  # category_based
                cat_instructions = []
                available_cats = I2V_CATEGORIES
                if categories:
                    for cat in categories:
                        if cat in available_cats:
                            cat_instructions.append(f"- {available_cats[cat]}")

                cat_text = "\n".join(cat_instructions) if cat_instructions else "- Add motion details"

                system = f"""You are a motion description expert for image-to-video AI.
Enhance the user's prompt with specific focus areas. Generate {count} variations.

FOCUS AREAS (include these aspects):
{cat_text}

RULES:
- Keep the exact same subject - don't add new people or change who is shown
- Keep prompts concise: 1-2 sentences
- Only add details related to the selected focus areas
- Do NOT add locations, settings, or context that wasn't in the original

Output format: Return ONLY a valid JSON array of {count} strings, no other text."""

        else:  # i2i
            if mode == "quick_improve":
                system = f"""You are a visual description expert for image-to-image AI.
Enhance the user's prompt to be more descriptive. Generate {count} variations.

RULES:
- Add visual details: composition, mood, artistic touches
- Keep the same subject and core concept
- Style preference: {style}
{"- Focus on: " + theme_focus if theme_focus else ""}
- Keep prompts concise: 1-2 sentences

Output format: Return ONLY a valid JSON array of {count} strings, no other text."""
            else:  # category_based
                cat_instructions = []
                available_cats = I2I_CATEGORIES
                if categories:
                    for cat in categories:
                        if cat in available_cats:
                            cat_instructions.append(f"- {available_cats[cat]}")

                cat_text = "\n".join(cat_instructions) if cat_instructions else "- Add visual details"

                system = f"""You are a visual description expert for image-to-image AI.
Enhance the user's prompt with specific focus areas. Generate {count} variations.

FOCUS AREAS:
{cat_text}

RULES:
- Keep the same subject and core concept
- Only add details related to the selected focus areas
- Keep prompts concise: 1-2 sentences

Output format: Return ONLY a valid JSON array of {count} strings, no other text."""

        return system

    async def enhance_prompt(
        self,
        simple_prompt: str,
        target: Literal["i2i", "i2v"] = "i2i",
        count: int = 3,
        style: str = "photorealistic",
        theme_focus: Optional[str] = None,
        mode: str = "quick_improve",
        categories: Optional[List[str]] = None
    ) -> List[str]:
        """
        Enhance a simple prompt into multiple detailed variations.

        Args:
            simple_prompt: The basic prompt to enhance
            target: Target generation type ("i2i" or "i2v")
            count: Number of variations to generate
            style: Style preference (e.g., "photorealistic", "artistic")
            theme_focus: Optional focus area (e.g., "outfits", "poses")
            mode: Enhancement mode ("quick_improve" or "category_based")
            categories: List of categories to focus on

        Returns:
            List of enhanced prompt variations
        """
        # Check cache
        cache_key = self._get_cache_key(simple_prompt, target, count, style, theme_focus, mode, categories)
        if cache_key in _prompt_cache:
            logger.info("Prompt cache hit", cache_key=cache_key[:8])
            return _prompt_cache[cache_key]

        # If no API key, return fallback variations
        if not self.api_key:
            logger.warning("Using fallback prompt enhancement (no API key)")
            return self._fallback_enhance(simple_prompt, target, count, style, theme_focus, mode, categories)

        try:
            system_prompt = self._get_system_prompt(target, count, style, theme_focus, mode, categories)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.ANTHROPIC_API_URL,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-Key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1024,  # Reduced for concise outputs
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": f"Enhance this prompt: {simple_prompt}"}
                        ],
                    },
                )

                if response.status_code != 200:
                    logger.error("Claude API error", status=response.status_code, body=response.text)
                    return self._fallback_enhance(simple_prompt, target, count, style, theme_focus, mode, categories)

                data = response.json()
                content = data["content"][0]["text"]

                # Parse JSON response
                enhanced = json.loads(content)
                if not isinstance(enhanced, list):
                    raise ValueError("Response is not a list")

                # Cache result
                _prompt_cache[cache_key] = enhanced
                logger.info("Prompt enhanced successfully", count=len(enhanced))
                return enhanced

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON", error=str(e))
            return self._fallback_enhance(simple_prompt, target, count, style, theme_focus, mode, categories)
        except Exception as e:
            logger.error("Prompt enhancement failed", error=str(e))
            return self._fallback_enhance(simple_prompt, target, count, style, theme_focus, mode, categories)

    def _fallback_enhance(
        self,
        prompt: str,
        target: Literal["i2i", "i2v"],
        count: int,
        style: str,
        theme_focus: Optional[str],
        mode: str = "quick_improve",
        categories: Optional[List[str]] = None
    ) -> List[str]:
        """Generate fallback enhanced prompts without API."""
        variations = []

        # Motion-focused templates for i2v (no extra context)
        if target == "i2v":
            templates = [
                f"{prompt}, with slow deliberate movement",
                f"{prompt}, the motion smooth and natural",
                f"{prompt}, moving gently and gracefully",
                f"{prompt}, with subtle fluid motion",
                f"{prompt}, the action slow and relaxed",
            ]

            # Add category-specific enhancements
            if categories:
                if "camera_movement" in categories:
                    templates = [f"{prompt}, slow camera pan following the motion"] + templates
                if "motion_intensity" in categories:
                    templates = [f"{prompt}, with gentle unhurried movement"] + templates
                if "facial_expression" in categories:
                    templates = [f"{prompt}, expression transitioning naturally"] + templates
                if "body_language" in categories:
                    templates = [f"{prompt}, gestures flowing and relaxed"] + templates
        else:  # i2i
            templates = [
                f"{prompt}, {style} style, high detail",
                f"{prompt}, {style}, natural lighting",
                f"{prompt}, {style}, dramatic composition",
                f"{prompt}, {style}, warm tones",
                f"{prompt}, {style}, sharp focus",
            ]

            if categories:
                if "lighting" in categories:
                    templates = [f"{prompt}, studio lighting, soft shadows"] + templates
                if "outfit" in categories:
                    templates = [f"{prompt}, stylish attire"] + templates
                if "pose" in categories:
                    templates = [f"{prompt}, confident stance"] + templates
                if "background" in categories:
                    templates = [f"{prompt}, softly blurred background"] + templates
                if "style" in categories:
                    templates = [f"{prompt}, cinematic {style} look"] + templates

        # Add theme focus variations if specified
        if theme_focus:
            focus_templates = {
                "outfits": [f"{prompt}, casual outfit", f"{prompt}, formal attire"],
                "poses": [f"{prompt}, standing pose", f"{prompt}, seated position"],
                "expressions": [f"{prompt}, smiling", f"{prompt}, serious look"],
                "lighting": [f"{prompt}, studio lighting", f"{prompt}, natural light"],
            }
            if theme_focus in focus_templates:
                templates = focus_templates[theme_focus] + templates

        return templates[:count]

    async def enhance_bulk(
        self,
        prompts: List[str],
        target: Literal["i2i", "i2v"] = "i2i",
        count: int = 3,
        style: str = "photorealistic",
        theme_focus: Optional[str] = None,
        mode: str = "quick_improve",
        categories: Optional[List[str]] = None
    ) -> List[List[str]]:
        """
        Enhance multiple prompts.

        Args:
            prompts: List of simple prompts to enhance
            target: Target generation type
            count: Number of variations per prompt
            style: Style preference
            theme_focus: Optional focus area
            mode: Enhancement mode
            categories: Categories to focus on

        Returns:
            List of enhanced prompt lists (one per input prompt)
        """
        results = []
        for prompt in prompts:
            enhanced = await self.enhance_prompt(prompt, target, count, style, theme_focus, mode, categories)
            results.append(enhanced)
        return results


# Singleton instance
prompt_enhancer = PromptEnhancer()
