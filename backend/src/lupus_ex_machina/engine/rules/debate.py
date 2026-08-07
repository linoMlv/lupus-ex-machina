"""What the floor costs, and what it is worth (D-002).

Held in configuration rather than in the code because D-002 is explicit that
these values are indicative and will have to be calibrated by playing.
"""

from pydantic import BaseModel, ConfigDict, Field


class DebateOptions(BaseModel):
    """What the floor costs, and what it is worth (D-002).

    Held in configuration rather than in the code because D-002 is explicit that
    these values are indicative and will have to be calibrated by playing.
    """

    model_config = ConfigDict(frozen=True)

    addressed_bonus: int = Field(
        default=25,
        ge=0,
        description="Bonus d'enchère pour un joueur que le dernier orateur interpellait.",
    )
    accused_bonus: int = Field(
        default=40,
        ge=0,
        description="Bonus d'enchère pour un joueur que le dernier orateur accusait.",
    )
    """Worth more than merely being talked to, and D-002 already said so: an
    answer owed to the whole table is more pressing than one owed to a person."""

    recency_penalty: int = Field(
        default=30,
        ge=0,
        description="Malus d'enchère pour celui qui vient de parler, qui s'estompe ensuite.",
    )
    """The anti-monopoly of D-002, and what makes a debate move: the surest way
    to lose the next auction is to have won the last one."""

    recency_window: int = Field(
        default=3,
        ge=1,
        description="Nombre de tours au bout desquels le malus de récence est retombé à zéro.",
    )
    word_quota: int = Field(
        default=300,
        ge=0,
        description=(
            "Nombre de mots qu'un joueur peut dépenser dans la journée avant d'être pénalisé."
        ),
    )
    quota_penalty: int = Field(
        default=50,
        ge=0,
        description="Malus d'enchère appliqué une fois le quota de mots du jour dépassé.",
    )
    """Answers the verbosity of language models with something other than a
    truncation: a player who has said a great deal has to want the floor markedly
    more than one who has been listening."""

    minimum_urgency: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Urgence en dessous de laquelle une enchère n'emporte pas la parole.",
    )
    """Zero is today's behaviour exactly, and that is deliberate: a rule of the
    game is not created in a jalon about configuration. Above zero, a round where
    nobody bids hard enough is a debate that has run out (D-060)."""

    waiting_allowed: bool = Field(
        default=True,
        description="Un joueur peut ne rien faire de son tour : ni parler, ni voter.",
    )
    """D-048 makes waiting legal, and strategically sound. Turned off, a table
    can no longer stall — at the price of the silence that says something."""

    turns_per_player_per_day: int = Field(
        default=5,
        ge=1,
        description="Nombre maximal de prises de parole par joueur et par journée.",
    )
    """A ceiling on model calls (GL-7), not a rule: a debate is meant to end when
    the last player votes (D-013), or when nobody has anything left to say."""

    speech_word_limit: int = Field(
        default=50,
        ge=1,
        description="Nombre maximal de mots d'une prise de parole.",
    )
    analysis_word_limit: int = Field(
        default=40,
        ge=1,
        description="Nombre maximal de mots d'une analyse privée.",
    )
    notebook_word_limit: int = Field(
        default=20,
        ge=1,
        description="Nombre maximal de mots d'une note de carnet.",
    )
    notebook_note_limit: int = Field(
        default=30,
        ge=1,
        description="Nombre maximal de notes qu'un carnet peut contenir.",
    )
    """Capped so its author has to arbitrate what is worth keeping (D-005). The
    engine holds the cap: one asked for in a prompt is one a model talks past."""
