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

    require_werewolf_target: bool = False
    """Whether the pack must leave the night with a victim (D-078).

    False by default: the rules do not force a designation, and a game that does
    not progress is an admitted state rather than a bug. When it is switched on,
    a pack that ties or names nobody has the choice made for it.
    """

    seer_learns_exact_role: bool = True
    """Whether the seer reads the role itself, or only "wolf or not" (D-031).

    The two make very different games, and neither is the obvious default; the
    richer one is taken, since the poorer is a deliberate handicap.
    """

    speaking_seer: bool = False
    """Whether the table hears what the seer found, without whom she looked at.

    Off by default: it hands the village a great deal, and the option exists to
    be turned on knowingly (D-031).
    """

    wake_witch_without_potions: bool = True
    """Whether the witch is woken once both her potions are gone (D-054).

    On by default. She learns whom the pack took, which she would learn at dawn
    anyway, so the information is worth only the round it is given in — and a
    table where she suddenly stops being called would say more than that.
    """

    hunter_must_shoot: bool = True
    """Whether the hunter's shot can be given up (D-055).

    On by default, and "non-renounceable" is taken literally: when a hunter will
    not aim, the engine aims for him. A rule the agents could quietly opt out of
    would not be a rule.
    """

    reveal_role_on_death: bool = False
    """Whether the role of a player who just died is announced (D-072).

    Death itself is never configurable: it is always public. Only what the
    deceased was may stay hidden, which is what makes the ghosts of J10 safe to
    keep on stage. The default is the discreet one; classic Werewolf reveals.
    """
