"""The two hands that reach into a hosted game from outside its rules (J8.5).

The engine has held both since J5 — `FloorClaim` and `DebateControl`, read
between turns, which is where "the floor is never cut in the middle of a turn"
comes from (D-014). What was missing is that a *hosted* game let go of them: it
took the defaults `play_game` builds, so nobody outside could ever reach one.

They are told apart by who they belong to. Taking the floor outright is the
person's, and a game with nobody at the table has no such thing. Calling time on
a debate is the moderator's, and it works **in both modes** (D-048) — which is
also why neither of them travels on the websocket (D-109).
"""

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.events import FloorClaimed, ForcedVoteReason, VoteForced
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.hosting.errors import NobodyIsPlayingError
from lupus_ex_machina.hosting.game import HostedGame
from support.hosted import a_provider, played_out, played_with_a_person
from support.persons import PLAYED_FROM_SEAT_ZERO

WATCHED = GameConfiguration(
    rules=GameRules(
        table=TableOptions(player_count=6, seed=4),
        night=NightOptions(require_werewolf_target=True),
    )
)


async def test_the_person_may_take_the_floor_outright() -> None:
    """An absolute priority is honoured *instead of* an auction, not inside one.

    Once, and once only: a claim that outlived its turn would hand the floor to
    the same person for the rest of the day (D-014).
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None

    game.hands.claim_the_floor()
    await played_with_a_person(game, RandomAgent(rng=create_rng(4)))

    claimed = [event.payload for event in game.events if isinstance(event.payload, FloorClaimed)]
    assert [taken.player for taken in claimed] == [person.player]


async def test_nobody_takes_the_floor_in_a_game_with_nobody_at_the_table() -> None:
    """Refused rather than passed over: a button that did nothing would look broken."""
    game = HostedGame(WATCHED, provider=a_provider)

    with pytest.raises(NobodyIsPlayingError):
        game.hands.claim_the_floor()


async def test_the_moderator_may_call_time_on_a_debate_of_a_watched_game() -> None:
    """D-048 works in both modes, which is why it is not the person's button."""
    game = HostedGame(WATCHED, provider=a_provider)

    game.hands.cut_the_debate_to(0)
    await played_out(game)

    forced = [event.payload for event in game.events if isinstance(event.payload, VoteForced)]
    assert forced, "the debate was closed by something"
    assert forced[0].reason is ForcedVoteReason.MODERATOR


def test_a_game_nobody_moderates_holds_the_allowance_its_own_rules_set() -> None:
    """The hand starts where the configuration left it, not at some default of its own."""
    game = HostedGame(WATCHED, provider=a_provider)

    assert game.hands.debate_turns_left == WATCHED.rules.vote.turns_before_forced_vote
