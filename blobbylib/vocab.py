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
    ("core",         "The foundational Blobby emojis that every Omni team member uses daily."),
    ("reactions",    "Blobby expressions and gestures built for Slack reactions and quick responses."),
    ("cities",       "City and region Blobbies celebrating the places the Omni team calls home."),
    ("partners",     "Blobby versions of Omni partner logos and tools in the data ecosystem."),
    ("holidays",     "Seasonal and holiday Blobbies for celebrations throughout the year."),
    ("characters",   "Blobby renditions of pop-culture characters, icons, and real-world figures."),
    ("food",         "Food and drink Blobbies capturing team favorites and regional classics."),
    ("animals",      "Animal Blobbies ranging from pets to wildlife to mythical creatures."),
    ("sports",       "Sports-themed Blobbies for teams, athletes, and game-day moments."),
    ("pop-culture",  "Blobby takes on movies, music, memes, and other cultural touchstones."),
    ("omni-values",  "Blobbies representing Omni's culture, values, and internal milestones."),
    ("animated",     "GIF animations that bring Blobby to life in Slack reactions and threads."),
    ("classic",      "Early-generation Blobbies preserved as a record of where it all started."),
    ("unsorted",     "Holding pen for Blobby items awaiting collection backfill."),
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
