"""How the night is run: the wake order, and what the pack weighs with."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lupus_ex_machina.engine.roles import ROLES, RoleName


class NightOptions(BaseModel):
    """How the night is run."""

    model_config = ConfigDict(frozen=True)

    require_werewolf_target: bool = Field(
        default=False,
        description="La meute doit repartir avec une victime ; à défaut, elle est tirée au sort.",
    )
    """False by default: the rules do not force a designation, and a game that
    does not progress is an admitted state rather than a bug (D-078)."""

    priority_budget: int = Field(
        default=100,
        ge=1,
        description="Points qu'un loup répartit entre les proies pour peser sur la désignation.",
    )
    """A ceiling rather than a quota (D-008): spending less is legal, and costs
    influence."""

    hold_a_runoff_on_a_tie: bool = Field(
        default=True,
        description=(
            "Une égalité entre proies rouvre la désignation une fois, entre les seules ex æquo."
        ),
    )
    wake_order: tuple[RoleName, ...] = Field(
        default=(RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH),
        description="Ordre dans lequel la nuit appelle les rôles.",
    )
    """A sequence rather than ranks: the order *is* the position, so there is no
    numbering to keep in agreement with itself. The registry no longer holds one
    (D-010) — two places giving the rank end up disagreeing."""

    @model_validator(mode="after")
    def _calls_every_role_that_wakes_exactly_once(self) -> Self:
        """Refuse an order that leaves a role out, or calls one twice.

        A role that acts at night and is never called would hold a power the
        game never offers it — an incoherent table rather than a variant.
        """
        called = list(self.wake_order)
        if len(set(called)) != len(called):
            raise ValueError("Un rôle ne peut être appelé qu'une fois dans la nuit")

        expected = {role for role, declared in ROLES.items() if declared.wakes_at_night}
        if set(called) != expected:
            missing = sorted(expected - set(called))
            extra = sorted(set(called) - expected)
            raise ValueError(
                f"L'ordre de réveil doit appeler exactement les rôles qui se réveillent "
                f"(manquants : {missing}, en trop : {extra})"
            )
        return self

    @model_validator(mode="after")
    def _wakes_the_witch_after_the_pack(self) -> Self:
        """Refuse a night that shows the witch a prey nobody has chosen yet.

        She is told whom the pack took and may pour her potion of life on them
        (D-029). Woken first, she would be asked to answer a question that has
        not been put — which is not a variant of the rules but a broken one.
        """
        called = list(self.wake_order)
        if called.index(RoleName.WITCH) < called.index(RoleName.WEREWOLF):
            raise ValueError(
                "La sorcière voit la proie de la meute : elle est réveillée après elle"
            )
        return self
