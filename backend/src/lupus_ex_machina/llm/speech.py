"""Cutting what a model produced down to what the rules allow (D-021, D-023).

Two operations, both deliberately dumb and both deterministic.

**Truncation** is applied by the engine rather than asked for in the prompt. A
model told to be brief is brief most of the time, and the times it is not are
exactly the times a bubble would run off the screen.

**Splitting into sentences** happens here rather than in the browser (D-023): a
game is replayed from its journal, so what is shown has to be the same on every
replay and on every screen.
"""

import re

#: What ends a sentence, kept with the sentence it ends.
SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def truncated(text: str, words: int) -> str:
    """The first so many words of a text, with an ellipsis when it was cut.

    Cut on words rather than on characters: half a word is a mistake a reader
    notices, and a model given a word budget answers in words.
    """
    said = text.split()
    if len(said) <= words:
        return text
    return " ".join(said[:words]) + "…"


def sentences(text: str) -> tuple[str, ...]:
    """A speech split the way it will be shown, one bubble per sentence (D-018).

    Deterministic and done on the server, so two replays of one game put the
    same words in the same bubbles.
    """
    return tuple(part for part in SENTENCE_END.split(text.strip()) if part)
