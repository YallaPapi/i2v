"""Cost calculation service for pipeline steps."""

from typing import List
from decimal import Decimal
import structlog

logger = structlog.get_logger()


class CostCalculator:
    """Service for calculating pipeline costs based on model pricing.

    All I2V prices are stored as PER-SECOND rates for accurate duration scaling.
    Prices verified from fal.ai January 2026.
    """

    # I2I Model pricing (per image) - fal.ai January 2026
    I2I_PRICING = {
        "gpt-image-1.5": {
            "low": Decimal("0.009"),
            "medium": Decimal("0.07"),
            "high": Decimal("0.20"),
        },
        "kling-image": Decimal("0.028"),
        "nano-banana": Decimal("0.039"),
        "nano-banana-pro": Decimal("0.15"),
        # FLUX.1
        "flux-general": Decimal("0.025"),
        # FLUX.2 models (Nov 2025)
        "flux-2-dev": Decimal("0.025"),  # ~$0.012/MP, estimated per image
        "flux-2-pro": Decimal("0.05"),   # ~$0.03/MP, estimated per image
        "flux-2-flex": Decimal("0.04"),  # Per image pricing
        "flux-2-max": Decimal("0.08"),   # Per image pricing
        # FLUX.1 Kontext
        "flux-kontext-dev": Decimal("0.025"),
        "flux-kontext-pro": Decimal("0.04"),
    }

    # I2V Model pricing - PER-SECOND rates from fal.ai (January 2026)
    # All values are $/second - multiply by duration to get total cost
    I2V_PRICING_PER_SEC = {
        # Wan models - resolution-based per-second pricing
        "wan": {
            "480p": Decimal("0.05"),
            "720p": Decimal("0.10"),
            "1080p": Decimal("0.15"),
        },
        # Wan 2.2 - slightly cheaper per-second
        "wan22": {
            "480p": Decimal("0.04"),
            "720p": Decimal("0.08"),
        },
        # Wan Pro - premium 1080p only
        "wan-pro": {"1080p": Decimal("0.16")},
        # Kling models - flat per-second rate
        "kling": Decimal("0.07"),  # Kling 2.5 Turbo Pro
        "kling-standard": Decimal("0.05"),  # Kling 2.1 Standard (budget)
        "kling-master": Decimal("0.28"),  # Kling 2.1 Master (premium)
        # Veo models - per-second (audio doubles the price)
        "veo2": Decimal("0.50"),  # Veo 2 (720p only)
        "veo31-fast": Decimal("0.10"),  # Veo 3.1 Fast (no audio)
        "veo31": Decimal("0.20"),  # Veo 3.1 (no audio)
        "veo31-flf": Decimal("0.20"),  # Veo 3.1 First-Last Frame
        "veo31-fast-flf": Decimal("0.10"),  # Veo 3.1 Fast First-Last Frame
        # Sora models - per-second
        "sora-2": Decimal("0.10"),  # Sora 2 (720p only)
        "sora-2-pro": Decimal("0.50"),  # Sora 2 Pro (1080p rate, 720p is $0.30/s)
    }

    # Wan 2.1 uses FLAT per-video pricing (not per-second)
    WAN21_FLAT_PRICING = {
        "480p": Decimal("0.20"),
        "720p": Decimal("0.40"),
    }

    # Face swap pricing (per swap)
    FACE_SWAP_PRICING = {
        "easel-advanced": Decimal("0.05"),
    }

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

    def get_face_swap_price(self, model: str = "easel-advanced") -> Decimal:
        """Get price per face swap."""
        return self.FACE_SWAP_PRICING.get(model, Decimal("0.05"))

    def get_i2v_price(
        self, model: str, resolution: str = "1080p", duration_sec: int = 5
    ) -> Decimal:
        """Get price per video for I2V model.

        Uses per-second pricing and multiplies by actual duration.
        Wan 2.1 is special - it uses flat per-video pricing.
        """
        # Special case: Wan 2.1 uses flat per-video pricing
        if model == "wan21":
            flat_price = self.WAN21_FLAT_PRICING.get(resolution, Decimal("0.40"))
            return flat_price

        # Get per-second rate
        pricing = self.I2V_PRICING_PER_SEC.get(model)
        if pricing is None:
            logger.warning(f"Unknown I2V model: {model}, using default $0.10/s")
            pricing = Decimal("0.10")

        # Get rate (may be resolution-dependent)
        if isinstance(pricing, dict):
            per_sec_rate = pricing.get(resolution, pricing.get("1080p", Decimal("0.10")))
        else:
            per_sec_rate = pricing

        # Calculate total: rate × duration
        return per_sec_rate * Decimal(duration_sec)

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

    def calculate_face_swap_cost(self, config: dict, num_inputs: int = 1) -> dict:
        """Calculate cost for face swap step."""
        model = config.get("model", "easel-advanced")

        total_swaps = num_inputs
        unit_price = self.get_face_swap_price(model)
        total_cost = Decimal(total_swaps) * unit_price

        return {
            "step_type": "face_swap",
            "model": model,
            "unit_count": total_swaps,
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
                running_output_count = (
                    len(input_prompts) * variations
                    if input_prompts
                    else running_output_count * variations
                )

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

            elif step_type == "face_swap":
                cost_info = self.calculate_face_swap_cost(config, running_output_count)
                # Face swap produces 1 output per input (1:1)

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
