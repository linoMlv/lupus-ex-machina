"""What the outside is allowed to see of a provider (D-113).

Never the key. A form filled in with the stored secret "for convenience" is the
ordinary way a settings screen leaks one: the value travels in the response and
nobody notices, the screen showing dots.

Its own module for the reason the projection of J3 is one: *what is kept* and
*what is shown* are two things, and the second is where a leak would live.
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.providers.storage import Entry
from lupus_ex_machina.providers.vault import UnreadableSecretError, opened

#: How much of a key is shown back. Four characters is what a person recognises
#: their own key by, and what nobody can do anything with.
SHOWN_CHARACTERS = 4


class ProviderCard(BaseModel):
    """A provider as a settings screen may show it."""

    model_config = ConfigDict(frozen=True)

    name: str
    base_url: str
    key_ending: str | None = Field(
        default=None,
        description="The last characters of the key, to recognise it by.",
    )
    """Absent when the key cannot be read at all — the secret has changed since
    it was stored, or there is none. Said rather than left blank: a screen that
    showed nothing would look like a provider registered without a key, and the
    person would never think to enter it again."""


def card_of(name: str, entry: Entry, *, secret: str | None) -> ProviderCard:
    """That entry, with the key reduced to what it is recognised by.

    The ending comes from the key **in the clear**: the tail of the stored
    ciphertext is the tail of a base64 blob, which recognises nothing.

    An unreadable key gives a card without an ending rather than no card at all
    — one provider whose secret has moved on must not take the settings screen
    down with it.
    """
    return ProviderCard(
        name=name,
        base_url=entry.base_url,
        key_ending=_ending_of(entry.api_key, secret=secret),
    )


def _ending_of(stored: str, *, secret: str | None) -> str | None:
    """The last characters of that key, or nothing when it cannot be read."""
    if secret is None:
        return None
    try:
        return opened(stored, secret=secret)[-SHOWN_CHARACTERS:]
    except UnreadableSecretError:
        return None
