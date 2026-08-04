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


Intent = Annotated[Speak | CastVote | Wait | RoleAction, Field(discriminator="kind")]
