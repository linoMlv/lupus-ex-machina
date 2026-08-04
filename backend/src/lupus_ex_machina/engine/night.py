"""The night, from who is woken to what it all comes to.

Two rules shape this module.

Powers are **collected, then resolved together** (D-006). Applying each as it is
played would make the witch incoherent — she has to see a victim the pack has
*designated*, not one who is already dead — and would make every future
interaction between roles a question of who happened to be woken first.

The pack designates **by weight** (D-008). A tie is settled by a silent runoff
restricted to the prey that tied, and a second tie takes nobody (D-050, D-062);
a night without a victim is a normal outcome of the rules, not a failure to
handle (D-078).
"""

from pydantic import BaseModel, ConfigDict

from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.priority import tally
from lupus_ex_machina.engine.roles import ROLES, RoleActionName, RoleName, Team
from lupus_ex_machina.engine.state import GameState


def night_callers(state: GameState) -> tuple[Player, ...]:
    """The living players the night wakes, in the order it wakes them.

    Ordered by the rank their role declares, then by seat, so two runs of the
    same game call the same people in the same order.
    """
    return tuple(
        sorted(
            (player for player in state.living if ROLES[player.role].wakes_at_night),
            key=lambda player: (ROLES[player.role].wake_order or 0, player.seat),
        )
    )


def prey_of(state: GameState) -> tuple[Player, ...]:
    """The living players the pack may take: everyone outside it.

    Narrowed to the ex aequo while a runoff is open (D-062).
    """
    hunted = tuple(player for player in state.living if player.team is not Team.WEREWOLVES)
    if not state.runoff_targets:
        return hunted
    return tuple(player for player in hunted if player.id in state.runoff_targets)


def tied_prey(state: GameState) -> tuple[PlayerId, ...]:
    """The prey a runoff would be held between, empty when there is nothing to break.

    A pack that wants nobody has no tie: it simply did not pick, which is a
    settled answer rather than an undecided one.
    """
    counted = tally(state.priority_shares)
    return () if counted.designated is not None else counted.leaders


def designated_prey(state: GameState, *, policy: InformationPolicy) -> PlayerId | None:
    """The prey the pack ends up taking, or ``None`` when it takes nobody."""
    settled = tally(state.priority_shares).designated
    if settled is not None:
        return settled
    if not policy.require_werewolf_target:
        return None

    return _forced_choice(state)


def _forced_choice(state: GameState) -> PlayerId | None:
    """Pick for a pack that must designate someone but did not (D-078).

    Taken from the prey it was torn between, or from every prey when it named
    none, and settled by seat so a game replays identically (D-040). A weighted
    draw was the other candidate in D-008; it would need the generator here, and
    a pure resolution is worth more than the variety.
    """
    torn_between = set(tied_prey(state))
    candidates = [
        player for player in prey_of(state) if not torn_between or player.id in torn_between
    ]
    if not candidates:
        return None

    return min(candidates, key=lambda player: player.seat).id


def resolve_night(
    state: GameState, *, policy: InformationPolicy
) -> tuple[GameState, PlayerId | None]:
    """Close the night: apply what it decided, and clear what it collected."""
    victim = designated_prey(state, policy=policy)
    killed = state if victim is None else state.with_players_killed([victim])
    return killed.cleared_of_round_choices(), victim


class Revelation(BaseModel):
    """What a seer is told about the player she looked at (D-031).

    Exactly one of the two is filled in, decided by the configuration: either
    the role itself, or the single bit that matters to the village. Modelling
    both as optional and validating the pair keeps the two settings one type,
    which is what the announcement and the private finding both carry.
    """

    model_config = ConfigDict(frozen=True)

    role: RoleName | None = None
    is_werewolf: bool | None = None

    @classmethod
    def of(cls, role: RoleName, *, in_full: bool) -> "Revelation":
        """Read a role the way the configuration says the seer reads it."""
        if in_full:
            return cls(role=role)
        return cls(is_werewolf=ROLES[role].team is Team.WEREWOLVES)


class Finding(BaseModel):
    """What one seer learned tonight, and about whom."""

    model_config = ConfigDict(frozen=True)

    seer: PlayerId
    target: PlayerId
    revelation: Revelation


def findings_of(state: GameState, *, policy: InformationPolicy) -> tuple[Finding, ...]:
    """What the seers of this table learned tonight.

    Delivered with the rest of the night rather than the moment she looks: the
    answer does not depend on anything else that happens, so nothing is lost,
    and the night keeps a single moment where information is handed out (D-006).
    """
    return tuple(
        Finding(
            seer=choice.actor,
            target=choice.target,
            revelation=Revelation.of(
                state.player(choice.target).role, in_full=policy.seer_learns_exact_role
            ),
        )
        for choice in state.night_choices
        if choice.action is RoleActionName.INSPECT
    )
