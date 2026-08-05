"""Which model, and which temperament, sits in each seat (D-058, D-064, D-077).

Two models per seat rather than one, because the quotas measured on 2026-08-03
differ by a factor of nearly two hundred between them (D-077): the auction is
the call a game makes most often, so it runs on a fast model, and generation on
a capable one. That separation is not a cost optimisation — it is what makes the
project viable on a free tier.

Personalities are a closed list on purpose (D-058). Sixteen temperaments give
immediate behavioural variety, which is the direct counter to the conformism and
the uniform style of language models, at the best variety-to-effort ratio of the
whole project.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Personality(StrEnum):
    """The sixteen MBTI codes a seat may be given (D-058).

    The code is an identifier, so it is written the way the world writes it. The
    name and the description handed to the model are French, and belong to the
    prompt that J7 builds, not here.
    """

    INTJ = "INTJ"
    INTP = "INTP"
    ENTJ = "ENTJ"
    ENTP = "ENTP"
    INFJ = "INFJ"
    INFP = "INFP"
    ENFJ = "ENFJ"
    ENFP = "ENFP"
    ISTJ = "ISTJ"
    ISFJ = "ISFJ"
    ESTJ = "ESTJ"
    ESFJ = "ESFJ"
    ISTP = "ISTP"
    ISFP = "ISFP"
    ESTP = "ESTP"
    ESFP = "ESFP"


class SeatProfile(BaseModel):
    """What one seat is played with."""

    model_config = ConfigDict(frozen=True)

    bidding_model: str = Field(
        default="ministral-3b-latest",
        min_length=1,
        description=(
            "Modèle qui répond aux enchères de parole. Il doit être rapide et à quota élevé."
        ),
    )
    generation_model: str = Field(
        default="mistral-small-latest",
        min_length=1,
        description="Modèle qui produit l'analyse, le carnet et la parole.",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Température du modèle de génération. Plus haut, plus imprévisible.",
    )
    top_p: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description="Troncature du noyau de probabilité du modèle de génération.",
    )
    personality: Personality | None = Field(
        default=None,
        description="Personnalité MBTI du siège. Vide, elle est tirée au sort (D-064).",
    )


class AgentOptions(BaseModel):
    """Which model plays which seat."""

    model_config = ConfigDict(frozen=True)

    default_profile: SeatProfile = Field(
        default_factory=SeatProfile,
        description="Profil appliqué à tout siège qui n'est pas configuré à part.",
    )
    seats: dict[int, SeatProfile] = Field(
        default_factory=dict,
        description="Profils par siège, pour créer des asymétries délibérées entre joueurs.",
    )

    def profile_of(self, seat: int) -> SeatProfile:
        """The profile that seat is played with, its own or the default one."""
        return self.seats.get(seat, self.default_profile)
