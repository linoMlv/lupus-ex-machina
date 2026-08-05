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
from lupus_ex_machina.engine.priority import tally
from lupus_ex_machina.engine.rng import Rng
from lupus_ex_machina.engine.roles import ONE_SHOT_ACTIONS, ROLES, RoleActionName, RoleName, Team
from lupus_ex_machina.engine.state import GameState


def night_callers(state: GameState) -> tuple[Player, ...]:
    """Every living player, in the order the night calls them (D-084).

    Everyone gets a turn, whether or not they hold a power: a turn is reading
    one's notebook and thinking the game over, and a villager who never did
    would start each dawn from nothing.

    The roles with a power come first, in the order the configuration gives them
    — that ordering is a rule (D-029) — and the rest follow by seat, which is a
    sweep rather than a ranking. Two runs of the same game call the same people
    in the same order.
    """
    order = state.rules.night.wake_order
    return tuple(sorted(state.living, key=lambda player: (_rank_of(player, order), player.seat)))


def _rank_of(player: Player, order: tuple[RoleName, ...]) -> int:
    """Where the night calls this player: at their role's rank, or after everyone."""
    if player.role not in order:
        return len(order)
    return order.index(player.role)


def potions_left_to(state: GameState, witch: PlayerId) -> frozenset[RoleActionName]:
    """The potions that witch has not drunk yet. Each one works once (D-029)."""
    return frozenset(
        action for action in ROLES[RoleName.WITCH].actions if not state.has_spent(witch, action)
    )


def victim_seen_by_the_witch(state: GameState) -> PlayerId | None:
    """Whom the pack has settled on, which is what the witch is shown (D-029).

    She is woken after it precisely so this has an answer, and she sees a prey
    that has been *designated* rather than one already dead — the whole reason
    the night resolves in one go (D-006).
    """
    return designated_prey(state)


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


def designated_prey(state: GameState) -> PlayerId | None:
    """The prey the pack ends up taking, or ``None`` when it takes nobody.

    Stays a pure reading of the state. A pack made to designate someone (D-078)
    has had its prey drawn before the night is resolved, and the answer is in
    the state: asking twice cannot give two victims.
    """
    settled = tally(state.priority_shares).designated
    if settled is not None:
        return settled
    if not state.rules.night.require_werewolf_target:
        return None

    return state.drawn_prey


def prey_drawn_by_lot(state: GameState, *, rng: Rng) -> PlayerId | None:
    """Draw a prey for a pack that must designate one but did not (D-081).

    Drawn from the prey it was torn between, or from every prey when it named
    none. ``None`` when there is nothing to settle: the pack chose, it is free
    to choose nobody, or nobody is left to take.

    The lot replaces the lowest seat this used to fall on, which was
    reproducible but always spared the same players. Reproducibility is kept by
    the generator being the game's own, seeded once (D-040).
    """
    if not state.rules.night.require_werewolf_target:
        return None
    if tally(state.priority_shares).designated is not None:
        return None

    torn_between = set(tied_prey(state))
    candidates = [
        player for player in prey_of(state) if not torn_between or player.id in torn_between
    ]
    if not candidates:
        return None

    return rng.choice(candidates).id


def powers_spent_tonight(state: GameState) -> tuple[tuple[PlayerId, RoleActionName], ...]:
    """The one-shot powers this night used up, in the order they were played.

    Read by the night, which spends them, and by whoever records the game, so
    the state and its journal cannot end up disagreeing about a potion.
    """
    return tuple(
        (choice.actor, choice.action)
        for choice in state.night_choices
        if choice.action in ONE_SHOT_ACTIONS
    )


def _potion_targets(state: GameState, action: RoleActionName) -> tuple[PlayerId, ...]:
    return tuple(choice.target for choice in state.night_choices if choice.action is action)


def resolve_night(state: GameState) -> tuple[GameState, tuple[PlayerId, ...]]:
    """Close the night, in the order the rules are written.

    Attack, then the potion that answers it, then the one that adds to it. The
    order is the specification: it reads aloud the way the rules do, and moving
    a line moves a rule.
    """
    taken = designated_prey(state)
    saved = _potion_targets(state, RoleActionName.HEAL)
    poisoned = _potion_targets(state, RoleActionName.POISON)

    victims = tuple(
        dict.fromkeys(([] if taken is None or taken in saved else [taken]) + list(poisoned))
    )

    settled = state.with_players_killed(victims)
    for actor, potion in powers_spent_tonight(state):
        settled = settled.with_power_spent_by(actor, potion)

    return settled.cleared_of_round_choices(), victims


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


def findings_of(state: GameState) -> tuple[Finding, ...]:
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
                state.player(choice.target).role, in_full=state.rules.roles.seer_learns_exact_role
            ),
        )
        for choice in state.night_choices
        if choice.action is RoleActionName.INSPECT
    )
