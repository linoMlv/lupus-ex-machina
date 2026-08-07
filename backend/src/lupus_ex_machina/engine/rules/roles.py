"""What each role may do, where the rules leave a choice."""

from pydantic import BaseModel, ConfigDict, Field


class RoleOptions(BaseModel):
    """What each role may do, where the rules leave a choice."""

    model_config = ConfigDict(frozen=True)

    seer_learns_exact_role: bool = Field(
        default=True,
        description="La voyante lit le rôle exact. Sinon, elle apprend seulement « loup ou non ».",
    )
    """The two make very different games, and the richer one is taken: the poorer
    is a deliberate handicap rather than an obvious default (D-031)."""

    speaking_seer: bool = Field(
        default=False,
        description="La voyante annonce publiquement ce qu'elle a lu, sans dire sur qui.",
    )
    """Off by default: it hands the village a great deal, and the option exists
    to be turned on knowingly (D-031)."""

    witch_may_save_herself: bool = Field(
        default=True,
        description="La sorcière peut se soigner elle-même quand la meute l'a désignée.",
    )
    """D-029 says she may. Turned off, the potion of life still exists but never
    reaches its owner, which is the classic handicap some tables play with."""

    hunter_must_shoot: bool = Field(
        default=True,
        description="Le tir du chasseur est obligatoire : sans cible, le moteur vise pour lui.",
    )
    """On by default, and "non-renounceable" is taken literally: a rule the
    agents could quietly opt out of would not be a rule (D-055)."""
