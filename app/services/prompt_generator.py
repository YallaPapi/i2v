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

# Gym/Fitness caption categories
GYM_CAPTION_CATEGORIES = {
    "fake_innocence": """## On-Screen Caption Instructions

FAKE INNOCENCE style: innocent claim + reveal it's actually thirsty/sexual.

The reveal must be FLIRTY and SUGGESTIVE - about wanting him, attraction, hooking up, physical desire. NOT about friendship or platonic feelings.

Examples (for format only, create NEW ones):
- "we're just friends" also us at 2am:
- "i'm not that type of girl" also me after he whispers in my ear:
- "let's just cuddle" me 5 minutes later:

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the thirsty context. Examples:
- "i'm just here for the gains" also me staring at him between sets:
- "it's just a gym crush" also me planning our post-workout meals together:
- "i only need a spotter" also me needing him to spot me at home too:

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Keep it spicy.""",

    "pov_situation": """## On-Screen Caption Instructions

POV style: drop the viewer into a specific thirsty/flirty moment using "pov:" or "when..."

The situation must be SUGGESTIVE - about tension, attraction, wanting him, almost hooking up. NOT wholesome or platonic.

Examples (for format only, create NEW ones):
- pov: he said we're just watching a movie
- when he pulls you closer and says "come here"
- pov: you're trying to be good but he keeps looking at you like that

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the thirsty context. Examples:
- pov: he asked to spot you and now you can't focus on the lift
- when he fixes your squat form and his hands are still on your hips
- pov: you made eye contact during hip thrusts and now it's weird

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make the viewer feel the tension.""",

    "fake_study": """## On-Screen Caption Instructions

FAKE STUDY style: pose as fake research/statistics/rules that are actually thirsty/sexual.

Format: "a new study found that...", "rule number 1:", "scientists discovered...", "research shows..."

Examples (for format only, create NEW ones):
- a new study found that sitting on his face 3x a week reduces stress by 110%
- rule number 1 of dating me: morning cuddles are mandatory and clothing is optional
- scientists discovered girls who get their back blown out sleep 47% better

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the fake study. Examples:
- a new study found that girls who never skip leg day also never skip—
- research shows gym girls have 200% more stamina where it counts
- scientists discovered hip thrusts improve performance in other areas too

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make it sound official but obviously thirsty.""",

    "shock_humor": """## On-Screen Caption Instructions

SHOCK HUMOR style: one-liner punchlines that are overtly sexual/suggestive but funny.

Short, punchy, catches you off guard. Mix wholesome framing with explicit implications.

Examples (for format only, create NEW ones):
- i'm so nice i pretend to gag on the small ones too
- just the tip never hurt a friendship
- i hate small talk just ask me if i want round 3

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the shock humor. Examples:
- i do hip thrusts for him not for me let's be honest
- my squat PR is nothing compared to what i can do on top
- i have great stamina at the gym but even better stamina at home

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make it funny and filthy.""",

    "female_desire": """## On-Screen Caption Instructions

FEMALE DESIRE style: "girl math", "my toxic trait", centering her horniness and control.

Flip the dynamic - she's the one dictating terms, being feral, wanting him.

Examples (for format only, create NEW ones):
- girl math is not wanting a relationship + planning our wedding after one compliment
- my toxic trait is thinking one good cuddle will fix my abandonment issues
- i think my biggest turn on is knowing i turned you on

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the female desire context. Examples:
- my toxic trait is wanting a gym boyfriend just so we can shower together after
- girl math is seeing him lift heavy and immediately planning our future
- my toxic trait is thinking couples who gym together stay together forever

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make her the one in control.""",

    "kink_subculture": """## On-Screen Caption Instructions

KINK SUBCULTURE style: niche internet slang, gooning references, meta-horny behavior.

Casual, lowercase, treats niche kink stuff as normal daily activity. Very online.

Examples (for format only, create NEW ones):
- why do people get mad when you goon to them i'd feel chosen honestly
- me and who edging each other until we forget our own names
- the way i'd let him ruin my life respectfully

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the kink context. Examples:
- the way i'd let him use me like gym equipment
- me and who doing partner stretches that turn into something else
- gooning to gym bros is cardio actually

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make it very online and unhinged.""",

    "mock_qa": """## On-Screen Caption Instructions

MOCK Q&A style: fake genuine questions to men that expose sexual curiosity.

Format: "genuine question:", "men please be honest:", "boys help me understand:"

Examples (for format only, create NEW ones):
- genuine question: how do you walk around with that thing all day and act normal
- men please be honest: do you actually like when we're on top or are you just being polite
- boys help me understand: why does it twitch like that

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the question. Examples:
- genuine question: do gym guys actually find gym girls attractive or is that just me being delusional
- men be honest: do you look at us during hip thrusts or are you being respectful
- boys help me understand: why do you grunt like that when you lift

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make it sound innocent but obviously thirsty.""",

    "comment_bait": """## On-Screen Caption Instructions

COMMENT BAIT style: direct prompts to get engagement in comments about thirsty topics.

Format: "be honest in the comments:", "boys let's talk about:", "girls help me out:"

Examples (for format only, create NEW ones):
- be honest in the comments: what's the biggest L you took in the bedroom
- boys let's talk about: do you even know what you're doing down there or are you freestyling
- girls help me out: is it normal to want round 4 or am i broken

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the comment bait. Examples:
- be honest: gym couples or nah
- boys let's talk about: do you actually like strong girls or is that just internet talk
- girls help me out: is it normal to get distracted by him mid-set

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make people want to comment.""",

    "chaotic_relatable": """## On-Screen Caption Instructions

CHAOTIC RELATABLE style: sexual but framed as chaotic daily life. "me when..." overshares.

Pair normal behavior with unhinged sexual overshare.

Examples (for format only, create NEW ones):
- me preparing to get on top for a total of 34 seconds
- when he likes lasting for ages but ur legs already gave out after 5 min
- me changing my sheets at 2am for absolutely no reason haha why would i do that

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the chaotic relatable context. Examples:
- me having gym stamina but tapping out after round 2 anyway
- when you do hip thrusts at the gym but can't do them at home for more than a minute
- me saying i'm too sore from leg day but making an exception for him

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Make it chaotic and relatable.""",

    "visual_punchline": """## On-Screen Caption Instructions

VISUAL PUNCHLINE style: setup only, the video/image carries the punchline. Ends with colon.

The caption sets up expectations, the visual delivers the thirsty punchline.

Examples (for format only, create NEW ones):
- when your selfies aren't hitting so you have to pull out the forbidden pose:
- the face i make when he says he's on his way:
- how i look at him when he doesn't know i'm planning our entire future:

CRITICAL: The caption MUST reference gym/fitness activities, culture, or terminology IN the setup. Examples:
- the look i give him across the gym when he's not paying attention:
- how i look at him when he offers to spot me:
- the face i make when he asks if i need a gym partner:

The caption should only make sense in a FITNESS context. Generic captions are not allowed.

All lowercase, no periods. Setup only, end with colon."""
}

# Bookish/Dark Academia caption categories
BOOKISH_CAPTION_CATEGORIES = {
    "fake_innocence": """## On-Screen Caption Instructions

FAKE INNOCENCE style: innocent claim + reveal it's actually thirsty/sexual.

The reveal must be FLIRTY and SUGGESTIVE - about wanting him, attraction, hooking up, physical desire. NOT about friendship or platonic feelings.

Examples (for format only, create NEW ones):
- "we're just friends" also us at 2am:
- "i'm not that type of girl" also me after he whispers in my ear:
- "let's just cuddle" me 5 minutes later:

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the thirsty context. Examples:
- "i just like reading" also me after finishing that spicy chapter:
- "it's just a book boyfriend" also me wanting the real thing now:
- "i'm just at the library to study" also me studying him instead:

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Keep it spicy.""",

    "pov_situation": """## On-Screen Caption Instructions

POV style: drop the viewer into a specific thirsty/flirty moment using "pov:" or "when..."

The situation must be SUGGESTIVE - about tension, attraction, wanting him, almost hooking up. NOT wholesome or platonic.

Examples (for format only, create NEW ones):
- pov: he said we're just watching a movie
- when he pulls you closer and says "come here"
- pov: you're trying to be good but he keeps looking at you like that

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the thirsty context. Examples:
- pov: he caught you reading the spicy scene and wants to reenact it
- when he reads over your shoulder and sees what chapter you're on
- pov: you're in the quiet section of the library and he won't stop staring

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make the viewer feel the tension.""",

    "fake_study": """## On-Screen Caption Instructions

FAKE STUDY style: pose as fake research/statistics/rules that are actually thirsty/sexual.

Format: "a new study found that...", "rule number 1:", "scientists discovered...", "research shows..."

Examples (for format only, create NEW ones):
- a new study found that sitting on his face 3x a week reduces stress by 110%
- rule number 1 of dating me: morning cuddles are mandatory and clothing is optional
- scientists discovered girls who get their back blown out sleep 47% better

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the fake study. Examples:
- a new study found that girls who read smut have higher standards and better ideas
- research shows romance readers give 200% better girlfriend energy
- scientists discovered reading spicy books improves real life performance

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make it sound official but obviously thirsty.""",

    "shock_humor": """## On-Screen Caption Instructions

SHOCK HUMOR style: one-liner punchlines that are overtly sexual/suggestive but funny.

Short, punchy, catches you off guard. Mix wholesome framing with explicit implications.

Examples (for format only, create NEW ones):
- i'm so nice i pretend to gag on the small ones too
- just the tip never hurt a friendship
- i hate small talk just ask me if i want round 3

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the shock humor. Examples:
- i've read enough smut to know exactly what to do don't worry
- my favorite books have 3 chapters i keep rereading if you know what i mean
- i annotate my books and i'd annotate him too

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make it funny and filthy.""",

    "female_desire": """## On-Screen Caption Instructions

FEMALE DESIRE style: "girl math", "my toxic trait", centering her horniness and control.

Flip the dynamic - she's the one dictating terms, being feral, wanting him.

Examples (for format only, create NEW ones):
- girl math is not wanting a relationship + planning our wedding after one compliment
- my toxic trait is thinking one good cuddle will fix my abandonment issues
- i think my biggest turn on is knowing i turned you on

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the female desire context. Examples:
- my toxic trait is comparing every guy to my book boyfriends and being disappointed
- girl math is reading enemies to lovers and manifesting it with my situationship
- my toxic trait is wanting a man who reads but also wanting to corrupt him

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make her the one in control.""",

    "kink_subculture": """## On-Screen Caption Instructions

KINK SUBCULTURE style: niche internet slang, gooning references, meta-horny behavior.

Casual, lowercase, treats niche kink stuff as normal daily activity. Very online.

Examples (for format only, create NEW ones):
- why do people get mad when you goon to them i'd feel chosen honestly
- me and who edging each other until we forget our own names
- the way i'd let him ruin my life respectfully

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the kink context. Examples:
- me and who reading spicy books together and acting out the scenes
- the way i'd let him do what chapter 23 described
- reading smut in public is an act of bravery actually

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make it very online and unhinged.""",

    "mock_qa": """## On-Screen Caption Instructions

MOCK Q&A style: fake genuine questions to men that expose sexual curiosity.

Format: "genuine question:", "men please be honest:", "boys help me understand:"

Examples (for format only, create NEW ones):
- genuine question: how do you walk around with that thing all day and act normal
- men please be honest: do you actually like when we're on top or are you just being polite
- boys help me understand: why does it twitch like that

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the question. Examples:
- genuine question: do guys actually find bookish girls attractive or is that just a trope
- men be honest: would you date a girl who reads smut in public
- boys help me understand: do you like when we recommend you books or is that annoying

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make it sound innocent but obviously thirsty.""",

    "comment_bait": """## On-Screen Caption Instructions

COMMENT BAIT style: direct prompts to get engagement in comments about thirsty topics.

Format: "be honest in the comments:", "boys let's talk about:", "girls help me out:"

Examples (for format only, create NEW ones):
- be honest in the comments: what's the biggest L you took in the bedroom
- boys let's talk about: do you even know what you're doing down there or are you freestyling
- girls help me out: is it normal to want round 4 or am i broken

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the comment bait. Examples:
- be honest: dark academia girls or cottagecore girls
- girls help me out: is it normal to be attracted to fictional men more than real ones
- boys let's talk about: do you find it hot when we read or is that just in movies

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make people want to comment.""",

    "chaotic_relatable": """## On-Screen Caption Instructions

CHAOTIC RELATABLE style: sexual but framed as chaotic daily life. "me when..." overshares.

Pair normal behavior with unhinged sexual overshare.

Examples (for format only, create NEW ones):
- me preparing to get on top for a total of 34 seconds
- when he likes lasting for ages but ur legs already gave out after 5 min
- me changing my sheets at 2am for absolutely no reason haha why would i do that

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the chaotic relatable context. Examples:
- me reading 300 pages of smut and calling it self improvement
- when he doesn't read but you're trying to fix him with book recommendations
- me saying i'm reading but actually just rereading that one scene for the 10th time

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Make it chaotic and relatable.""",

    "visual_punchline": """## On-Screen Caption Instructions

VISUAL PUNCHLINE style: setup only, the video/image carries the punchline. Ends with colon.

The caption sets up expectations, the visual delivers the thirsty punchline.

Examples (for format only, create NEW ones):
- when your selfies aren't hitting so you have to pull out the forbidden pose:
- the face i make when he says he's on his way:
- how i look at him when he doesn't know i'm planning our entire future:

CRITICAL: The caption MUST reference books, reading, libraries, or bookish culture IN the setup. Examples:
- how i look at him over my book when he's not paying attention:
- the face i make when he asks what i'm reading and it's smut:
- when someone asks why i'm blushing at my book:

The caption should only make sense in a BOOKISH context. Generic captions are not allowed.

All lowercase, no periods. Setup only, end with colon."""
}

# Nurse/Medical caption categories
NURSE_CAPTION_CATEGORIES = {
    "fake_innocence": """## On-Screen Caption Instructions

FAKE INNOCENCE style: innocent claim + reveal it's actually thirsty/sexual.

The reveal must be FLIRTY and SUGGESTIVE - about wanting him, attraction, hooking up, physical desire. NOT about friendship or platonic feelings.

Examples (for format only, create NEW ones):
- "we're just friends" also us at 2am:
- "i'm not that type of girl" also me after he whispers in my ear:
- "let's just cuddle" me 5 minutes later:

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the thirsty context. Examples:
- "i'm just here to take your vitals" also me checking him out:
- "it's just a 12 hour shift" also me thinking about him the whole time:
- "i just like helping people" also me wanting to help myself to him:

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Keep it spicy.""",

    "pov_situation": """## On-Screen Caption Instructions

POV style: drop the viewer into a specific thirsty/flirty moment using "pov:" or "when..."

The situation must be SUGGESTIVE - about tension, attraction, wanting him, almost hooking up. NOT wholesome or platonic.

Examples (for format only, create NEW ones):
- pov: he said we're just watching a movie
- when he pulls you closer and says "come here"
- pov: you're trying to be good but he keeps looking at you like that

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the thirsty context. Examples:
- pov: he keeps hitting the call button just to see you
- when you're checking his heart rate and yours is higher than his
- pov: he asked if you do house calls and you said yes

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make the viewer feel the tension.""",

    "fake_study": """## On-Screen Caption Instructions

FAKE STUDY style: pose as fake research/statistics/rules that are actually thirsty/sexual.

Format: "a new study found that...", "rule number 1:", "scientists discovered...", "research shows..."

Examples (for format only, create NEW ones):
- a new study found that sitting on his face 3x a week reduces stress by 110%
- rule number 1 of dating me: morning cuddles are mandatory and clothing is optional
- scientists discovered girls who get their back blown out sleep 47% better

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the fake study. Examples:
- a new study found that nurses give the best aftercare in every sense
- research shows girls in scrubs have 200% more healing energy if you know what i mean
- scientists discovered nurses have better bedside manner everywhere

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make it sound official but obviously thirsty.""",

    "shock_humor": """## On-Screen Caption Instructions

SHOCK HUMOR style: one-liner punchlines that are overtly sexual/suggestive but funny.

Short, punchy, catches you off guard. Mix wholesome framing with explicit implications.

Examples (for format only, create NEW ones):
- i'm so nice i pretend to gag on the small ones too
- just the tip never hurt a friendship
- i hate small talk just ask me if i want round 3

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the shock humor. Examples:
- 12 hour shifts but i'd do overtime for him
- i've seen a lot in this job but i'd still be impressed
- they say nurses have healing hands and yeah they're right

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make it funny and filthy.""",

    "female_desire": """## On-Screen Caption Instructions

FEMALE DESIRE style: "girl math", "my toxic trait", centering her horniness and control.

Flip the dynamic - she's the one dictating terms, being feral, wanting him.

Examples (for format only, create NEW ones):
- girl math is not wanting a relationship + planning our wedding after one compliment
- my toxic trait is thinking one good cuddle will fix my abandonment issues
- i think my biggest turn on is knowing i turned you on

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the female desire context. Examples:
- my toxic trait is wanting to take care of him in ways insurance doesn't cover
- girl math is being too tired after work but making an exception for him
- my toxic trait is dating patients (jk) (unless)

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make her the one in control.""",

    "kink_subculture": """## On-Screen Caption Instructions

KINK SUBCULTURE style: niche internet slang, gooning references, meta-horny behavior.

Casual, lowercase, treats niche kink stuff as normal daily activity. Very online.

Examples (for format only, create NEW ones):
- why do people get mad when you goon to them i'd feel chosen honestly
- me and who edging each other until we forget our own names
- the way i'd let him ruin my life respectfully

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the kink context. Examples:
- the way i'd play doctor with him no questions asked
- me and who doing a private examination after hours
- gooning in scrubs is just called a night shift actually

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make it very online and unhinged.""",

    "mock_qa": """## On-Screen Caption Instructions

MOCK Q&A style: fake genuine questions to men that expose sexual curiosity.

Format: "genuine question:", "men please be honest:", "boys help me understand:"

Examples (for format only, create NEW ones):
- genuine question: how do you walk around with that thing all day and act normal
- men please be honest: do you actually like when we're on top or are you just being polite
- boys help me understand: why does it twitch like that

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the question. Examples:
- genuine question: do guys actually have a thing for nurses or is that just tv
- men be honest: is it the scrubs or is it just me
- boys help me understand: why do you act different when i say i'm a nurse

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make it sound innocent but obviously thirsty.""",

    "comment_bait": """## On-Screen Caption Instructions

COMMENT BAIT style: direct prompts to get engagement in comments about thirsty topics.

Format: "be honest in the comments:", "boys let's talk about:", "girls help me out:"

Examples (for format only, create NEW ones):
- be honest in the comments: what's the biggest L you took in the bedroom
- boys let's talk about: do you even know what you're doing down there or are you freestyling
- girls help me out: is it normal to want round 4 or am i broken

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the comment bait. Examples:
- be honest: would you let a nurse take care of you
- boys let's talk about: the nurse fantasy is it real or just memes
- girls help me out: do guys actually like the tired scrubs look or am i delusional

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make people want to comment.""",

    "chaotic_relatable": """## On-Screen Caption Instructions

CHAOTIC RELATABLE style: sexual but framed as chaotic daily life. "me when..." overshares.

Pair normal behavior with unhinged sexual overshare.

Examples (for format only, create NEW ones):
- me preparing to get on top for a total of 34 seconds
- when he likes lasting for ages but ur legs already gave out after 5 min
- me changing my sheets at 2am for absolutely no reason haha why would i do that

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the chaotic relatable context. Examples:
- me after a 12 hour shift still looking like this:
- when you're exhausted from work but he's coming over so you find the energy
- me taking care of patients all day then going home to take care of him

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Make it chaotic and relatable.""",

    "visual_punchline": """## On-Screen Caption Instructions

VISUAL PUNCHLINE style: setup only, the video/image carries the punchline. Ends with colon.

The caption sets up expectations, the visual delivers the thirsty punchline.

Examples (for format only, create NEW ones):
- when your selfies aren't hitting so you have to pull out the forbidden pose:
- the face i make when he says he's on his way:
- how i look at him when he doesn't know i'm planning our entire future:

CRITICAL: The caption MUST reference nursing, medical work, scrubs, or healthcare IN the setup. Examples:
- the look i give when he says he's not feeling well:
- how i look at him when he asks if i can check something for him:
- the face i make when he says nurses are his type:

The caption should only make sense in a NURSE/MEDICAL context. Generic captions are not allowed.

All lowercase, no periods. Setup only, end with colon."""
}

PROMPT_GENERATION_TEMPLATE = """You are generating {count} detailed i2i (image-to-image) prompts for realistic vertical iPhone photos designed for Instagram and TikTok.

## Output Format
- Output EXACTLY {count} prompts
- Separate each prompt with exactly: ---
- No numbering, no bullet points, no meta explanations
- CRITICAL: Use COMMA-SEPARATED SEGMENTS, not run-on sentences. Each detail is its own chunk separated by commas.

## Prompt Structure (comma-separated segments)
Format each prompt like this, with commas separating each segment:
"{framing_prefix}realistic vertical iPhone photo, 9:16 aspect ratio, woman in the photo{identity_text}, [outfit/costume details], [pose/expression], [location], [lighting]{realism_suffix}, on-screen caption reads: [CAPTION]"

Example of CORRECT comma-separated format:
"Medium shot of realistic vertical iPhone photo, 9:16 aspect ratio, woman in the photo, preserving her exact facial features, dressed as Miku in grey school uniform with teal tie, teal twintail wig, teal colored contacts, slight smile, looking at camera, standing in Tokyo street at night, neon signs in background, natural ambient lighting, photographed on location, on-screen caption reads: pov he asked about my costume"

Example of WRONG run-on format:
"A realistic vertical iPhone photo in 9:16 aspect ratio of the woman in the photo who is dressed in cosplay as Miku wearing a grey school uniform with a teal tie and she has a teal twintail wig with teal colored contacts and she is smiling slightly while looking at the camera as she stands in a Tokyo street at night with neon signs behind her..."

## Core Requirements
- Real iPhone photo quality - NOT airbrushed, NOT CGI, NOT anime-style
- Real skin texture, real lighting, real person
- For cosplay: REAL HUMAN wearing a COSTUME with wigs/colored contacts as needed
- The on-screen caption segment MUST be: "on-screen caption reads: [CAPTION]"
- Caption is TikTok-style, off-center, Proxima Nova Semibold, white text with thin black outline

## Location Instructions
{location_instructions}

## Style Instructions
{style_instructions}

{caption_instructions}

## Pose/Expression Notes
- Keep it brief: "slight smile, looking at camera" or "casual posture, playful expression"
- Instagram/TikTok selfie energy

## BANNED WORDS - Never use these:
assassination, assassin, kill, killing, murder, death, blood, violent, weapon, gun, knife, stab

Generate {count} unique prompts now. Use comma-separated segments. Separate prompts with ---"""


def get_random_caption_instructions(style: str = "cosplay") -> tuple[str, str]:
    """Get caption instructions from a random category based on style"""
    style_to_categories = {
        "cosplay": COSPLAY_CAPTION_CATEGORIES,
        "cottagecore": COTTAGECORE_CAPTION_CATEGORIES,
        "gym": GYM_CAPTION_CATEGORIES,
        "bookish": BOOKISH_CAPTION_CATEGORIES,
        "nurse": NURSE_CAPTION_CATEGORIES,
    }
    categories = style_to_categories.get(style, COSPLAY_CAPTION_CATEGORIES)
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
    elif style == "gym":
        if location_type == "outdoor":
            return """Generate VARIED outdoor fitness locations: outdoor tracks, park workout areas, beach fitness spots, hiking trails, outdoor yoga spaces, rooftop workout areas with city views.
Include specific vibes: early morning light, golden hour, post-workout glow, athletic energy.
Mix it up - don't repeat the same setting."""
        elif location_type == "indoor":
            return """Generate VARIED indoor gym/fitness locations: commercial gym floor with equipment, weight room with mirrors, yoga/pilates studio, CrossFit box, home gym setup, apartment workout space, gym locker room (tasteful).
Describe specific vibes: gym mirror selfie, post-workout glow, between sets, stretching area.
Mix it up - don't repeat the same setting."""
        else:  # mixed
            return """Generate a MIX of indoor and outdoor fitness locations.
Outdoor: outdoor tracks, park workouts, beach fitness, hiking trails, rooftop workout areas.
Indoor: commercial gyms, weight rooms, yoga studios, home gyms, locker rooms (tasteful).
Vary between indoor and outdoor. Don't repeat locations."""
    elif style == "bookish":
        if location_type == "outdoor":
            return """Generate VARIED outdoor bookish/reading locations: park benches with books, cafe patios, university quads, bookstore outdoor seating, library gardens, picnic blankets with books, coffee shop terraces.
Include specific vibes: cozy reading nook energy, dark academia aesthetic, intellectual atmosphere.
Mix it up - don't repeat the same setting."""
        elif location_type == "indoor":
            return """Generate VARIED indoor bookish locations: library reading rooms, cozy bookstore aisles, coffee shop corners, bedroom reading nooks with fairy lights, dark academia study rooms, home libraries, university libraries.
Describe specific vibes: surrounded by books, warm lighting, cozy sweater weather, holding a book.
Mix it up - don't repeat the same setting."""
        else:  # mixed
            return """Generate a MIX of indoor and outdoor bookish locations.
Outdoor: park benches, cafe patios, university quads, bookstore patios.
Indoor: libraries, bookstores, coffee shops, cozy reading nooks, dark academia settings.
Vary between indoor and outdoor. Don't repeat locations."""
    elif style == "nurse":
        if location_type == "outdoor":
            return """Generate VARIED outdoor nurse/medical locations: hospital entrance area, ambulance bay, outdoor break area near hospital, walking to/from car in scrubs, hospital parking structure, medical campus outdoor seating.
Include specific vibes: post-shift tired but cute, break time, arriving/leaving work.
Mix it up - don't repeat the same setting."""
        elif location_type == "indoor":
            return """Generate VARIED indoor nurse/medical locations: hospital corridor, nurse station, break room, locker room (tasteful), home after shift still in scrubs, bathroom mirror selfie in scrubs, living room in scrubs after work.
Describe specific vibes: 12-hour shift energy, break time vibes, post-shift at home, tired but still cute.
Mix it up - don't repeat the same setting."""
        else:  # mixed
            return """Generate a MIX of indoor and outdoor nurse/medical locations.
Outdoor: hospital entrances, ambulance bays, outdoor break areas, parking structures.
Indoor: hospital corridors, nurse stations, break rooms, home in scrubs after work.
Vary between indoor and outdoor. Don't repeat locations."""
    else:
        # Cosplay uses urban locations (default)
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
    """Build style-specific instructions for each niche"""
    if style == "cottagecore":
        return """Include cottagecore outfits and themes in the prompts.
Pick DIFFERENT cottagecore themes each time - vary the inspirations: gardening, baking, foraging, herbalism, beekeeping, flower pressing, candle making, knitting, reading by firelight, berry picking, farm life, mushroom hunting, picnicking, jam making.
Include ACCURATE outfit details for each theme (prairie dresses, puff sleeves, Peter Pan collars, milkmaid tops, flowy linen dresses, gingham patterns, floral aprons, embroidered blouses, lace details, straw hats, woven baskets, ankle boots, flower crowns, earthy and muted tones).
Don't repeat the same theme. Be accurate with aesthetic details."""
    elif style == "gym":
        return """THIS IS A FITNESS/GYM GIRL - A REAL WOMAN IN WORKOUT CLOTHES.

The prompt must describe a REAL PERSON in athletic wear. This is what gym girls actually look like:
- Real human face with natural skin texture, maybe some sweat/glow
- Wearing actual workout clothes (sports bras, leggings, shorts, tank tops)
- Hair typically in ponytail, bun, or braids for working out
- Real iPhone photo quality - gym mirror selfie or workout photo style

Include VARIED gym outfits: sports bras (various colors), high-waisted leggings, biker shorts, crop tops, tank tops, matching sets, sneakers.
Include gym accessories where appropriate: AirPods, scrunchie on wrist, gym bag, water bottle, resistance bands.
Describe the athletic vibe: post-workout glow, between sets, stretching, flexing casually.
Vary the outfits and colors. Don't repeat the same look."""
    elif style == "bookish":
        return """THIS IS A BOOKISH/DARK ACADEMIA GIRL - A REAL WOMAN WITH COZY INTELLECTUAL VIBES.

The prompt must describe a REAL PERSON with bookish aesthetic. This is what bookish girls actually look like:
- Real human face with natural skin texture
- Cozy, intellectual aesthetic clothing
- Often holding or near books
- Real iPhone photo quality - cozy selfie or reading nook style

Include VARIED bookish outfits: oversized sweaters, cardigans, turtlenecks, cozy knits, plaid skirts, collared shirts under sweaters, glasses (optional), earth tones, cream/brown/burgundy colors.
Include bookish props where appropriate: holding a book, coffee/tea cup, reading glasses, bookmark.
Describe the cozy vibe: warm lighting, surrounded by books, intellectual energy, soft and approachable.
Mix dark academia (structured, scholarly) with cozy bookworm (soft, comfortable) aesthetics.
Vary the outfits and settings. Don't repeat the same look."""
    elif style == "nurse":
        return """THIS IS A NURSE - A REAL WOMAN IN MEDICAL SCRUBS.

The prompt must describe a REAL PERSON in nurse/medical attire. This is what nurses actually look like:
- Real human face with natural skin texture, maybe tired but cute
- Wearing actual medical scrubs (various colors: ceil blue, navy, burgundy, black, pink, printed)
- Hair typically tied back for work
- Real iPhone photo quality - selfie in scrubs style

Include VARIED scrub colors and styles: ceil blue scrubs, navy scrubs, burgundy/wine scrubs, black scrubs, pink scrubs, fun printed scrubs.
Include medical accessories where appropriate: stethoscope around neck, badge/lanyard, comfortable nursing shoes, Apple Watch.
Describe the nurse vibe: post-shift tired but still cute, break time energy, hardworking healthcare worker aesthetic.
Can be at work (hospital, nurse station) or at home still in scrubs after a shift.
Vary the scrub colors and settings. Don't repeat the same look."""
    else:  # cosplay (default)
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
    style: Literal["cosplay", "cottagecore", "gym", "bookish", "nurse"],
    location: Literal["outdoor", "indoor", "mixed"],
    exaggerated_bust: bool = False,
    preserve_identity: bool = True,
    framing: Literal["close", "medium", "full"] = "medium",
    realism: bool = True,
) -> list[str]:
    """
    Generate i2i prompts using Claude.

    Args:
        api_key: Anthropic API key
        count: Number of prompts to generate (1-50)
        style: "cosplay" or "cottagecore"
        location: "outdoor", "indoor", or "mixed"
        exaggerated_bust: If True, add exaggerated bust description to prompts
        preserve_identity: If True, add "preserving her exact facial features" to prompts
        framing: "close" (face/shoulders), "medium" (waist up), "full" (head to toe)
        realism: If True, add anti-painted-background modifiers

    Returns:
        List of generated prompts
    """
    if count < 1 or count > 50:
        raise ValueError("Count must be between 1 and 50")

    client = anthropic.Anthropic(api_key=api_key)

    location_instructions = build_location_instructions(location, style)
    style_instructions = build_style_instructions(style)
    caption_instructions, category = get_random_caption_instructions(style)

    # Build identity preservation text
    identity_text = ", preserving her exact facial features and natural skin texture" if preserve_identity else ""

    # Build framing prefix
    framing_prefixes = {
        "close": "Close-up shot of ",
        "medium": "Medium shot of ",
        "full": "Full body shot of ",
    }
    framing_prefix = framing_prefixes.get(framing, "Medium shot of ")

    # Build realism suffix (anti-painted-background)
    realism_suffix = ", photographed on location, natural ambient lighting, authentic environment" if realism else ""

    logger.info(
        "Generating prompts",
        count=count,
        style=style,
        location=location,
        caption_category=category,
        preserve_identity=preserve_identity,
        framing=framing,
        realism=realism,
    )

    prompt = PROMPT_GENERATION_TEMPLATE.format(
        count=count,
        location_instructions=location_instructions,
        style_instructions=style_instructions,
        caption_instructions=caption_instructions,
        identity_text=identity_text,
        framing_prefix=framing_prefix,
        realism_suffix=realism_suffix,
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

    logger.info("Generated prompts", requested=count, actual=len(clean_prompts), exaggerated_bust=exaggerated_bust, preserve_identity=preserve_identity, framing=framing, realism=realism)

    return clean_prompts
