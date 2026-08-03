"""What the table is allowed to learn.

Options about information are not conditions scattered through the engine: each
one decides whether a fact is *produced*, and the audience of that fact is then
settled once, by the fact itself (D-009). This is where those decisions live.

J6 folds this into the single configuration schema of the project (D-068). It
stands alone here because J3 needs it and J6 is four jalons away — the shape is
what matters, and the shape is a small frozen record of decisions.
"""

from pydantic import BaseModel, ConfigDict


class InformationPolicy(BaseModel):
    """The information options of a game."""

    model_config = ConfigDict(frozen=True)

    reveal_role_on_death: bool = False
    """Whether the role of a player who just died is announced (D-072).

    Death itself is never configurable: it is always public. Only what the
    deceased was may stay hidden, which is what makes the ghosts of J10 safe to
    keep on stage. The default is the discreet one; classic Werewolf reveals.
    """
