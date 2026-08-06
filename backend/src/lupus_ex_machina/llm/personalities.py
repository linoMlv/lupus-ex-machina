"""The sixteen temperaments a seat can be played with (D-058, D-064).

The best variety-to-effort ratio of the whole project, and a direct answer to
the two failure modes of a table of models: they agree with each other, and they
all write the same way (BS-001). Sixteen temperaments give a table where
somebody always pushes back.

They are not only a style. D-064 makes them **mechanical**: a temperament shifts
how badly its seat wants the floor, so an introvert genuinely speaks less rather
than merely saying it does. Only the E/I axis is wired to the auction — the two
other axes shape what is said, which is the prompt's business, and inventing a
mechanical effect for them would be arithmetic nobody could calibrate.

Hard-coded in the sense D-058 means it — nobody configures them — but the texts
live with the other prompts (J7.2.1): every one of them is injected into a
system prompt, and prompts are rewritten while a game is calibrated.
"""

import tomllib
from functools import cache

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.configuration.agents import Personality
from lupus_ex_machina.llm.prompting import PROMPTS

#: What being an extravert is worth in an auction, in points of urgency. Applied
#: symmetrically: an introvert bids that much less. Indicative and meant to be
#: calibrated by playing (D-002).
OUTSPOKEN_BIAS = 15


class Temperament(BaseModel):
    """One temperament: what it is called, how it plays, how badly it wants the floor."""

    model_config = ConfigDict(frozen=True)

    code: Personality
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    @property
    def urgency_bias(self) -> int:
        """What this temperament adds to, or takes from, its own urgency (D-064).

        Read off the first letter rather than stored: the axis *is* the code, and
        a second place holding it would be a second place to get it wrong.
        """
        return OUTSPOKEN_BIAS if self.code.value.startswith("E") else -OUTSPOKEN_BIAS


@cache
def personalities() -> dict[Personality, Temperament]:
    """The catalogue, read once from the file that holds its texts."""
    written = tomllib.loads((PROMPTS / "personalities.toml").read_text(encoding="utf-8"))
    return {
        Personality(code): Temperament(
            code=Personality(code), name=entry["name"], description=entry["description"]
        )
        for code, entry in written.items()
    }


def drawn_personality(seed: int) -> Personality:
    """A temperament for a seat nobody configured (D-064).

    Drawn from a number rather than at random so the same game deals the same
    table twice: everything a game does comes from one seed.
    """
    codes = sorted(personalities())
    return codes[seed % len(codes)]
