"""Cost calculation service for pipeline steps."""

from typing import List, Optional
from decimal import Decimal
import structlog

logger = structlog.get_logger()


class CostCalculator:
    """Service for calculating pipeline costs based on model pricing."""

    # I2I Model pricing (per image)
    I2I_PRICING = {
        "gpt-image-1.5": {
            "low": Decimal("0.009"),
            "medium": Decimal("0.07"),
            "high": Decimal("0.20"),
        },
        "kling-image": Decimal("0.028"),
        "nano-banana": Decimal("0.039"),
        "nano-banana-pro": Decimal("0.15"),
    }

    # I2V Model pricing - from fal_client.py per-second rates
    # wan: 480p=$0.05/s, 720p=$0.10/s, 1080p=$0.15/s → per 5s
    # wan21/wan22: 480p=$0.04/s, 580p=$0.06/s, 720p=$0.08/s → per 5s
    # wan-pro: 1080p=$0.16/s → ~$0.80/5s
    # veo2: $0.50/s → $2.50/5s
    # veo31-fast: $0.10/s → $0.60/6s (veo uses 6s not 5s)
    # veo31: $0.20/s → $1.20/6s
    # sora-2: $0.10/s → $0.40/4s (sora uses 4s)
    I2V_PRICING = {
        "wan": {"480p": Decimal("0.25"), "720p": Decimal("0.50"), "1080p": Decimal("0.75")},
        "wan21": {"480p": Decimal("0.20"), "720p": Decimal("0.40")},
        "wan22": {"480p": Decimal("0.20"), "720p": Decimal("0.40")},
        "wan-pro": {"1080p": Decimal("0.80")},
        "kling": Decimal("0.35"),
        "kling-standard": Decimal("0.25"),
        "kling-master": Decimal("1.40"),
        "veo2": Decimal("2.50"),  # $0.50/s * 5s
        "veo31-fast": Decimal("0.60"),  # $0.10/s * 6s
        "veo31": Decimal("1.20"),  # $0.20/s * 6s
        "veo31-flf": Decimal("1.20"),  # $0.20/s * 6s
        "veo31-fast-flf": Decimal("0.60"),  # $0.10/s * 6s
        "sora-2": Decimal("0.40"),  # $0.10/s * 4s
        "sora-2-pro": Decimal("2.00"),  # $0.50/s * 4s @ 1080p
    }

    # Base duration for I2V pricing (seconds)
    I2V_BASE_DURATION = 5

    # Prompt enhancement pricing (negligible, using Claude Haiku)
    PROMPT_ENHANCE_PRICE = Decimal("0.001")

    def get_i2i_price(self, model: str, quality: str = "high") -> Decimal:
        """Get price per image for I2I model."""
        pricing = self.I2I_PRICING.get(model)
        if pricing is None:
            logger.warning(f"Unknown I2I model: {model}, using default")
            return Decimal("0.10")

        if isinstance(pricing, dict):
            return pricing.get(quality, pricing.get("high", Decimal("0.10")))
        return pricing

    def get_i2v_price(self, model: str, resolution: str = "1080p", duration_sec: int = 5) -> Decimal:
        """Get price per video for I2V model."""
        pricing = self.I2V_PRICING.get(model)
        if pricing is None:
            logger.warning(f"Unknown I2V model: {model}, using default")
            pricing = Decimal("0.50")

        # Get base price
        if isinstance(pricing, dict):
            base_price = pricing.get(resolution, pricing.get("1080p", Decimal("0.50")))
        else:
            base_price = pricing

        # Scale by duration
        duration_multiplier = Decimal(duration_sec) / Decimal(self.I2V_BASE_DURATION)
        return base_price * duration_multiplier

    def calculate_prompt_enhance_cost(self, config: dict) -> dict:
        """Calculate cost for prompt enhancement step."""
        input_prompts = config.get("input_prompts", [])
        variations_per_prompt = config.get("variations_per_prompt", 5)

        total_prompts = len(input_prompts) * variations_per_prompt
        total_cost = Decimal(total_prompts) * self.PROMPT_ENHANCE_PRICE

        return {
            "step_type": "prompt_enhance",
            "model": "claude-3-haiku",
            "unit_count": total_prompts,
            "unit_price": float(self.PROMPT_ENHANCE_PRICE),
            "total": float(total_cost),
        }

    def calculate_i2i_cost(self, config: dict, num_inputs: int = 1) -> dict:
        """Calculate cost for I2I step."""
        model = config.get("model", "gpt-image-1.5")
        quality = config.get("quality", "high")
        images_per_prompt = config.get("images_per_prompt", 1)

        # Calculate set mode multiplier
        set_mode = config.get("set_mode", {})
        set_multiplier = 1
        if set_mode.get("enabled"):
            variations = set_mode.get("variations", [])
            count_per = set_mode.get("count_per_variation", 1)
            if variations:
                set_multiplier = len(variations) * count_per

        total_images = num_inputs * images_per_prompt * set_multiplier
        unit_price = self.get_i2i_price(model, quality)
        total_cost = Decimal(total_images) * unit_price

        return {
            "step_type": "i2i",
            "model": model,
            "unit_count": total_images,
            "unit_price": float(unit_price),
            "total": float(total_cost),
        }

    def calculate_i2v_cost(self, config: dict, num_inputs: int = 1) -> dict:
        """Calculate cost for I2V step."""
        model = config.get("model", "kling")
        resolution = config.get("resolution", "1080p")
        duration_sec = config.get("duration_sec", 5)
        videos_per_image = config.get("videos_per_image", 1)

        total_videos = num_inputs * videos_per_image
        unit_price = self.get_i2v_price(model, resolution, duration_sec)
        total_cost = Decimal(total_videos) * unit_price

        return {
            "step_type": "i2v",
            "model": model,
            "unit_count": total_videos,
            "unit_price": float(unit_price),
            "total": float(total_cost),
        }

    def estimate_pipeline_cost(self, steps: List[dict]) -> dict:
        """
        Estimate total pipeline cost.

        Args:
            steps: List of step configs with step_type and config

        Returns:
            Cost breakdown with total
        """
        breakdown = []
        running_output_count = 1  # Start with 1 input

        for i, step in enumerate(steps):
            step_type = step.get("step_type")
            config = step.get("config", {})

            if step_type == "prompt_enhance":
                cost_info = self.calculate_prompt_enhance_cost(config)
                # Prompt enhance multiplies outputs
                input_prompts = config.get("input_prompts", [])
                variations = config.get("variations_per_prompt", 5)
                running_output_count = len(input_prompts) * variations if input_prompts else running_output_count * variations

            elif step_type == "i2i":
                cost_info = self.calculate_i2i_cost(config, running_output_count)
                # I2I multiplies by images_per_prompt and set_mode
                images_per = config.get("images_per_prompt", 1)
                set_mode = config.get("set_mode", {})
                set_mult = 1
                if set_mode.get("enabled"):
                    variations = set_mode.get("variations", [])
                    count_per = set_mode.get("count_per_variation", 1)
                    if variations:
                        set_mult = len(variations) * count_per
                running_output_count = running_output_count * images_per * set_mult

            elif step_type == "i2v":
                cost_info = self.calculate_i2v_cost(config, running_output_count)
                # I2V multiplies by videos_per_image
                videos_per = config.get("videos_per_image", 1)
                running_output_count = running_output_count * videos_per

            else:
                logger.warning(f"Unknown step type: {step_type}")
                continue

            cost_info["step_order"] = step.get("step_order", i)
            breakdown.append(cost_info)

        total = sum(item["total"] for item in breakdown)

        return {
            "breakdown": breakdown,
            "total": float(total),
            "currency": "USD",
        }

    def format_cost_tree(self, estimate: dict) -> str:
        """Format cost estimate as tree string for display."""
        lines = ["Pipeline Cost Estimate:"]

        for i, item in enumerate(estimate["breakdown"]):
            is_last = i == len(estimate["breakdown"]) - 1
            prefix = "  └─" if is_last else "  ├─"
            model_str = f" ({item['model']})" if item.get("model") else ""
            lines.append(
                f"{prefix} {item['step_type'].replace('_', ' ').title()}{model_str}: "
                f"{item['unit_count']} × ${item['unit_price']:.3f} = ${item['total']:.2f}"
            )

        lines.append("  " + "─" * 40)
        lines.append(f"  Total: ${estimate['total']:.2f}")

        return "\n".join(lines)


# Singleton instance
cost_calculator = CostCalculator()
