"""What a round leaves in the state: ballots, night choices, spent powers, speeches.

Small immutable records, each one the trace of a single move. They are kept
apart from :class:`~lupus_ex_machina.engine.state.GameState` itself because they
answer a different question: the state says what a game *is* right now, these
say what was played to get there.

None of them holds what was *said* or what a move came to. The words belong to
the journal, and the effects are settled by the resolution (D-006, D-040).
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName


class Ballot(BaseModel):
    """A vote cast during the day. A missing target is a blank vote (D-027)."""

    model_config = ConfigDict(frozen=True)

    voter: PlayerId
    target: PlayerId | None = None


class NightChoice(BaseModel):
    """A power a player used on someone during the night.

    The action travels with the target because the night holds several of them
    at once (D-006): they are collected as they are played and settled together
    at the end, so each one has to say what it was.
    """

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    action: RoleActionName
    target: PlayerId


class SpentPower(BaseModel):
    """A one-shot power its holder has now used up.

    Kept apart from the choices of a round, which are wiped as each round ends:
    a potion is spent for the rest of the game, not for the night (D-029).
    """

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    action: RoleActionName


class Speech(BaseModel):
    """One turn at the floor, as the round remembers it.

    The round keeps this because the auction that decides who speaks next is
    scored against it (D-002): who has just spoken, how much they have spoken,
    and whom they were talking to. What was actually *said* is not here — that
    belongs to the journal, which is where the transcript lives.

    Whom a speaker addressed and accused is declared by the speaker rather than
    read out of their words. Digging it out of French prose would put a parser
    of French in the middle of the rules, and would be exactly as reliable as
    that sounds.
    """

    model_config = ConfigDict(frozen=True)

    speaker: PlayerId
    words: int = Field(ge=0)
    addressed: PlayerId | None = None
    accused: PlayerId | None = None


class PriorityShare(BaseModel):
    """One wolf's spread of the night's budget over the prey (D-008)."""

    model_config = ConfigDict(frozen=True)

    actor: PlayerId
    allocations: tuple[PriorityPoint, ...]


def count_words(speech: str) -> int:
    """How much room a turn took up, in words.

    Lives here, with the field it fills in, so the runner and the replay of a
    journal cannot end up counting differently — the quota that reads it (D-002)
    would then depend on which of the two built the state.
    """
    return len(speech.split())
