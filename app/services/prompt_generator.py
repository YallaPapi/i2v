"""
Prompt Generator Service

Generates i2i prompts with on-screen captions for Instagram/TikTok style photos.
Extracted from generate_prompts.py for API integration.
"""

import random
import anthropic
import structlog
from typing import Literal

logger = structlog.get_logger()

MODEL = "claude-sonnet-4-5-20250929"

# Cosplay caption categories
COSPLAY_CAPTION_CATEGORIES = {
    "fake_innocence": """## On-Screen Caption Instructions

FAKE INNOCENCE style: innocent claim + reveal it's actually thirsty/sexual.

The reveal must be FLIRTY and SUGGESTIVE - about wanting him, attraction, hooking up, physical desire. NOT about friendship or platonic feelings.

Examples (for format only, create NEW ones):
- "we're just friends" also us at 2am:
- "i'm not that type of girl" also me after he whispers in my ear:
- "let's just cuddle" me 5 minutes later:

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the thirsty context. Examples:
- Mikasa: "i'm just here to protect humanity" also me wanting him to wreck me:
- Power: "i don't catch feelings for humans" also me after one headpat:
- Yor: "i'm just a regular housewife" also my plans for him tonight:

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Keep it spicy.""",

    "pov_situation": """## On-Screen Caption Instructions

POV style: drop the viewer into a specific thirsty/flirty moment using "pov:" or "when..."

The situation must be SUGGESTIVE - about tension, attraction, wanting him, almost hooking up. NOT wholesome or platonic.

Examples (for format only, create NEW ones):
- pov: he said we're just watching a movie
- when he pulls you closer and says "come here"
- pov: you're trying to be good but he keeps looking at you like that

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the thirsty context. Examples:
- Mikasa: "pov: he asked me to protect him and now i can't stop thinking about it"
- Power: "when he gives you a headpat and ur devil instincts kick in"
- Yor: "pov: he doesn't know about ur secret job but wants to take u home anyway"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make the viewer feel the tension.""",

    "fake_study": """## On-Screen Caption Instructions

FAKE STUDY style: pose as fake research/statistics/rules that are actually thirsty/sexual.

Format: "a new study found that...", "rule number 1:", "scientists discovered...", "research shows..."

Examples (for format only, create NEW ones):
- a new study found that sitting on his face 3x a week reduces stress by 110%
- rule number 1 of dating me: morning cuddles are mandatory and clothing is optional
- scientists discovered girls who get their back blown out sleep 47% better

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the fake study. Examples:
- Mikasa: "a new study found that girls who can fight titans also fight for his attention harder"
- Power: "research shows devil girls give 200% more chaotic energy in bed"
- Zero Two: "scientists discovered darlings who ride with you once never want anyone else"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make it sound official but obviously thirsty.""",

    "shock_humor": """## On-Screen Caption Instructions

SHOCK HUMOR style: one-liner punchlines that are overtly sexual/suggestive but funny.

Short, punchy, catches you off guard. Mix wholesome framing with explicit implications.

Examples (for format only, create NEW ones):
- i'm so nice i pretend to gag on the small ones too
- just the tip never hurt a friendship
- i hate small talk just ask me if i want round 3

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the shock humor. Examples:
- Mikasa: "i'd wrap more than just this scarf around you"
- Power: "they call me a fiend but wait til you see what this mouth does"
- Marin: "i spend hours on my cosplay but i'd spend longer on you"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make it funny and filthy.""",

    "female_desire": """## On-Screen Caption Instructions

FEMALE DESIRE style: "girl math", "my toxic trait", centering her horniness and control.

Flip the dynamic - she's the one dictating terms, being feral, wanting him.

Examples (for format only, create NEW ones):
- girl math is not wanting a relationship + planning our wedding after one compliment
- my toxic trait is thinking one good cuddle will fix my abandonment issues
- i think my biggest turn on is knowing i turned you on

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the female desire context. Examples:
- Mikasa: "my toxic trait is being willing to destroy everything for him and thinking that's romantic"
- Power: "girl math is being a literal devil but still wanting him to text back"
- Yor: "my toxic trait is having a secret double life but getting jealous when he talks to other girls"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make her the one in control.""",

    "kink_subculture": """## On-Screen Caption Instructions

KINK SUBCULTURE style: niche internet slang, gooning references, meta-horny behavior.

Casual, lowercase, treats niche kink stuff as normal daily activity. Very online.

Examples (for format only, create NEW ones):
- why do people get mad when you goon to them i'd feel chosen honestly
- me and who edging each other until we forget our own names
- the way i'd let him ruin my life respectfully

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the kink context. Examples:
- Mikasa: "the way i'd let him use me like odm gear"
- Power: "gooning to devils is normal actually we're just misunderstood"
- Zero Two: "the way darling and i would edge for 100 episodes straight"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make it very online and unhinged.""",

    "mock_qa": """## On-Screen Caption Instructions

MOCK Q&A style: fake genuine questions to men that expose sexual curiosity.

Format: "genuine question:", "men please be honest:", "boys help me understand:"

Examples (for format only, create NEW ones):
- genuine question: how do you walk around with that thing all day and act normal
- men please be honest: do you actually like when we're on top or are you just being polite
- boys help me understand: why does it twitch like that

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the question. Examples:
- Mikasa: "genuine question: do guys actually find girls who could end them attractive"
- Power: "men be honest: would you date a devil if she was hot enough"
- Marin: "genuine question: do guys like when we dress up for them or is that just me being delusional"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make it sound innocent but obviously thirsty.""",

    "comment_bait": """## On-Screen Caption Instructions

COMMENT BAIT style: direct prompts to get engagement in comments about thirsty topics.

Format: "be honest in the comments:", "boys let's talk about:", "girls help me out:"

Examples (for format only, create NEW ones):
- be honest in the comments: what's the biggest L you took in the bedroom
- boys let's talk about: do you even know what you're doing down there or are you freestyling
- girls help me out: is it normal to want round 4 or am i broken

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the comment bait. Examples:
- Mikasa: "be honest: would you let a girl who fights titans boss you around"
- Power: "boys let's talk about: would you wife a devil yes or yes"
- Yor: "be honest in the comments: secret agent wives or regular wives"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make people want to comment.""",

    "chaotic_relatable": """## On-Screen Caption Instructions

CHAOTIC RELATABLE style: sexual but framed as chaotic daily life. "me when..." overshares.

Pair normal behavior with unhinged sexual overshare.

Examples (for format only, create NEW ones):
- me preparing to get on top for a total of 34 seconds
- when he likes lasting for ages but ur legs already gave out after 5 min
- me changing my sheets at 2am for absolutely no reason haha why would i do that

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the chaotic relatable context. Examples:
- Mikasa: "me using all my titan training stamina and still tapping out after round 2"
- Power: "when ur a literal devil but still get nervous when he takes his shirt off"
- Marin: "me spending 6 hours on cosplay makeup just for him to take it off in 6 minutes"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Make it chaotic and relatable.""",

    "visual_punchline": """## On-Screen Caption Instructions

VISUAL PUNCHLINE style: setup only, the video/image carries the punchline. Ends with colon.

The caption sets up expectations, the visual delivers the thirsty punchline.

Examples (for format only, create NEW ones):
- when your selfies aren't hitting so you have to pull out the forbidden pose:
- the face i make when he says he's on his way:
- how i look at him when he doesn't know i'm planning our entire future:

CRITICAL: If cosplaying, the caption MUST reference that character's powers, abilities, storyline, or personality IN the setup. Examples:
- Mikasa: "how i look at him after he said he'd let me protect him:"
- Power: "when he called me a good devil:"
- Yor: "the face i make when he says he likes dangerous women:"

The caption should only make sense for THAT character. Generic captions are not allowed for cosplay prompts.

All lowercase, no periods. Setup only, end with colon."""
}

# Cottagecore caption categories
COTTAGECORE_CAPTION_CATEGORIES = {
    "fake_innocence": """## On-Screen Caption Instructions

FAKE INNOCENCE style: innocent claim + reveal it's actually thirsty/sexual.

The reveal must be FLIRTY and SUGGESTIVE - about wanting him, attraction, hooking up, physical desire. NOT about friendship or platonic feelings.

Examples (for format only, create NEW ones):
- "we're just friends" also us at 2am:
- "i'm not that type of girl" also me after he whispers in my ear:
- "let's just cuddle" me 5 minutes later:

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the thirsty context. Examples:
- Gardening: "i'm just tending my garden" also me wanting him to plow my field:
- Baking: "i just like making bread" also me wanting him to put a bun in my oven:
- Foraging: "i'm just picking wildflowers" also me when he picks me up:

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Keep it spicy.""",

    "pov_situation": """## On-Screen Caption Instructions

POV style: drop the viewer into a specific thirsty/flirty moment using "pov:" or "when..."

The situation must be SUGGESTIVE - about tension, attraction, wanting him, almost hooking up. NOT wholesome or platonic.

Examples (for format only, create NEW ones):
- pov: he said we're just watching a movie
- when he pulls you closer and says "come here"
- pov: you're trying to be good but he keeps looking at you like that

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the thirsty context. Examples:
- Baking: "pov: he's teaching you to knead dough and his hands are on yours"
- Gardening: "when he offers to help in the garden and takes his shirt off"
- Foraging: "pov: you went mushroom hunting but now he's got you pinned against a tree"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make the viewer feel the tension.""",

    "fake_study": """## On-Screen Caption Instructions

FAKE STUDY style: pose as fake research/statistics/rules that are actually thirsty/sexual.

Format: "a new study found that...", "rule number 1:", "scientists discovered...", "research shows..."

Examples (for format only, create NEW ones):
- a new study found that sitting on his face 3x a week reduces stress by 110%
- rule number 1 of dating me: morning cuddles are mandatory and clothing is optional
- scientists discovered girls who get their back blown out sleep 47% better

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the fake study. Examples:
- Baking: "a new study found that girls who bake also know how to get a rise out of him"
- Gardening: "research shows women who garden are 89% more likely to make him beg"
- Herbalism: "scientists discovered girls who brew tea also brew trouble in the bedroom"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make it sound official but obviously thirsty.""",

    "shock_humor": """## On-Screen Caption Instructions

SHOCK HUMOR style: one-liner punchlines that are overtly sexual/suggestive but funny.

Short, punchy, catches you off guard. Mix wholesome framing with explicit implications.

Examples (for format only, create NEW ones):
- i'm so nice i pretend to gag on the small ones too
- just the tip never hurt a friendship
- i hate small talk just ask me if i want round 3

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the shock humor. Examples:
- Baking: "i spend hours on my sourdough but i'd spend longer on him"
- Beekeeping: "they say i'm sweet as honey but wait til you taste me"
- Knitting: "i can do more with my hands than just knit"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make it funny and filthy.""",

    "female_desire": """## On-Screen Caption Instructions

FEMALE DESIRE style: "girl math", "my toxic trait", centering her horniness and control.

Flip the dynamic - she's the one dictating terms, being feral, wanting him.

Examples (for format only, create NEW ones):
- girl math is not wanting a relationship + planning our wedding after one compliment
- my toxic trait is thinking one good cuddle will fix my abandonment issues
- i think my biggest turn on is knowing i turned you on

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the female desire context. Examples:
- Gardening: "my toxic trait is wanting a man who will help me garden and also ruin me"
- Baking: "girl math is baking him cookies and expecting him to wife me immediately"
- Farm life: "my toxic trait is daydreaming about farm life with a man i met yesterday"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make her the one in control.""",

    "kink_subculture": """## On-Screen Caption Instructions

KINK SUBCULTURE style: niche internet slang, gooning references, meta-horny behavior.

Casual, lowercase, treats niche kink stuff as normal daily activity. Very online.

Examples (for format only, create NEW ones):
- why do people get mad when you goon to them i'd feel chosen honestly
- me and who edging each other until we forget our own names
- the way i'd let him ruin my life respectfully

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the kink context. Examples:
- Foraging: "me and who foraging for mushrooms then breeding in the forest"
- Baking: "the way i'd let him use me like his favorite rolling pin"
- Herbalism: "gooning to a man who brings me wildflowers is self care actually"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make it very online and unhinged.""",

    "mock_qa": """## On-Screen Caption Instructions

MOCK Q&A style: fake genuine questions to men that expose sexual curiosity.

Format: "genuine question:", "men please be honest:", "boys help me understand:"

Examples (for format only, create NEW ones):
- genuine question: how do you walk around with that thing all day and act normal
- men please be honest: do you actually like when we're on top or are you just being polite
- boys help me understand: why does it twitch like that

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the question. Examples:
- Baking: "genuine question: do guys actually find girls who bake attractive or is that a myth"
- Gardening: "men be honest: would you let a girl who talks to her plants boss you around"
- Farm life: "boys help me understand: do you want the cottage wife or not"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make it sound innocent but obviously thirsty.""",

    "comment_bait": """## On-Screen Caption Instructions

COMMENT BAIT style: direct prompts to get engagement in comments about thirsty topics.

Format: "be honest in the comments:", "boys let's talk about:", "girls help me out:"

Examples (for format only, create NEW ones):
- be honest in the comments: what's the biggest L you took in the bedroom
- boys let's talk about: do you even know what you're doing down there or are you freestyling
- girls help me out: is it normal to want round 4 or am i broken

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the comment bait. Examples:
- Baking: "be honest in the comments: would you wife a girl who bakes for you"
- Foraging: "boys let's talk about: forest dates or nah"
- Herbalism: "girls help me out: is making him tea giving pick me or wife material"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make people want to comment.""",

    "chaotic_relatable": """## On-Screen Caption Instructions

CHAOTIC RELATABLE style: sexual but framed as chaotic daily life. "me when..." overshares.

Pair normal behavior with unhinged sexual overshare.

Examples (for format only, create NEW ones):
- me preparing to get on top for a total of 34 seconds
- when he likes lasting for ages but ur legs already gave out after 5 min
- me changing my sheets at 2am for absolutely no reason haha why would i do that

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the chaotic relatable context. Examples:
- Baking: "me baking at 3am because i'm stressed about him not texting back"
- Gardening: "when ur supposed to be gardening but u can't stop thinking about him"
- Foraging: "me pretending to forage but actually just daydreaming about sitting on his face"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Make it chaotic and relatable.""",

    "visual_punchline": """## On-Screen Caption Instructions

VISUAL PUNCHLINE style: setup only, the video/image carries the punchline. Ends with colon.

The caption sets up expectations, the visual delivers the thirsty punchline.

Examples (for format only, create NEW ones):
- when your selfies aren't hitting so you have to pull out the forbidden pose:
- the face i make when he says he's on his way:
- how i look at him when he doesn't know i'm planning our entire future:

CRITICAL: The caption MUST reference the cottagecore theme's activities or elements IN the setup. Examples:
- Baking: "how i look at him when he eats what i made:"
- Gardening: "the face i make when he offers to help in the garden:"
- Foraging: "when he asks if i want to go on a nature walk:"

The caption should only make sense for THAT theme. Generic captions are not allowed.

All lowercase, no periods. Setup only, end with colon."""
}

PROMPT_GENERATION_TEMPLATE = """You are generating {count} detailed i2i (image-to-image) prompts for realistic vertical iPhone photos designed for Instagram and TikTok.

## Output Format
- Output EXACTLY {count} prompts
- Each prompt is ONE self-contained paragraph
- Separate each prompt with exactly: ---
- No numbering, no bullet points, no meta explanations

## Core Requirements (EVERY prompt must include these EXACTLY)
- Every prompt MUST start with: "realistic vertical iPhone photo in 9:16 aspect ratio of the woman in the photo, preserving her exact facial features and natural skin texture,"
- This MUST look like a real photo taken on a phone and posted to social media. NO airbrushing, NO CGI look, NO anime-style faces. Real skin texture, real lighting, real person.
- For cosplay: continue with "dressed in cosplay as [character]" - she is a REAL HUMAN wearing a COSTUME. Include wigs and colored contacts if the character has unusual hair/eye colors - that's what real cosplayers do. But her FACE must still look like a real human face, not an anime face.
- The on-screen caption MUST use this EXACT structure:
  "There is an off-center TikTok-style on-screen caption that is only an overlaid text and is not related to her pose or movement, which reads: "[CAPTION]" in Proxima Nova Semibold font in white text with a thin black outline, all lowercase, no other text, logos, or UI elements."

## Location Instructions
{location_instructions}

## Style Instructions
{style_instructions}

{caption_instructions}

## Style Notes
- Casual Instagram/TikTok photo
- Brief pose/expression note (small smile, looking at camera, casual posture)

## BANNED WORDS - Never use these in prompts or captions:
assassination, assassin, kill, killing, murder, death, blood, violent, weapon, gun, knife, stab

Generate {count} unique prompts now. Remember: separate with --- and include ALL required elements in EVERY prompt."""


def get_random_caption_instructions(style: str = "cosplay") -> tuple[str, str]:
    """Get caption instructions from a random category based on style"""
    categories = COSPLAY_CAPTION_CATEGORIES if style == "cosplay" else COTTAGECORE_CAPTION_CATEGORIES
    category = random.choice(list(categories.keys()))
    return categories[category], category


def build_location_instructions(location_type: str, style: str = "cosplay") -> str:
    """Build location instructions based on type and style"""
    if style == "cottagecore":
        if location_type == "outdoor":
            return """Generate VARIED outdoor rural locations across different US areas (Montana meadows, Idaho forests, Vermont farms, Wyoming prairies, Oregon countryside, Maine woodlands, Tennessee hills, North Carolina mountains, Wisconsin pastures, etc.).
Include specific natural landmarks like wildflower fields, creek beds, wooden fences, old barns, orchards, rolling hills.
Mix it up - don't repeat the same area or landmark. Be creative with real rural places."""
        elif location_type == "indoor":
            return """Generate VARIED indoor cottagecore locations: cozy cottages, farmhouse kitchens, sunlit reading nooks, rustic bedrooms with quilts, greenhouse interiors, candle-lit spaces.
Describe the specific vibe (warm morning light, dried flowers hanging, handmade quilts, wooden beams, vintage furniture, etc.).
Mix it up - don't repeat the same setting."""
        else:  # mixed
            return """Generate a MIX of indoor and outdoor rural locations.
Outdoor: various rural US areas (Montana meadows, Vermont farms, Oregon countryside, Maine woodlands, etc.) with natural landmarks like wildflower fields, creek beds, old barns.
Indoor: cozy cottages, farmhouse kitchens, rustic bedrooms, greenhouse interiors with specific vibes.
Vary between indoor and outdoor. Don't repeat locations."""
    else:
        # Cosplay uses urban locations
        if location_type == "outdoor":
            return """Generate VARIED outdoor locations across different US cities (NYC, Miami, LA, Vegas, Chicago, Austin, etc.).
Include specific recognizable landmarks, streets, or venues for each city.
Mix it up - don't repeat the same city or landmark. Be creative with real places."""
        elif location_type == "indoor":
            return """Generate VARIED indoor locations: bedrooms, apartments, convention halls, etc.
Describe the specific vibe (cozy with fairy lights, minimalist, aesthetic with LED lights, convention with cosplayers in background, etc.).
Mix it up - don't repeat the same setting."""
        else:  # mixed
            return """Generate a MIX of indoor and outdoor locations.
Outdoor: various US cities (NYC, Miami, LA, Vegas, Chicago, Austin, etc.) with specific landmarks.
Indoor: bedrooms, apartments, conventions with specific vibes.
Vary between indoor and outdoor. Don't repeat locations."""


def build_style_instructions(style: str) -> str:
    """Build style-specific instructions (cosplay or cottagecore)"""
    if style == "cottagecore":
        return """Include cottagecore outfits and themes in the prompts.
Pick DIFFERENT cottagecore themes each time - vary the inspirations: gardening, baking, foraging, herbalism, beekeeping, flower pressing, candle making, knitting, reading by firelight, berry picking, farm life, mushroom hunting, picnicking, jam making.
Include ACCURATE outfit details for each theme (prairie dresses, puff sleeves, Peter Pan collars, milkmaid tops, flowy linen dresses, gingham patterns, floral aprons, embroidered blouses, lace details, straw hats, woven baskets, ankle boots, flower crowns, earthy and muted tones).
Don't repeat the same theme. Be accurate with aesthetic details."""
    else:  # cosplay
        return """THIS IS COSPLAY - A REAL HUMAN WEARING A COSTUME IN A REAL PHOTO.

The prompt must describe a REAL PERSON dressed in a COSPLAY COSTUME. This is what cosplayers actually look like:
- Real human face with natural skin texture (NOT airbrushed, NOT anime-style, NOT CGI)
- Wearing a costume (often handmade/amateur quality)
- Wearing a WIG if the character has unusual hair color
- Wearing COLORED CONTACTS if the character has unusual eye color
- Real iPhone photo quality - the kind you'd see posted on Instagram or TikTok

CORRECT: "the woman in the photo is dressed in cosplay as Miku, wearing a grey school uniform with teal tie, teal twintail wig, and teal colored contacts..."
WRONG: "Hatsune Miku with perfect porcelain skin and large anime eyes..." (this creates an airbrushed anime face, NOT a real person)

The face must look HUMAN. Real pores, real skin, real proportions. Just a normal person who put on a costume and wig.

Pick DIFFERENT anime characters each time - vary the source anime/manga.
Include ACCURATE costume details (clothing, accessories, wigs, colored contacts where appropriate).
Examples: Attack on Titan, Sailor Moon, Evangelion, Chainsaw Man, Jujutsu Kaisen, One Piece, Demon Slayer, My Hero Academia, Spy x Family, etc.
Don't repeat the same character."""


async def generate_prompts(
    api_key: str,
    count: int,
    style: Literal["cosplay", "cottagecore"],
    location: Literal["outdoor", "indoor", "mixed"],
    exaggerated_bust: bool = False,
) -> list[str]:
    """
    Generate i2i prompts using Claude.

    Args:
        api_key: Anthropic API key
        count: Number of prompts to generate (1-50)
        style: "cosplay" or "cottagecore"
        location: "outdoor", "indoor", or "mixed"
        exaggerated_bust: If True, add exaggerated bust description to prompts

    Returns:
        List of generated prompts
    """
    if count < 1 or count > 50:
        raise ValueError("Count must be between 1 and 50")

    client = anthropic.Anthropic(api_key=api_key)

    location_instructions = build_location_instructions(location, style)
    style_instructions = build_style_instructions(style)
    caption_instructions, category = get_random_caption_instructions(style)

    logger.info(
        "Generating prompts",
        count=count,
        style=style,
        location=location,
        caption_category=category,
    )

    prompt = PROMPT_GENERATION_TEMPLATE.format(
        count=count,
        location_instructions=location_instructions,
        style_instructions=style_instructions,
        caption_instructions=caption_instructions,
    )

    message = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )

    raw_text = message.content[0].text.strip()

    # Parse prompts - split by --- and clean each one
    raw_prompts = raw_text.split("---")
    clean_prompts = []
    for p in raw_prompts:
        # Remove line breaks within prompt, collapse to single line
        cleaned = " ".join(p.strip().split())
        if cleaned:
            # Inject exaggerated bust text if enabled
            if exaggerated_bust:
                # Find a good injection point - after describing the woman/subject
                # Look for common patterns and inject after them
                bust_text = "with an oversized bust, exaggerated chest size,"
                # Inject early in the prompt, after "the woman in the photo"
                if "the woman in the photo," in cleaned:
                    cleaned = cleaned.replace(
                        "the woman in the photo,",
                        f"the woman in the photo, {bust_text}",
                        1
                    )
                elif "the woman in the photo" in cleaned:
                    cleaned = cleaned.replace(
                        "the woman in the photo",
                        f"the woman in the photo {bust_text}",
                        1
                    )
                else:
                    # Fallback: add near the beginning after first comma
                    first_comma = cleaned.find(",")
                    if first_comma > 0:
                        cleaned = cleaned[:first_comma + 1] + f" {bust_text}" + cleaned[first_comma + 1:]
                    else:
                        cleaned = f"{bust_text} {cleaned}"
            clean_prompts.append(cleaned)

    logger.info("Generated prompts", requested=count, actual=len(clean_prompts), exaggerated_bust=exaggerated_bust)

    return clean_prompts
