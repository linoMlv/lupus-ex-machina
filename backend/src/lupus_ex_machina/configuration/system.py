"""Technical settings that belong to nobody's rules (D-047, D-063, D-066).

These are in the catalogue at the same title as the rules of the game (D-069),
and they are the ones most easily forgotten because no player ever sees them.

The round budget of the runner is deliberately *not* here. D-078 is explicit:
it exists to turn a hypothetical deadlock into a loud failure rather than a
hang, and it must never become something a game can be set to.

Read by J7 and J8.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SystemOptions(BaseModel):
    """Context, rate limiting, and record keeping."""

    model_config = ConfigDict(frozen=True)

    context_windows: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Fenêtre de contexte réelle de chaque modèle, en jetons. "
            "Un modèle absent n'est jamais compacté."
        ),
    )
    """Declared per model rather than assumed (D-063): a whole game fits in about
    fifteen thousand tokens, so compaction should never trigger in V1 — but the
    mechanism stays correct if the word limits or the table size change."""

    context_margin: float = Field(
        default=0.8,
        gt=0.0,
        le=1.0,
        description="Part de la fenêtre de contexte utilisable avant de déclencher la compaction.",
    )
    backoff_first_delay_seconds: float = Field(
        default=1.0,
        gt=0.0,
        description="Première attente après un refus pour cause de débit dépassé.",
    )
    """Short on purpose (D-066): a long first step empties the display buffer and
    the scene freezes without explanation."""

    backoff_maximum_delay_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Attente maximale entre deux tentatives, une fois le doublement arrêté.",
    )
    record_journal_to: Path | None = Field(
        default=None,
        description="Fichier où écrire le journal de la partie. Vide, il reste en mémoire.",
    )
