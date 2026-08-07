"""How a debate is meant to end, and the nets under it (J5.5, D-048, D-060).

A round closes when the last player votes (D-013). Everything here is what
happens when a table will not do that.
"""

from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import (
    Scripted,
)
from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import (
    BallotAnnounced,
    Event,
    ForcedVoteReason,
    VoteForced,
)
from lupus_ex_machina.engine.intents import (
    TakeTurn,
    Wait,
)
from lupus_ex_machina.engine.runner import (
    DebateControl,
)
from lupus_ex_machina.engine.turn import Turn
from lupus_ex_machina.engine.views import PlayerView
from support.agents import NeverVotesAgent, a_table_of
from support.days import a_day_played_by
from support.games import (
    speakers_of,
)

# --- How a debate is meant to end (J5.5, D-048, D-060) -----------------------


def forced_votes_in(events: tuple[Event, ...]) -> list[VoteForced]:
    return [event.payload for event in events if isinstance(event.payload, VoteForced)]


async def test_a_turn_nobody_used_means_the_debate_is_over() -> None:
    """An auction that produced neither a word nor a ballot ends the debate.

    D-060: a table with nothing left to say is put to the vote, rather than
    spending another round of model calls on the same silence.
    """
    events = await a_day_played_by(a_table_of(NeverVotesAgent))

    forced = forced_votes_in(events)

    assert forced, "the vote was forced"
    assert forced[0].reason is ForcedVoteReason.DEBATE_EXHAUSTED


async def test_a_debate_that_ran_out_of_turns_is_put_to_the_vote() -> None:
    """The budget of turns is the other way out, and it says so in the journal."""

    class TalksForever(Scripted):
        async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
            return Turn(intent=TakeTurn(speech="Je continue.") if view.may_speak else Wait())

    events = await a_day_played_by(a_table_of(TalksForever))

    forced = forced_votes_in(events)

    assert forced, "a debate that never votes is closed anyway"
    assert forced[0].reason is ForcedVoteReason.TURN_BUDGET_SPENT


async def test_a_forced_vote_closes_the_round_for_everyone() -> None:
    """Whatever forced it, the round ends the way D-013 says it does."""
    events = await a_day_played_by(a_table_of(NeverVotesAgent))

    voters = {event.payload.voter for event in events if isinstance(event.payload, BallotAnnounced)}

    assert len(voters) == 8, "every living player ends the round having voted"


async def test_the_moderator_can_cut_a_debate_short() -> None:
    """D-048: the hand the user keeps on a debate that drags on.

    Set to zero, the vote is called at once — and the journal says it was the
    moderator, not the table running out of things to say.
    """
    events = await a_day_played_by(a_table_of(NeverVotesAgent), control=DebateControl(turns_left=0))

    forced = forced_votes_in(events)

    assert forced[0].reason is ForcedVoteReason.MODERATOR
    assert not speakers_of(events), "nobody got to speak"


def test_the_moderator_leaves_the_debate_alone_by_default() -> None:
    assert DebateControl().turns_left is None


async def test_a_moderator_who_allows_one_turn_gets_exactly_one() -> None:
    class TalksForever(Scripted):
        async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
            return Turn(intent=TakeTurn(speech="Je continue.") if view.may_speak else Wait())

    events = await a_day_played_by(a_table_of(TalksForever), control=DebateControl(turns_left=1))

    assert len(speakers_of(events)) == 1
    assert forced_votes_in(events)[0].reason is ForcedVoteReason.MODERATOR


async def test_the_moderator_can_call_time_in_the_middle_of_a_debate() -> None:
    """What the control is for: a hand on a debate already under way (D-048).

    Set before the day, it is a setting. The point of D-048 is the user watching
    a debate drag on and stopping it, so the allowance is read again before
    every turn rather than once at the start.
    """
    control = DebateControl()

    class SpeaksThenCallsTime(Scripted):
        """Speaks once, and cuts the debate short as it does — as the user would."""

        async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
            return Bid(urgency=50, intention="Encore.")

        async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
            if not view.may_speak:
                return Turn(intent=Wait())
            control.cut_to(0)
            return Turn(intent=TakeTurn(speech="Je serai bref."))

    events = await a_day_played_by(a_table_of(SpeaksThenCallsTime), control=control)

    assert len(speakers_of(events)) == 1, "the debate stopped at the next turn"
    assert forced_votes_in(events)[0].reason is ForcedVoteReason.MODERATOR
