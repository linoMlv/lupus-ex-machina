"""The shapes a model is asked to answer in (D-004, D-035).

Flat on purpose, where the engine's own intents are a discriminated union. A
model fills in fields; it does not pick a variant and then fill in the fields of
that variant, and a schema that asked it to would spend a share of every game on
answers that parse and mean nothing. The engine's union is rebuilt from these
answers, and the validator remains the last authority on what is legal (D-001).

Players are named, never identified. A model only ever sees the names spoken at
the table, so those are what it answers with — an identifier in a prompt would
be a leak of the engine into the fiction (revue de J2).

Field names are English because they are code; every description is French,
because the JSON schema carries them to the model (HR-6).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.turn import NotebookOperation


class Emote(StrEnum):
    """What a player's body says while they speak (D-075, D-076).

    A closed list rather than free text: it drives an animation, and a value
    outside the catalogue would be one the scene cannot play.
    """

    NEUTRAL = "neutral"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    INSISTENCE = "insistence"
    WITHDRAWAL = "withdrawal"


class _Answer(BaseModel):
    """Shared configuration of everything a model fills in.

    Closed to unknown fields: the schema handed over says
    ``additionalProperties: false`` (D-035), and what the schema promises the
    type has to keep.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class BidAnswer(_Answer):
    """How badly a player wants the floor, and what they would say (D-002).

    The cheap call of the project, made once per player per turn at the floor:
    two fields and nothing else (GL-7).
    """

    urgency: int = Field(
        ge=0,
        le=100,
        description="À quel point tu veux prendre la parole maintenant, de 0 à 100.",
    )
    intention: str = Field(
        min_length=1,
        description="En quelques mots, ce que tu dirais si on te donnait la parole.",
    )


class PriorityAnswer(_Answer):
    """Points one wolf puts on one prey (D-008)."""

    target: str = Field(min_length=1, description="Le nom du joueur concerné.")
    points: int = Field(
        description="Positif pour le désigner, négatif pour l'écarter. Les deux coûtent."
    )


class TurnAnswer(_Answer):
    """A whole turn: what a player thought, wrote, said and decided (D-004).

    One answer rather than four calls, because a turn is a single thought and
    every round trip costs (GL-7).
    """

    reasoning: str = Field(
        min_length=1,
        description="Ton analyse de la situation, pour toi seul. Personne ne l'entend.",
    )
    notebook: tuple[NotebookOperation, ...] = Field(
        default=(), description="Ce que tu écris dans ton carnet privé, ou rien."
    )
    emote: Emote = Field(
        default=Emote.NEUTRAL, description="Ce que ton attitude montre pendant que tu parles."
    )
    speech: str | None = Field(
        default=None, description="Ce que tu dis publiquement, ou rien si tu ne parles pas."
    )
    addressed: str | None = Field(
        default=None, description="Le nom du joueur à qui tu t'adresses, si tu t'adresses à un."
    )
    accused: str | None = Field(
        default=None, description="Le nom du joueur que tu accuses d'être un loup, si tu accuses."
    )
    vote: str | None = Field(
        default=None, description="Le nom du joueur contre qui tu votes, si tu votes contre un."
    )
    votes_blank: bool = Field(
        default=False,
        description="Vrai pour voter blanc. Voter met fin à ta parole pour la journée.",
    )
    action: RoleActionName | None = Field(
        default=None, description="Le pouvoir que tu utilises, si tu en utilises un."
    )
    target: str | None = Field(default=None, description="Le nom du joueur que ton pouvoir vise.")
    priorities: tuple[PriorityAnswer, ...] = Field(
        default=(),
        description="Ta répartition de points sur les proies, si tu es un loup et que la nuit "
        "te le demande.",
    )


class ReflectionAnswer(_Answer):
    """What a player makes of a round that has just closed (D-086).

    Nothing to decide, so nothing but a thought and a notebook: the floor closed
    with the vote, and this is what the count and the resolution taught.
    """

    reasoning: str = Field(min_length=1, description="Ce que ce tour t'a appris, pour toi seul.")
    notebook: tuple[NotebookOperation, ...] = Field(
        default=(), description="Ce que tu écris dans ton carnet privé, ou rien."
    )
