"""How the game is shown, and at what pace (D-018, D-019, D-022, D-076).

Display is the dominant constraint on rhythm, not the latency of the models: a
bubble stays up half a second per word, and the floor is only released once the
last one has gone. That is also what hides the latency — while the scene plays,
the backend runs ahead.

Read by J10 and J11.
"""

from pydantic import BaseModel, ConfigDict, Field


class DisplayOptions(BaseModel):
    """Pace and effects of the staging."""

    model_config = ConfigDict(frozen=True)

    seconds_per_word: float = Field(
        default=0.5,
        gt=0.0,
        description="Durée d'affichage d'une bulle, par mot qu'elle contient.",
    )
    manual_bubble_advance: bool = Field(
        default=False,
        description="Les bulles n'avancent qu'au bouton « bulle suivante ».",
    )
    animations_enabled: bool = Field(
        default=True,
        description="Animations des personnages : parole, regards, émotes.",
    )
    effects_enabled: bool = Field(
        default=True,
        description="Effets de mise en scène : particules, sons, musiques, vignettage.",
    )
