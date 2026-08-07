"""A night: every living player is woken in turn, and nothing is settled early.

The night is silent (D-083) — nobody speaks, each player reads their notebook,
thinks, and acts if their role lets them. Everything collected is resolved in
one go at the end (D-006), which is what makes the interactions between roles
tractable at all.
"""

from lupus_ex_machina.engine.events import (
    EventPayload,
    NightResolved,
    PowerSpent,
    PrioritiesRevealed,
    RevealedShare,
    RunoffOpened,
    SeerFindingAnnounced,
    SeerInspected,
)
from lupus_ex_machina.engine.night import (
    findings_of,
    night_callers,
    powers_spent_tonight,
    prey_drawn_by_lot,
    resolve_night,
    tied_prey,
)
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import Team
from lupus_ex_machina.engine.runner import acting, closing
from lupus_ex_machina.engine.runner.scribe import Scribe
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome


def _night_outcome(victims: tuple[PlayerId, ...]) -> EventPayload:
    return NightResolved(victims=victims)


def _last_of_the_pack(callers: tuple[Player, ...]) -> PlayerId | None:
    """The last wolf the night calls, or ``None`` when it calls none.

    Where the pack's designation is closed. Read from the callers themselves
    rather than counted, so a pack of one, of two, or of none all work the same.
    """
    wolves = [caller for caller in callers if caller.team is Team.WEREWOLVES]
    return wolves[-1].id if wolves else None


async def play_night(scribe: Scribe, state: GameState) -> tuple[GameState, Outcome | None]:
    """Wake the roles in the order the night calls them, then resolve."""
    state = scribe.enter(state, Phase.NIGHT)
    state = await _collect_night_intents(scribe, state)

    _hand_out_what_the_seers_read(scribe, state)
    _write_down_what_was_used_up(scribe, state)
    return await closing.close(scribe, state, resolve_night, _night_outcome)


async def _collect_night_intents(scribe: Scribe, state: GameState) -> GameState:
    """Ask everyone the night wakes, in the order their role is called (D-006).

    Reading the callers once is safe here, and only here: nothing kills anyone
    while the night runs, because everything it collects is settled at the end
    (D-006). The day has no such guarantee — the hunter fires as they die — which
    is why its own loop cannot take the same shortcut.
    """
    callers = night_callers(state)
    last_wolf = _last_of_the_pack(callers)

    for caller in callers:
        state = await acting.take_turn(scribe, state, caller.id)
        if caller.id == last_wolf:
            state = await _settle_what_the_pack_designates(scribe, state)
    return state


async def _settle_what_the_pack_designates(scribe: Scribe, state: GameState) -> GameState:
    """Close the pack's designation as soon as its last wolf has answered.

    Inside the round of wake-ups rather than after it, because the roles woken
    later read the answer: the witch is shown the prey and may save them (D-029).
    Settled afterwards, a tie broken by the runoff — or a prey drawn by lot
    (D-081) — would kill someone she was never shown and could have saved. The
    wake order says she comes after the pack; this is what makes that mean
    *after it has finished*.
    """
    tied = tied_prey(state)
    if tied and state.rules.night.hold_a_runoff_on_a_tie:
        state = await _hold_a_runoff(scribe, state, tied)

    reveal_what_the_pack_weighed(scribe, state)
    return _send_the_pack_to_the_lot(scribe, state)


async def _hold_a_runoff(scribe: Scribe, state: GameState, tied: tuple[PlayerId, ...]) -> GameState:
    """Put the tied prey back to the pack, once, without a word (D-050, D-062)."""
    state = state.reopened_for_runoff(tied)
    scribe.record(RunoffOpened(targets=tied), at=state)

    for wolf in night_callers(state):
        if wolf.team is Team.WEREWOLVES:
            state = await acting.take_turn(scribe, state, wolf.id)
    return state


def reveal_what_the_pack_weighed(scribe: Scribe, state: GameState) -> None:
    """Show the pack who weighed what, now that answering is out of the question.

    After the designation, never during: the spreads are blind so that no wolf
    can follow another into a herd vote (D-085), and that is a property of *when*
    they are read rather than of keeping them secret for good.
    """
    if not state.rules.information.reveal_priorities_at_the_designation:
        return

    scribe.record(
        PrioritiesRevealed(
            shares=tuple(
                RevealedShare(wolf=share.actor, allocations=share.allocations)
                for share in state.priority_shares
            )
        ),
        at=state,
    )


def _send_the_pack_to_the_lot(scribe: Scribe, state: GameState) -> GameState:
    """Draw a prey for a pack made to take one that still has not (D-081).

    Drawn here, once, and only after the runoff has had its chance — a pack
    settles its own tie before the lot ever settles it for them. The answer goes
    into the state so that the resolution *reads* it: a night asked twice cannot
    come back with two different victims.
    """
    drawn = prey_drawn_by_lot(state, rng=scribe.rng)
    return state if drawn is None else state.with_prey_drawn(drawn)


def _hand_out_what_the_seers_read(scribe: Scribe, state: GameState) -> None:
    """Tell each seer what she read, and the table if she speaks (D-031)."""
    for finding in findings_of(state):
        scribe.record(
            SeerInspected(seer=finding.seer, target=finding.target, revelation=finding.revelation),
            at=state,
        )
        if state.rules.roles.speaking_seer:
            scribe.record(SeerFindingAnnounced(revelation=finding.revelation), at=state)


def _write_down_what_was_used_up(scribe: Scribe, state: GameState) -> None:
    """Record the potions this night emptied, before the round is wiped."""
    for actor, action in powers_spent_tonight(state):
        scribe.record(PowerSpent(actor=actor, action=action), at=state)
