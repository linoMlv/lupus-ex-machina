"""The timer that passes a turn nobody answered (J8.5.5, D-097).

By default a game waits on its person for as long as it takes: a game that does
not progress is an admitted state (D-078), and the moderator's hand is the way
out of it. A timer is the other way out, and it is **off unless it is set**.

What it does at the end of its count is the part worth stating. It does
**nothing** — never a blank vote, which would close the floor for that round and
could not be taken back (D-013, D-024). That is far too heavy a thing to happen
because somebody stepped away from their screen.
"""

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.intents import Wait
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rules import GameMode, GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.turn import Reflection
from lupus_ex_machina.hosting.game import HostedGame
from lupus_ex_machina.hosting.human import HumanAgent
from lupus_ex_machina.hosting.protocol import Question, QuestionClosed, QuestionPut
from lupus_ex_machina.hosting.stage import Stage
from support.hosted import a_provider, played_out
from support.persons import a_view_at_the_floor

#: Short enough to keep the suite quick, long enough that it is a wait and not
#: a coincidence of scheduling.
AT_ONCE = 0.01

PLAYED_ON_A_TIMER = GameConfiguration(
    rules=GameRules(
        table=TableOptions(
            player_count=6,
            seed=4,
            mode=GameMode.PLAYER,
            human_seat=0,
            human_answer_timeout_seconds=AT_ONCE,
        ),
        night=NightOptions(require_werewolf_target=True),
    )
)


def a_person_on_a_timer(said: list[Question] | None = None) -> HumanAgent:
    heard = said if said is not None else []
    return HumanAgent(PlayerId("p0"), announce=heard.append, timeout=AT_ONCE)


def test_a_game_waits_for_ever_unless_a_timer_is_set() -> None:
    """Off by default: passing somebody's turn is not something to do by accident."""
    assert TableOptions().human_answer_timeout_seconds is None


async def test_a_timer_carries_a_game_past_a_person_who_never_answers() -> None:
    """The whole point of the setting, and the only way to see it work.

    Nobody answers a single question here — which without a timer is the game
    that stops at its opening night for ever.
    """
    game = HostedGame(PLAYED_ON_A_TIMER, provider=a_provider)

    await played_out(game)

    assert game.stage is Stage.OVER


async def test_a_turn_the_timer_passed_does_nothing_at_all() -> None:
    """Never a blank vote: that closes the floor, and is irrevocable (D-024)."""
    turn = await a_person_on_a_timer().decide(a_view_at_the_floor(), ())

    assert isinstance(turn.intent, Wait)
    assert turn.reasoning is None, "and it puts no words in their mouth either"


async def test_a_stock_taking_the_timer_passed_writes_nothing_down() -> None:
    """Their notebook is theirs (D-017): silence must not add a line to it."""
    taken = await a_person_on_a_timer().reflect(a_view_at_the_floor(), ())

    assert taken == Reflection()


async def test_a_question_the_timer_passed_is_said_to_be_closed() -> None:
    """A passed turn records no fact, so nothing else would ever say so (D-097).

    A client with only the journal to go on would sit in front of a question the
    game stopped asking, for the rest of the game.
    """
    said: list[Question] = []

    await a_person_on_a_timer(said).decide(a_view_at_the_floor(), ())

    assert [type(spoken) for spoken in said] == [QuestionPut, QuestionClosed]
    assert [spoken.number for spoken in said] == [1, 1], "the same question, put and then closed"
