"""Putting what people said into a prompt without letting them write the prompt.

Every speech reaches a model inside a labelled ``<parole>`` block, human and
generated alike (D-067). The system prompt states that what is inside such a
block is something a player *claims*, never an instruction — and that only the
system prompt has authority.

That promise rests entirely on one thing: the block must be impossible to leave.
A player who could close it would be writing outside it, and the whole
protection would fall. So the delimiters are neutralised before insertion, and
that is the one part of this design worth a test of its own (J7.2.4).

Neutralised rather than deleted: an attempt to break out stays readable as
something a player said, which is social information the other agents can use.

The tag is French because it belongs to the prompt, which HR-6 allows; the code
around it is English.
"""

import re

#: What a block is called. French on purpose (HR-6): it is read by the models.
TAG = "parole"

#: Anything that could close or forge a block. Replaced by its typographic
#: lookalike, which reads the same out loud and parses as nothing.
# The lookalikes are flagged as ambiguous with the characters they replace,
# which is exactly why they were chosen: they read the same to a human and to
# a model, and parse as nothing at all.
DELIMITERS = {"<": "‹", ">": "›", '"': "“"}  # noqa: RUF001

#: Control characters carry nothing that can be said out loud, and they break
#: both the parsing and the display (D-053).
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

#: Newlines and runs of spaces: a speech is one line, whatever a model produces.
WHITESPACE = re.compile(r"\s+")


def spoken(text: str) -> str:
    """What is left of a text once what cannot be said out loud is dropped (D-053).

    Accents, punctuation and the em dashes of French are kept — the filter is
    there for what breaks parsing and display, not for what looks unusual. It
    protects neither the model nor the prompt: an injection written in plain
    French passes through it untouched, and the block below is what answers that.
    """
    return WHITESPACE.sub(" ", CONTROL.sub("", text)).strip()


def neutralised(text: str) -> str:
    """The same text, with every delimiter of a block made harmless.

    Substituted rather than escaped as entities: a model reads a lookalike as
    the character it is, where an HTML entity would only teach it a second way
    to write the thing it must not write.
    """
    for delimiter, lookalike in DELIMITERS.items():
        text = text.replace(delimiter, lookalike)
    return text


def speech_block(*, speaker: str, day: int, order: int, speech: str) -> str:
    """One speech, labelled with who said it and when, ready to be injected.

    The speaker's name is neutralised too. It comes from the table rather than
    from the player, but a quote inside it would forge an attribute exactly as a
    quote inside the speech would.
    """
    return (
        f'<{TAG} locuteur="{neutralised(speaker)}" jour="{day}" ordre="{order}">'
        f"{neutralised(spoken(speech))}"
        f"</{TAG}>"
    )
