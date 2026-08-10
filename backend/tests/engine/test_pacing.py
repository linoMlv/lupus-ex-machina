"""How far ahead of its audience a game may run (J8.4, D-023, D-095).

The engine plays faster than anybody watches: a turn costs a few seconds of
model calls and half a minute of bubbles. Left alone it would play a whole game
into a buffer nobody has looked at yet, spending the call budget on turns the
user may never see.

So a turn is *in flight* until the client says it has shown everything that
existed when that turn began, and a game pauses once too many are. The pause is
taken **between two turns**, where the controls are already read — which is where
"the floor is never cut in the middle of a turn" comes from (D-014), and the
pause inherits it without any rule having to say so.
"""

import asyncio

from lupus_ex_machina.engine.runner.controls import Pacing


async def test_a_game_runs_freely_until_too_much_is_in_flight() -> None:
    pacing = Pacing(turns_in_flight=2)

    await pacing.before_a_turn(recorded=0)
    await pacing.before_a_turn(recorded=5)

    assert pacing.turns_in_flight == 2


async def test_a_turn_too_many_waits_for_the_audience() -> None:
    """The whole point: the engine stops rather than running away with the budget."""
    pacing = Pacing(turns_in_flight=1)
    await pacing.before_a_turn(recorded=0)

    waiting = asyncio.ensure_future(pacing.before_a_turn(recorded=5))
    await asyncio.sleep(0)

    assert not waiting.done(), "the second turn is held back"
    pacing.shown(4)
    await asyncio.wait_for(waiting, timeout=1)


async def test_showing_a_turn_makes_room_for_the_next_one() -> None:
    """A turn stops being in flight once the audience reaches its opening.

    The second turn began when five facts existed, so an audience that has shown
    the first three has reached the first turn and not the second.
    """
    pacing = Pacing(turns_in_flight=3)
    await pacing.before_a_turn(recorded=0)
    await pacing.before_a_turn(recorded=5)

    pacing.shown(2)

    assert pacing.turns_in_flight == 1, "the first turn has been reached, the second has not"


async def test_showing_everything_empties_the_flight() -> None:
    pacing = Pacing(turns_in_flight=3)
    await pacing.before_a_turn(recorded=0)
    await pacing.before_a_turn(recorded=5)

    pacing.shown(9)

    assert pacing.turns_in_flight == 0


async def test_a_game_nobody_paces_never_waits() -> None:
    """The default of the engine: scripted games and `make play` know no audience."""
    pacing = Pacing()

    for turn in range(50):
        await asyncio.wait_for(pacing.before_a_turn(recorded=turn), timeout=1)


async def test_the_first_turn_is_never_held_back() -> None:
    """There is nothing to have shown before it, so waiting would be waiting for ever."""
    pacing = Pacing(turns_in_flight=1)

    await asyncio.wait_for(pacing.before_a_turn(recorded=0), timeout=1)
