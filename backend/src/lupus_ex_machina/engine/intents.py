"""What an agent may ask the engine to do.

Agents never produce effects, only intents (D-001). The union is closed and
discriminated on ``kind``, which makes it directly usable as the structured
output schema of a language model in J7 — the engine and the model then speak
the same language, with no translation layer in between.

Field names are English because they are code; the values an agent fills in are
French, because they are content shown on screen or sent to a model (HR-6).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName


class IntentKind(StrEnum):
    """Discriminator of the intent union."""

    TAKE_TURN = "take_turn"
    WAIT = "wait"
    ROLE_ACTION = "role_action"
    SHARE_PRIORITY = "share_priority"


class _BaseIntent(BaseModel):
    """Shared configuration of every intent."""

    model_config = ConfigDict(frozen=True)


class Vote(BaseModel):
    """Whom a player names for elimination, or nobody (D-027)."""

    model_config = ConfigDict(frozen=True)

    target: PlayerId | None = Field(
        default=None,
        description="Le joueur que tu veux éliminer, ou rien pour voter blanc.",
    )

    @property
    def is_blank(self) -> bool:
        """Whether the voter skips rather than naming someone (D-027)."""
        return self.target is None


class TakeTurn(_BaseIntent):
    """What a player does with the turn they won (D-013, D-028).

    One intent with optional parts rather than three, because the rules give a
    turn three ways to go: speak and leave the round open, speak *and* vote —
    the last turn a player may speak in — or vote without a word. Three types
    would duplicate the validation and the recording of what is one move.

    Whom the speaker is talking to and whom they accuse are declared, not read
    out of their words: the auction pays for both (D-002), and digging them out
    of French prose would put a parser of French in the middle of the rules.
    """

    kind: Literal[IntentKind.TAKE_TURN] = IntentKind.TAKE_TURN
    speech: str | None = Field(
        default=None,
        min_length=1,
        description="Ce que tu dis publiquement, ou rien si tu prends la parole pour voter.",
    )
    addressed: PlayerId | None = Field(
        default=None,
        description="Le joueur à qui tu t'adresses, si tu t'adresses à quelqu'un en particulier.",
    )
    accused: PlayerId | None = Field(
        default=None,
        description="Le joueur que tu accuses d'être un loup-garou, si tu en accuses un.",
    )
    vote: Vote | None = Field(
        default=None,
        description="Ton vote, ou rien pour garder ton droit de parole ce tour-ci.",
    )

    @model_validator(mode="after")
    def _says_or_does_something(self) -> "TakeTurn":
        """A turn that neither speaks nor votes is :class:`Wait` under another name."""
        if self.speech is None and self.vote is None:
            raise ValueError("A turn either speaks, votes, or both")
        return self


class Wait(_BaseIntent):
    """Do nothing this turn, keeping the right to speak (D-048)."""

    kind: Literal[IntentKind.WAIT] = IntentKind.WAIT


class RoleAction(_BaseIntent):
    """Use the power of one's role on someone."""

    kind: Literal[IntentKind.ROLE_ACTION] = IntentKind.ROLE_ACTION
    action: RoleActionName
    target: PlayerId = Field(description="Le joueur que tu vises.")


#: How many points a wolf spreads over the prey in one night (D-008). A ceiling
#: rather than a quota: spending less is a legal choice, and it costs the wolf
#: influence over the tally, which is penalty enough.
PRIORITY_BUDGET = 100


class PriorityPoint(BaseModel):
    """Points a wolf puts on one prey. Negative means "anyone but them"."""

    model_config = ConfigDict(frozen=True)

    target: PlayerId = Field(description="Le joueur concerné.")
    points: int = Field(
        description=(
            "Points que tu mets sur ce joueur : positif pour le désigner, négatif pour l'écarter."
        )
    )


class SharePriority(_BaseIntent):
    """Spread the night's budget over the prey the pack might take (D-008).

    The pack does not vote for a single name: each wolf weighs the prey, and the
    designation is the tally. Abstaining is :class:`Wait` — an allocation is how
    a wolf states a preference, so it states at least one.
    """

    kind: Literal[IntentKind.SHARE_PRIORITY] = IntentKind.SHARE_PRIORITY
    allocations: tuple[PriorityPoint, ...] = Field(
        min_length=1,
        description=(
            f"Répartis jusqu'à {PRIORITY_BUDGET} points entre les proies, "
            "en comptant les points négatifs dans ton budget."
        ),
    )

    @property
    def spent(self) -> int:
        """Budget consumed. Pushing a prey away costs as much as pulling one in."""
        return sum(abs(allocation.points) for allocation in self.allocations)


Intent = Annotated[TakeTurn | Wait | RoleAction | SharePriority, Field(discriminator="kind")]
