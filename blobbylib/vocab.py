"""Fixed tag vocabulary and collection registry for the Blobby backfill pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tag vocabulary – about 60 lowercase single words or hyphenated words
# ---------------------------------------------------------------------------

_TAG_LIST: list[str] = [
    # emotions
    "happy", "sad", "angry", "scared", "sleepy", "surprised",
    "love", "laughing", "thinking", "confused",
    # reactions
    "yes", "no", "thanks", "hype", "fire", "pray", "salute",
    "wave", "clap", "thumbs-up", "high-five",
    # objects
    "hat", "glasses", "crown", "helmet", "coffee", "book",
    "laptop", "phone", "flag", "trophy", "gift", "balloon",
    # places
    "city", "beach", "mountain", "space", "office",
    # holidays
    "halloween", "christmas", "thanksgiving", "new-year",
    "st-patricks", "easter", "pride",
    # sports
    "hockey", "basketball", "baseball", "soccer", "surfing",
    "skiing", "cycling",
    # animals
    "cat", "dog", "duck", "bear", "penguin", "koala",
    "kangaroo", "dinosaur",
    # food
    "pizza", "burrito", "hotdog", "cake", "cookie", "donut",
    "beer", "wine", "boba",
    # costume
    "pirate", "captain", "chef", "doctor", "knight",
    "superhero", "wizard", "elf", "ghost", "zombie",
    "vampire", "werewolf",
    # omni product words
    "dbt", "snowflake", "databricks", "sql", "dashboard",
    "data", "ai", "agent",
    # style
    "animated", "pixel", "retro",
]


# ---------------------------------------------------------------------------
# Collection registry – slugs + one-line descriptions (from collections.yaml)
# ---------------------------------------------------------------------------

_COLLECTION_INFO: list[tuple[str, str]] = [
    ("core",         "The official master Blobbies, hand-picked only, never assigned by the model."),
    ("holidays",     "Anything tied to a holiday or season, Halloween monsters included."),
    ("pop-culture",  "Recognizable franchise characters, celebrities, memes, zodiac signs."),
    ("costumes",     "Generic professions and outfits with no franchise (pirate, captain, doctor, chef, builder, showgirl)."),
    ("cities",       "Places, flags, landmarks, local food that stands for a place."),
    ("partners",     "dbt, Snowflake, Databricks, MotherDuck, Google Sheets, and other software or brands."),
    ("food",         "Food and drink."),
    ("animals",      "Animals."),
    ("sports",       "Sports."),
    ("omni",         "AI, agents, dashboards, SQL, data, Omni values."),
    ("reactions",    "Emotions, gestures, and sign-holding words only."),
    ("objects",      "A Blobby doing or being a thing that fits nowhere above (balloon, cube, rocket, typing, vacation, on a date)."),
    ("unsorted",     "Holding pen for items awaiting backfill."),
]


@dataclass(frozen=True)
class Vocab:
    """Holds the fixed tag list and collection registry for the backfill prompt."""

    tags: frozenset[str]
    collections: dict[str, str]  # slug -> one-line description

    def valid_tags(self, candidates: list[str]) -> list[str]:
        """Return only the candidates that exist in the tag list, preserving order."""
        return [t for t in candidates if t in self.tags]

    def valid_collection(self, slug: str) -> str:
        """Return slug if it is a known collection, else 'unsorted'."""
        return slug if slug in self.collections else "unsorted"


VOCAB: Vocab = Vocab(
    tags=frozenset(_TAG_LIST),
    collections=dict(_COLLECTION_INFO),
)
