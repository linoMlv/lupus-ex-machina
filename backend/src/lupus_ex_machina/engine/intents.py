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

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleActionName


class IntentKind(StrEnum):
    """Discriminator of the intent union."""

    SPEAK = "speak"
    VOTE = "vote"
    WAIT = "wait"
    ROLE_ACTION = "role_action"
    SHARE_PRIORITY = "share_priority"


class _BaseIntent(BaseModel):
    """Shared configuration of every intent."""

    model_config = ConfigDict(frozen=True)


class Speak(_BaseIntent):
    """Take the floor publicly."""

    kind: Literal[IntentKind.SPEAK] = IntentKind.SPEAK
    speech: str = Field(min_length=1, description="Ce que tu dis publiquement.")


class CastVote(_BaseIntent):
    """Vote, which also gives up the right to speak for the round (D-013)."""

    kind: Literal[IntentKind.VOTE] = IntentKind.VOTE
    target: PlayerId | None = Field(
        default=None,
        description="Le joueur que tu veux éliminer, ou rien pour voter blanc.",
    )

    @property
    def is_blank(self) -> bool:
        """Whether the voter skips rather than naming someone (D-027)."""
        return self.target is None


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


Intent = Annotated[
    Speak | CastVote | Wait | RoleAction | SharePriority, Field(discriminator="kind")
]
