import uuid
from dataclasses import dataclass

@dataclass
class Verse:
    num: int
    text: str


@dataclass
class Card:
    """A single reference/body verse card datum."""
    title: str                               # Combined text-reference for verse as entered by user
    verses: list[Verse]                      # The actual verses 
    uuid: str                                # Deletion key
    options: dict[str, object]               # Optional per-card typesetting options

    def __init__(self, title: str, verses: list[Verse], **options):
        self.title = title
        self.verses = verses
        self.uuid = str(uuid.uuid4())
        self.options = options.copy()

    def get_verse(self, num: int) -> Verse:
        for v in self.verses:
            if v.num == num:
                return v
        raise KeyError(num)

