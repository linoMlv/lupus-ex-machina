"""Building what a model is handed, out of what its player is allowed to know.

Two rules govern this module, and both are properties the tests hold rather than
intentions.

**Nothing enters a prompt that the projection did not carry.** The sources are
the :class:`~lupus_ex_machina.engine.views.PlayerView` and the *projected*
journal, and there is no third one. It is the likeliest leak in the whole
project (GL-3): the state is one attribute away at every line.

**The prose lives in files.** Prompts are rewritten constantly while a game is
being calibrated, and rewriting them must never mean touching code. What this
module holds is the assembly, not the words.

Everything a model reads is French; the code around it is English (HR-6).
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.events import Event
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.llm.pieces import (
    _last_word,
    _moment,
    _moves,
    _notebook,
    _role_brief,
    _table,
    _transcript,
    _what_they_know,
    template,
)


class Briefing(BaseModel):
    """What a seat is played with, beyond the rules its role gives it."""

    model_config = ConfigDict(frozen=True)

    personality: str = Field(
        min_length=1, description="Le tempérament du siège, injecté dans le prompt système."
    )


def system_prompt(view: PlayerView, *, briefing: Briefing) -> str:
    """The standing instructions of one seat: the rules, its role, its temperament."""
    return template("system").substitute(
        role=_role_brief(view.role),
        knowledge=_what_they_know(view),
        personality=briefing.personality,
    )


def turn_prompt(view: PlayerView, *, journal: Sequence[Event]) -> str:
    """Everything one seat needs to take its turn, and nothing else."""
    return template("turn").substitute(
        moment=_moment(view),
        table=_table(view),
        notebook=_notebook(view, journal),
        transcript=_transcript(view, journal),
        moves=_moves(view),
        analysis_words=view.limits.analysis_words,
        notebook_words=view.limits.notebook_words,
        speech_words=view.limits.speech_words,
    )


def bid_prompt(view: PlayerView, *, journal: Sequence[Event]) -> str:
    """The short question the floor is auctioned with (D-002, GL-7).

    Deliberately thin: this is the call a game makes most often, and handing it
    the whole transcript would cost as much as a generation.
    """
    return template("bid").substitute(moment=_moment(view), last=_last_word(view, journal))
