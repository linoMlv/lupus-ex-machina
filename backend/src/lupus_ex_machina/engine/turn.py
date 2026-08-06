"""What a player hands back when the game asks them to play (D-083, D-004).

A turn is three things in one answer: what the player made of the situation,
what they wrote in their notebook, and what they decided to do. One answer
rather than three, because each one costs a model call and a turn is a single
thought (GL-7).

The engine collects all three. It is the only thing holding the journal, so an
agent recording its own facts would be an agent writing into the source of truth
(D-001) — and the separation between what is thought and what is said would rest
on the agent's good behaviour instead of on the code (D-004, GL-3).

Field names are English because they are code; the descriptions are French,
because they are read by the models (HR-6).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.intents import Intent


class NotebookOperationName(StrEnum):
    """The three things a player may do to their own notebook (D-005)."""

    ADD = "add"
    REVISE = "revise"
    DROP = "drop"


class _NotebookOperation(BaseModel):
    """Shared configuration of every operation on a notebook.

    Closed to unknown fields, like everything a model fills in: the JSON schema
    it is handed says ``additionalProperties: false``, and what the schema
    promises the type has to keep (D-035).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class AddNote(_NotebookOperation):
    """Write a new line in one's notebook."""

    operation: Literal[NotebookOperationName.ADD] = NotebookOperationName.ADD
    note: str = Field(min_length=1, description="Ce que tu veux retenir, en une phrase.")


class ReviseNote(_NotebookOperation):
    """Write a line over an older one, keeping its number."""

    operation: Literal[NotebookOperationName.REVISE] = NotebookOperationName.REVISE
    entry: int = Field(ge=0, description="Le numéro de la note que tu réécris.")
    note: str = Field(min_length=1, description="Ce que la note dit désormais.")


class DropNote(_NotebookOperation):
    """Strike a line out of one's notebook."""

    operation: Literal[NotebookOperationName.DROP] = NotebookOperationName.DROP
    entry: int = Field(ge=0, description="Le numéro de la note que tu supprimes.")


#: A union rather than one type with optional fields (D-035): a deletion carries
#: no text and an addition aims at no number, so the three shapes are three
#: types. What the model may leave out is then what the schema says it may.
NotebookOperation = Annotated[AddNote | ReviseNote | DropNote, Field(discriminator="operation")]


class Reflection(BaseModel):
    """What a player thought on their turn, and what they wrote down.

    Never public, whatever it contains: only speech reaches the shared
    transcript, and that is held by the types rather than by a prompt (D-004).
    """

    model_config = ConfigDict(frozen=True)

    reasoning: str | None = Field(
        default=None,
        min_length=1,
        description="Ton analyse de la situation, pour toi seul. Personne à la table ne l'entend.",
    )
    notebook: tuple[NotebookOperation, ...] = Field(
        default=(),
        description="Ce que tu écris dans ton carnet privé, ou rien.",
    )


class Turn(Reflection):
    """A reflection, and the move it led to."""

    intent: Intent = Field(description="Ce que tu décides de faire.")
