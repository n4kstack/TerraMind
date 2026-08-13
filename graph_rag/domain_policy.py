"""
Query domain policy
===================
TerraMind has two assistants — AugNosis (knowledge-graph Q&A) and the
post-diagnosis chatbot — and both exist to answer agricultural questions.
Nothing else.

Both leaked, in different ways:

* AugNosis classified a query as non-agricultural and then handed it to a
  prompt beginning "You are a helpful assistant", so "write a loop in python"
  came back as a full Python tutorial.
* The chatbot gated on a keyword blocklist, which can only ever catch the
  off-topic subjects somebody thought to enumerate ahead of time.

This module inverts the default. A query is answered only when it is
recognisably about agriculture, or is ordinary conversational courtesy
("hello", "thanks", "sorry"). Everything else is declined. One classifier is
shared by both assistants deliberately: two copies drift apart, and the drift
stays invisible until something like the Python tutorial reaches users.
"""

from __future__ import annotations

import re
from typing import Literal

QueryDomain = Literal["agriculture", "smalltalk", "off_topic"]

# ── Off-topic signals ────────────────────────────────────────────────────────
# Subjects a farming assistant has no business answering. Kept deliberately
# unambiguous: every term here would be surprising in a genuine field question.
_OFF_TOPIC = re.compile(
    r"\b("
    r"python|javascript|typescript|java|c\+\+|c#|golang|rust\s+lang|sql|html|css|"
    r"code|coding|program(?:ming|me)?|script|function|algorithm|api|regex|"
    r"compiler|debug|repo(?:sitory)?|github|frontend|backend|database|"
    r"stock|bitcoin|crypto|forex|nifty|sensex|share\s+market|trading|"
    r"president|prime\s+minister|election|parliament|politic(?:s|al)|"
    r"movie|film|celebrity|actor|actress|cricket|football|basketball|ipl|fifa|"
    r"song|album|lyrics|video\s+game|"
    r"recipe|restaurant|hotel|"
    r"essay|homework|assignment|poem|haiku|"
    r"tell\s+me\s+a\s+joke"
    r")\b",
    re.IGNORECASE,
)

# ── Conversational courtesy ──────────────────────────────────────────────────
# Allowed, but answered with a short scoped reply rather than a real answer.
_GREETING = re.compile(r"\b(hi|hey|hello|hola|namaste|namaskar|good\s+(morning|afternoon|evening))\b", re.I)
_THANKS = re.compile(r"\b(thanks|thank\s+you|thankyou|dhanyavad|shukriya|appreciate\s+it)\b", re.I)
_APOLOGY = re.compile(r"\b(sorry|my\s+bad|apolog(?:y|ies|ise|ize))\b", re.I)
_HOW_ARE_YOU = re.compile(r"\b(how\s+are\s+you|how'?s\s+it\s+going|what'?s\s+up|are\s+you\s+(?:there|ok|okay))\b", re.I)
_WHO_ARE_YOU = re.compile(
    r"\b(who\s+are\s+you|what\s+are\s+you|your\s+name|what\s+can\s+you\s+do|"
    r"how\s+(?:can|do)\s+you\s+help|what\s+do\s+you\s+do)\b",
    re.I,
)
_FAREWELL = re.compile(r"\b(bye|goodbye|see\s+you|good\s?night|alvida)\b", re.I)
_ACK = re.compile(r"^(ok(ay)?|k|cool|nice|great|got\s+it|fine|yes|no|yeah|nope|hmm+)[.!]*$", re.I)

_SMALLTALK = (_GREETING, _THANKS, _APOLOGY, _HOW_ARE_YOU, _WHO_ARE_YOU, _FAREWELL, _ACK)

# Courtesy is only courtesy when it is the whole message. "hi, write me a
# python loop" is a coding request wearing a greeting.
_SMALLTALK_MAX_WORDS = 7

# ── Agriculture vocabulary ────────────────────────────────────────────────────
# Broad on purpose. With the default flipped to deny, anything genuinely
# agricultural that is missing here becomes a false refusal — a worse failure
# for a farmer mid-season than the occasional over-broad match.
_AGRI_TERMS = [
    # Domain and practice
    "agricultur", "agronom", "agri", "farm", "farmer", "farming", "cultivat",
    "horticultur", "plantation", "orchard", "nursery", "cropping", "kisan",
    # Crops — cereals, pulses, oilseeds, cash crops
    "crop", "rice", "paddy", "wheat", "maize", "corn", "barley", "millet",
    "bajra", "jowar", "sorghum", "ragi", "oat", "pulse", "lentil", "chickpea",
    "gram", "pigeon\\s*pea", "arhar", "tur", "moong", "urad", "soybean",
    "groundnut", "peanut", "mustard", "sesame", "sunflower", "castor",
    "linseed", "sugarcane", "cotton", "jute", "tobacco", "tea", "coffee",
    "rubber", "coconut", "arecanut", "cashew", "spice", "cardamom", "pepper",
    "turmeric", "ginger", "garlic", "chilli", "chili", "cumin", "coriander",
    # Fruit and vegetable
    "tomato", "potato", "onion", "brinjal", "eggplant", "okra", "ladyfinger",
    "cabbage", "cauliflower", "spinach", "carrot", "radish", "peas", "beans",
    "cucumber", "pumpkin", "gourd", "melon", "banana", "mango", "guava",
    "papaya", "pomegranate", "grape", "citrus", "lemon", "orange", "apple",
    "cherry", "peach", "strawberry", "cassava", "yam", "beet",
    # Plant anatomy and growth
    "leaf", "leaves", "stem", "root", "shoot", "seed", "seedling", "sapling",
    "germinat", "sowing", "sow", "transplant", "flower", "bloom", "pollinat",
    "fruit", "grain", "tiller", "canopy", "foliage", "vine", "tuber", "bulb",
    "graft", "prune", "harvest", "yield", "produce", "ripen", "maturity",
    # Soil, water, nutrition
    "soil", "loam", "clay", "silt", "sandy", "alluvial", "black\\s+soil",
    "ph\\b", "salinity", "alkalin", "acidic\\s+soil", "erosion", "tilth",
    "till", "plough", "plow", "harrow", "mulch", "compost", "manure", "dung",
    "vermicompost", "fertiliz", "fertilis", "urea", "npk", "nitrogen",
    "phosphor", "potash", "potassium", "micronutrient", "zinc", "boron",
    "irrigat", "drip", "sprinkler", "borewell", "canal", "watering",
    "waterlog", "drainage", "moisture", "drought", "rainfall", "monsoon",
    "kharif", "rabi", "zaid", "season", "weather", "frost", "humidity",
    # Pests, disease, protection
    "pest", "insect", "aphid", "thrip", "whitefly", "bollworm", "borer",
    "caterpillar", "larva", "mite", "nematode", "locust", "termite", "weevil",
    "hopper", "leafhopper", "mealybug", "armyworm", "fruit\\s*fly",
    "disease", "blight", "rust", "smut", "wilt", "mildew", "mosaic", "rot",
    "canker", "scab", "anthracnose", "fungus", "fungal", "bacteri", "viral",
    "virus", "pathogen", "infest", "infect", "lesion", "spot", "chlorosis",
    "necrosis", "yellowing", "stunt", "deficiency", "symptom", "diagnos",
    "pesticide", "insecticide", "fungicide", "herbicide", "weedicide",
    "spray", "dose", "dosage", "phi\\b", "residue", "biopestic", "neem",
    "weed", "weeding", "quarantine", "resistant\\s+variety",
    # Livestock and allied
    "livestock", "cattle", "buffalo", "cow", "goat", "sheep", "poultry",
    "chicken", "dairy", "fodder", "silage", "grazing", "veterinar",
    "apicultur", "beekeep", "aquacultur", "fishery", "sericultur",
    # Economics and policy, as farmers actually ask about them
    "mandi", "msp", "procurement", "subsid", "kcc", "crop\\s+insurance",
    "acre", "hectare", "bigha", "quintal", "market\\s+price", "storage",
    "warehouse", "cold\\s+chain", "post\\s*harvest", "tractor", "implement",
]

_AGRI = re.compile(r"\b(" + "|".join(_AGRI_TERMS) + r")", re.IGNORECASE)


def classify_query(text: str, *, has_domain_entities: bool = False) -> QueryDomain:
    """
    Decide whether a query may be answered.

    Parameters
    ----------
    text:
        The raw user query.
    has_domain_entities:
        Set when an upstream parser already resolved a crop, pest, disease,
        soil type or pesticide against the knowledge graph. That is a stronger
        signal than any word list, so it admits questions phrased entirely in
        vocabulary this module does not carry.

    Notes
    -----
    Off-topic wins over an agriculture match when a query somehow trips both
    ("write a python script for my farm"). A genuine field question rarely
    contains "bitcoin" or "parliament", so the cost of that ordering is an
    occasional invitation to rephrase; the cost of the reverse is answering
    programming questions under an agronomy banner, which is what shipped.
    """
    q = (text or "").strip()
    if not q:
        return "off_topic"

    if _OFF_TOPIC.search(q):
        return "off_topic"

    if has_domain_entities or _AGRI.search(q):
        return "agriculture"

    if len(q.split()) <= _SMALLTALK_MAX_WORDS and any(p.search(q) for p in _SMALLTALK):
        return "smalltalk"

    return "off_topic"


def refusal_message(assistant: str = "TerraMind") -> str:
    """Explain the boundary and show the way back, rather than just saying no."""
    return (
        f"That falls outside what {assistant} covers. I answer questions about "
        "farming — crops and varieties, pests and diseases, soil and nutrition, "
        "irrigation, weather and crop protection.\n\n"
        "Ask me something like *\"why are my tomato leaves curling?\"* or "
        "*\"when should I apply nitrogen to wheat?\"* and I'll help."
    )


def smalltalk_reply(text: str, assistant: str = "TerraMind") -> str:
    """
    Answer courtesy with courtesy, then point back at the domain.

    Deliberately canned rather than model-generated: routing pleasantries to a
    general-purpose prompt is exactly how the off-topic answers got out.
    """
    q = (text or "").strip()

    if _THANKS.search(q):
        return "You're welcome. Ask me anything else about your crop or field."
    if _APOLOGY.search(q):
        return "No need to apologise. What would you like to know about your crop?"
    if _FAREWELL.search(q):
        return "Goodbye, and good luck with the season."
    if _WHO_ARE_YOU.search(q):
        return (
            f"I'm {assistant}'s agricultural assistant. I answer questions about crops "
            "and varieties, pests and diseases, soil and nutrition, irrigation, weather "
            "and crop protection — grounded in an agricultural knowledge graph and the "
            "research literature.\n\nWhat's happening in your field?"
        )
    if _HOW_ARE_YOU.search(q):
        return "Doing well, thank you. What's happening in your field?"
    if _GREETING.search(q):
        return (
            f"Hello. I'm {assistant}'s agricultural assistant — ask me about a crop, "
            "a pest or disease you're seeing, soil and nutrition, or irrigation."
        )

    return "Understood. What would you like to know about your crop or field?"
