"""Seed initial templates for MVP."""

import structlog
from sqlalchemy.orm import Session

from app.models import Template

logger = structlog.get_logger()

# MVP Template definitions based on PRD
MVP_TEMPLATES = [
    # Social SFW Templates
    {
        "id": "cosplay-thirst-trap",
        "name": "Cosplay Thirst Trap",
        "description": "Cosplay-inspired photos with thirst trap energy. Perfect for IG/TikTok.",
        "category": "social_sfw",
        "output_type": "image",
        "base_prompt": "professional photo of woman in {costume} cosplay, {pose}, {setting}, sexy but tasteful, instagram aesthetic, high fashion photography, {lighting}",
        "negative_prompt": "ugly, deformed, blurry, low quality, amateur, watermark",
        "variables": {
            "costume": ["anime schoolgirl", "catgirl maid", "bunny girl", "nurse", "police officer", "cheerleader", "princess", "witch", "elf", "pirate"],
            "pose": ["standing confidently", "sitting elegantly", "leaning against wall", "looking over shoulder", "hands on hips", "twirling", "stretching"],
            "setting": ["bedroom mirror selfie", "studio backdrop", "outdoor garden", "urban street", "cafe interior", "beach sunset"],
            "lighting": ["golden hour", "soft studio lighting", "neon lights", "natural daylight", "dramatic shadows"]
        },
        "caption_templates": [
            "POV: your anime waifu came to life",
            "they said cosplay wasn't a personality trait...",
            "main character energy only",
            "the costume stays ON during {activity}",
            "when the {costume} fits just right",
        ],
        "recommended_model": "flux-2-pro",
        "video_model": "kling",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": False,
        "is_featured": True,
        "tags": ["cosplay", "thirst trap", "instagram", "tiktok", "anime"],
    },
    {
        "id": "gym-fitness",
        "name": "Gym & Fitness",
        "description": "Workout and gym aesthetic content. Show off gains.",
        "category": "social_sfw",
        "output_type": "image",
        "base_prompt": "fitness model in {outfit}, {pose}, {setting}, athletic body, motivated expression, {lighting}, professional fitness photography",
        "negative_prompt": "ugly, deformed, blurry, low quality, watermark",
        "variables": {
            "outfit": ["sports bra and leggings", "crop top and shorts", "gym tank", "yoga outfit", "athleisure set"],
            "pose": ["lifting weights", "stretching", "flexing", "mid-workout", "taking mirror selfie", "holding protein shake"],
            "setting": ["modern gym", "home gym", "outdoor workout area", "yoga studio", "locker room mirror"],
            "lighting": ["bright gym lights", "morning sunlight", "dramatic spotlight", "natural window light"]
        },
        "caption_templates": [
            "no rest days, only best days",
            "sweat now, shine later",
            "building my dream body one rep at a time",
            "gym crush loading...",
            "these gains aren't gonna make themselves",
        ],
        "recommended_model": "gpt-image-1.5",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": False,
        "is_featured": True,
        "tags": ["gym", "fitness", "workout", "gains", "motivation"],
    },
    {
        "id": "grwm-selfie",
        "name": "Get Ready With Me",
        "description": "GRWM style selfies and mirror shots. Casual, relatable content.",
        "category": "social_sfw",
        "output_type": "image",
        "base_prompt": "casual selfie of woman {activity}, {outfit}, {setting}, {makeup}, authentic instagram aesthetic, relatable vibe",
        "negative_prompt": "ugly, deformed, blurry, low quality, professional studio",
        "variables": {
            "activity": ["doing makeup", "fixing hair", "choosing outfit", "applying lipstick", "taking selfie"],
            "outfit": ["oversized hoodie", "cute pajamas", "casual dress", "jeans and crop top", "robe"],
            "setting": ["bathroom mirror", "bedroom vanity", "closet", "messy room", "ring light setup"],
            "makeup": ["natural makeup", "glam makeup", "no makeup", "half-done makeup", "bold lips"]
        },
        "caption_templates": [
            "GRWM to do absolutely nothing",
            "getting ready takes longer than the actual event",
            "is it a good hair day or did I just get lucky?",
            "that 'running late but still cute' energy",
            "the before vs after transformation hits different",
        ],
        "recommended_model": "gpt-image-1.5",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": False,
        "is_featured": False,
        "tags": ["grwm", "selfie", "relatable", "casual", "makeup"],
    },
    {
        "id": "pov-scenarios",
        "name": "POV Scenarios",
        "description": "Point-of-view style content for engagement. Great for TikTok.",
        "category": "social_sfw",
        "output_type": "image",
        "base_prompt": "POV shot, woman {action}, {expression}, looking directly at camera, {setting}, intimate framing, {lighting}",
        "negative_prompt": "ugly, deformed, blurry, side profile, looking away",
        "variables": {
            "action": ["reaching toward camera", "whispering secret", "waking you up", "offering hand", "playfully teasing"],
            "expression": ["playful smile", "seductive glance", "surprised", "caring", "mischievous"],
            "setting": ["cozy bedroom", "kitchen morning", "living room couch", "car passenger seat", "picnic blanket"],
            "lighting": ["soft morning light", "warm lamp light", "golden hour", "cozy ambient"]
        },
        "caption_templates": [
            "POV: you're the main character in my story",
            "POV: your crush finally noticed you",
            "POV: I'm your dream girl and I'm real",
            "POV: waking up to this every morning",
            "POV: she's actually into you",
        ],
        "recommended_model": "flux-2-pro",
        "video_model": "kling",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": False,
        "is_featured": True,
        "tags": ["pov", "tiktok", "viral", "engagement", "interactive"],
    },

    # NSFW Templates
    {
        "id": "lingerie-photoshoot",
        "name": "Lingerie Photoshoot",
        "description": "Elegant lingerie photos. Tasteful but sexy.",
        "category": "nsfw",
        "output_type": "image",
        "base_prompt": "professional boudoir photo of woman in {lingerie}, {pose}, {setting}, elegant and sensual, soft focus, {lighting}",
        "negative_prompt": "ugly, deformed, cheap looking, amateur, harsh lighting",
        "variables": {
            "lingerie": ["black lace set", "red satin", "white bridal", "sheer bodysuit", "silk chemise", "strappy set"],
            "pose": ["lying on bed", "standing by window", "sitting on chair", "kneeling", "over the shoulder look"],
            "setting": ["luxury bedroom", "hotel suite", "silk sheets", "velvet couch", "by fireplace"],
            "lighting": ["candlelight", "soft window light", "warm tones", "dramatic shadows", "fairy lights"]
        },
        "caption_templates": [
            "the things I'd let you do...",
            "subscribe to see what happens next",
            "your view for the evening",
            "dressed up just for you",
            "private show loading...",
        ],
        "recommended_model": "pony-realistic",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": True,
        "is_featured": True,
        "tags": ["lingerie", "boudoir", "sexy", "onlyfans", "nsfw"],
    },
    {
        "id": "implied-nude-tease",
        "name": "Implied Nude Tease",
        "description": "Suggestive but not explicit. Strategic covering.",
        "category": "nsfw",
        "output_type": "image",
        "base_prompt": "artistic implied nude of woman, {covering}, {pose}, {setting}, tasteful and teasing, {lighting}, professional photography",
        "negative_prompt": "explicit, vulgar, cheap, amateur, deformed",
        "variables": {
            "covering": ["sheet draped", "arm across chest", "back turned", "silhouette only", "hands covering", "towel barely held"],
            "pose": ["sitting on bed edge", "standing by window", "lying face down", "shower steam", "behind frosted glass"],
            "setting": ["minimalist bedroom", "spa bathroom", "natural hot spring", "artist studio", "beach at dawn"],
            "lighting": ["backlit silhouette", "soft diffused", "golden hour glow", "steam and shadow", "candlelit"]
        },
        "caption_templates": [
            "imagination is the best filter",
            "less is more (but you can see more on OF)",
            "the art of the tease",
            "what you can't see is the best part",
            "leaving something to the imagination... for now",
        ],
        "recommended_model": "pony-realistic",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": True,
        "is_featured": True,
        "tags": ["tease", "implied", "artistic", "suggestive", "onlyfans"],
    },

    # Brainrot/Viral Templates
    {
        "id": "brainrot-viral",
        "name": "Brainrot Viral",
        "description": "Absurdist, chaotic meme energy. Pure engagement bait.",
        "category": "brainrot",
        "output_type": "image",
        "base_prompt": "chaotic photo of woman {action}, {expression}, {prop}, absurd situation, meme energy, {setting}",
        "negative_prompt": "boring, normal, professional, serious",
        "variables": {
            "action": ["t-posing", "screaming at sky", "eating something weird", "dramatically falling", "staring menacingly"],
            "expression": ["unhinged smile", "dead inside", "dramatically crying", "evil grin", "confused"],
            "prop": ["holding fish", "with random cat", "surrounded by energy drinks", "wearing traffic cone", "multiple phones"],
            "setting": ["walmart at 3am", "empty parking lot", "mcdonalds", "random field", "bathroom floor"]
        },
        "caption_templates": [
            "me when the {random} hits different at 3am",
            "real ones understand this energy",
            "this is my last brain cell",
            "corporate wants you to find the difference (it's me, I'm the difference)",
            "POV: you just discovered my page and you're questioning your life choices",
        ],
        "recommended_model": "flux-2-dev",
        "aspect_ratio": "9:16",
        "tier_required": "starter",
        "is_nsfw": False,
        "is_featured": False,
        "tags": ["brainrot", "meme", "viral", "chaotic", "absurd"],
    },

    # Carousel Templates
    {
        "id": "outfit-carousel",
        "name": "Outfit Showcase Carousel",
        "description": "Multi-slide outfit reveal. Perfect for fashion content.",
        "category": "carousel",
        "output_type": "carousel",
        "base_prompt": "fashion photo of woman wearing {outfit}, {pose}, clean background, professional fashion photography",
        "variables": {
            "outfit": ["casual streetwear", "elegant dress", "athleisure", "business casual", "night out look"],
            "pose": ["full body front", "walking pose", "sitting casual", "over shoulder", "detail shot"]
        },
        "caption_templates": [
            "swipe to see my favorite looks this week",
            "which outfit is your vibe?",
            "1, 2, or 3? vote below",
            "outfit check - rate 1-10",
            "new fits just dropped",
        ],
        "slides": [
            {"scene": "full body front shot", "prompt_suffix": "standing straight, front view"},
            {"scene": "side angle", "prompt_suffix": "elegant side pose"},
            {"scene": "detail/accessory shot", "prompt_suffix": "close up on outfit details"},
            {"scene": "candid walking", "prompt_suffix": "natural walking pose"},
            {"scene": "sitting casual", "prompt_suffix": "relaxed sitting pose"}
        ],
        "recommended_model": "gpt-image-1.5",
        "aspect_ratio": "4:5",
        "tier_required": "pro",
        "is_nsfw": False,
        "is_featured": True,
        "tags": ["carousel", "fashion", "outfit", "instagram", "style"],
    },
    {
        "id": "day-in-life-carousel",
        "name": "Day in My Life Carousel",
        "description": "Story-style carousel showing daily activities.",
        "category": "carousel",
        "output_type": "carousel",
        "base_prompt": "lifestyle photo of woman {activity}, {setting}, authentic casual vibe, instagram aesthetic",
        "variables": {
            "activity": ["morning routine", "coffee run", "workout", "work from home", "evening wind down"],
            "setting": ["cozy bedroom", "trendy cafe", "modern gym", "home office", "living room"]
        },
        "caption_templates": [
            "a day in my life",
            "productive day check",
            "this is your sign to live your best life",
            "romanticizing my daily routine",
            "soft life loading...",
        ],
        "slides": [
            {"scene": "morning wake up", "prompt_suffix": "stretching in bed, morning light"},
            {"scene": "morning routine", "prompt_suffix": "skincare or coffee moment"},
            {"scene": "midday activity", "prompt_suffix": "productive work or workout"},
            {"scene": "afternoon break", "prompt_suffix": "relaxing with drink or snack"},
            {"scene": "evening vibes", "prompt_suffix": "cozy evening atmosphere"}
        ],
        "recommended_model": "gpt-image-1.5",
        "aspect_ratio": "4:5",
        "tier_required": "pro",
        "is_nsfw": False,
        "is_featured": False,
        "tags": ["carousel", "lifestyle", "day in life", "aesthetic", "routine"],
    },
]


def seed_templates(db: Session, force: bool = False) -> int:
    """
    Seed MVP templates into database.

    Args:
        db: Database session
        force: If True, overwrite existing templates

    Returns:
        Number of templates created/updated
    """
    count = 0

    for template_data in MVP_TEMPLATES:
        existing = db.query(Template).filter(Template.id == template_data["id"]).first()

        if existing and not force:
            logger.debug("Template already exists, skipping", template_id=template_data["id"])
            continue

        if existing:
            # Update existing
            template = existing
        else:
            # Create new
            template = Template(id=template_data["id"])
            db.add(template)

        # Set all fields
        template.name = template_data["name"]
        template.description = template_data.get("description")
        template.category = template_data.get("category", "social_sfw")
        template.output_type = template_data.get("output_type", "image")
        template.base_prompt = template_data["base_prompt"]
        template.negative_prompt = template_data.get("negative_prompt")
        template.recommended_model = template_data.get("recommended_model")
        template.video_model = template_data.get("video_model")
        template.aspect_ratio = template_data.get("aspect_ratio", "9:16")
        template.duration_sec = template_data.get("duration_sec")
        template.quality = template_data.get("quality", "high")
        template.tier_required = template_data.get("tier_required", "starter")
        template.is_nsfw = 1 if template_data.get("is_nsfw") else 0
        template.is_active = 1
        template.is_featured = 1 if template_data.get("is_featured") else 0

        if template_data.get("variables"):
            template.set_variables(template_data["variables"])
        if template_data.get("caption_templates"):
            template.set_caption_templates(template_data["caption_templates"])
        if template_data.get("slides"):
            template.set_slides(template_data["slides"])
        if template_data.get("tags"):
            template.set_tags(template_data["tags"])

        count += 1
        logger.info("Template seeded", template_id=template.id, name=template.name)

    db.commit()
    logger.info("Template seeding complete", count=count)
    return count


def get_template_count(db: Session) -> int:
    """Get count of active templates."""
    return db.query(Template).filter(Template.is_active == 1).count()
