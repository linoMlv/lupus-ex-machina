"""How a round is closed.

The blank vote is not an option here, and cannot be: Day 1 has no other way out
(D-032), so switching it off would describe a game with no legal move.
"""

from pydantic import BaseModel, ConfigDict, Field


class VoteOptions(BaseModel):
    """How a round is closed.

    The blank vote is not an option here, and cannot be: Day 1 has no other way
    out (D-032), so switching it off would describe a game with no legal move.
    """

    model_config = ConfigDict(frozen=True)

    hold_a_runoff_on_a_tie: bool = Field(
        default=True,
        description=(
            "Une égalité rouvre le vote une fois, sans débat, entre les seuls ex æquo. "
            "Sinon, une égalité n'élimine personne."
        ),
    )
    turns_before_forced_vote: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Nombre de prises de parole avant que le meneur de jeu ne déclenche le vote. "
            "Vide, le débat n'est pas écourté."
        ),
    )
