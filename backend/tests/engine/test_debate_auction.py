"""The floor is auctioned, never passed round the table (J5.3.3, D-002).

The heart of the project: who speaks is won, and what it is won against is
the round the auction is scored on.
"""

import itertools

from lupus_ex_machina.engine.events import (
    Event,
    FloorAuctioned,
)
from lupus_ex_machina.engine.visibility import VisibilityScope
from support.days import a_day_of
from support.games import (
    speakers_of,
)

# --- The floor is auctioned, not passed round the table (J5.3.3, D-002) ------


def auctions_in(events: tuple[Event, ...]) -> list[FloorAuctioned]:
    return [event.payload for event in events if isinstance(event.payload, FloorAuctioned)]


async def test_the_most_pressing_player_speaks_first_whatever_their_seat() -> None:
    """The whole point of the auction: the floor is won, not handed round.

    Seat 7 is last in every ordering the engine had before this; wanting it more
    than anyone else has to be enough to speak first.
    """
    state, events = await a_day_of({seat: (100 if seat == 7 else 10) for seat in range(8)})

    assert speakers_of(events)[0] == state.players[7].id


async def test_holding_the_floor_is_what_costs_the_most_in_the_next_auction() -> None:
    """The anti-monopoly of D-002: nobody speaks twice in a row while others want to."""
    _, events = await a_day_of(dict.fromkeys(range(8), 50))

    spoken = speakers_of(events)

    assert len(spoken) > 1, "the day had a debate at all"
    assert all(first != second for first, second in itertools.pairwise(spoken))


async def test_every_bid_is_written_down_including_the_losing_ones() -> None:
    """The raw material of the staging (D-075) and of tuning the coefficients."""
    _, events = await a_day_of({seat: seat * 10 for seat in range(8)})

    auctions = auctions_in(events)

    assert auctions, "an auction is a fact of the game"
    assert len(auctions[0].scores) > 1, "the losers are kept too"


async def test_an_auction_is_for_the_spectator_alone() -> None:
    """What a player wanted to say is not something the table gets to know."""
    _, events = await a_day_of(dict.fromkeys(range(8), 50))

    auctions = auctions_in(events)

    assert auctions, "there were auctions to check in the first place"
    for auction in auctions:
        assert auction.audience.scope is VisibilityScope.SPECTATOR
