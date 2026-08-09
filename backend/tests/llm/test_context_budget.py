"""The budget a prompt is held to, and where it comes from (J7.3, D-063).

A window is declared per model rather than assumed, the budget is what a margin
leaves of it, and a model nobody declared a window for is never held to one.
"""

from collections.abc import Sequence

from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.events import (
    Event,
    NotebookEntryRecorded,
    PhaseEntered,
    SpeechDelivered,
    VoteResolved,
)
from lupus_ex_machina.engine.notebook import notebook_of
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.llm.answers import BidAnswer, ReflectionAnswer, TurnAnswer
from lupus_ex_machina.llm.context import ContextBudget, budget_for, estimated_tokens, pruned
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.messages import Message, Role
from support.recorders import VILLAGER, WOLF, Recorder
from support.seats import FORCED, answering, seated

# --- The window is declared, the budget is derived (J7.3.1, J7.3.2) ----------


def test_the_budget_is_what_the_margin_leaves_of_a_declared_window() -> None:
    """D-063: the window is real and per model, the budget is a part of it."""
    declared = SystemOptions(context_windows={"ministral-3b-latest": 128_000}, context_margin=0.8)

    assert budget_for("ministral-3b-latest", declared).tokens == 102_400


def test_a_model_no_window_was_declared_for_is_never_held_to_a_budget() -> None:
    """An undeclared model is left alone rather than given a guessed window.

    Guessing would be the worse failure: too small a guess prunes a context that
    fitted, and nothing at the table would say why an agent stopped remembering.
    """
    budget = budget_for("a-model-nobody-declared", SystemOptions())

    assert budget.tokens is None
    assert budget.holds((Message(role=Role.USER, content="x" * 10_000_000),))


def test_a_conversation_is_weighed_whole_rather_than_prompt_by_prompt() -> None:
    """The window holds everything sent, so the standing instructions count too."""
    tight = budget_for("m", SystemOptions(context_windows={"m": 100}, context_margin=1.0))
    halves = (
        Message(role=Role.SYSTEM, content="a" * 300),
        Message(role=Role.USER, content="b" * 300),
    )

    assert tight.holds(halves[:1]), "one half fits on its own"
    assert not tight.holds(halves), "both together do not"


def test_the_estimate_grows_with_the_text_it_measures() -> None:
    """An estimate, and named as one: no tokeniser is exact for every provider.

    What it must be is monotonic and roughly right — the margin of D-063 is what
    absorbs the rest, and V1 sits two orders of magnitude below its window.
    """
    assert estimated_tokens("") == 0
    assert estimated_tokens("a" * 400) > estimated_tokens("a" * 40)
    assert 50 <= estimated_tokens("a" * 400) <= 200


# --- What an overflowing journal loses, and what it keeps (J7.3.3, D-089) ----


def a_talkative_game() -> Recorder:
    """Five days of a game, talked through: one speech and one note a day.

    Left standing on the fifth day, so the same recorder gives both the journal
    and the state a turn would be taken in — a journal of one table read against
    the state of another would name players nobody is sitting.

    Days are walked through the phase machine rather than declared, so this is a
    journal the engine could really have written.
    """
    recorder = Recorder()
    for day in range(1, 6):
        recorder.enter(Phase.DAY, day=day)
        recorder.write(SpeechDelivered(speaker=WOLF.id, speech=f"Je parle le jour {day}."))
        recorder.write(NotebookEntryRecorded(player=WOLF.id, entry=day, note=f"Note {day}"))
        if day < 5:
            recorder.write(VoteResolved(eliminated=VILLAGER.id if day == 1 else None))
            recorder.enter(Phase.RESOLUTION)
            recorder.enter(Phase.NIGHT)
            recorder.enter(Phase.RESOLUTION)
    return recorder


def a_journal_of_five_days() -> tuple[Event, ...]:
    """The journal that game leaves behind."""
    return a_talkative_game().journal.events


def speeches_in(journal: Sequence[Event]) -> list[int]:
    """The days that still have something said on them."""
    return [event.day for event in journal if isinstance(event.payload, SpeechDelivered)]


def test_pruning_drops_the_speeches_of_the_days_that_are_no_longer_recent() -> None:
    """D-089: the last two days stay whole, older talk is what goes.

    The talk is what grows without bound — a hundred and twenty-five turns at
    fifty words — so it is the only thing worth dropping. Everything else in a
    journal is a handful of facts a game long.
    """
    kept = pruned(a_journal_of_five_days(), day=5)

    assert speeches_in(kept) == [4, 5]


def test_pruning_keeps_every_note_of_the_notebook() -> None:
    """Non-negotiable: the notebook is *replayed* from these facts (D-088).

    Drop one and the notebook loses a note nobody deleted, which would be an
    agent quietly forgetting something it wrote down.
    """
    whole = a_journal_of_five_days()

    assert notebook_of(pruned(whole, day=5), WOLF.id) == notebook_of(whole, WOLF.id)


def test_pruning_keeps_what_the_game_is_made_of_however_old_it_is() -> None:
    """Who died and what the table decided outlive the talk about them."""
    kept = pruned(a_journal_of_five_days(), day=5)

    assert [event for event in kept if isinstance(event.payload, VoteResolved)]
    assert [event for event in kept if isinstance(event.payload, PhaseEntered) and event.day == 1]


def test_a_game_shorter_than_the_window_of_days_loses_nothing() -> None:
    """Nothing is old yet on day two, so nothing goes."""
    whole = a_journal_of_five_days()

    assert pruned(whole, day=2) == whole


# --- Nothing is pruned until it has to be (J7.3.3, D-063) --------------------


async def a_turn_asked_with(budget: ContextBudget) -> str:
    """The prompt one seat is actually handed, played under that budget.

    Read off the provider rather than built here: what a test must check is what
    would have been *sent*, not what a helper thinks was assembled.
    """
    played = a_talkative_game()
    provider = FakeCompletions(invent=answering)

    await seated(provider, budget=budget).decide(
        project(played.state, WOLF.id), played.journal.events
    )

    return provider.asked[-1].messages[-1].content


async def test_a_conversation_that_fits_is_handed_over_whole() -> None:
    """The mechanism costs nothing until a window is actually reached (D-063)."""
    asked = await a_turn_asked_with(ContextBudget(tokens=None))

    assert "jour 1" in asked, "the oldest talk is still there"
    assert "jour 5" in asked


async def test_a_conversation_too_large_for_its_window_is_pruned_to_fit() -> None:
    """And it is the older talk that goes, exactly as D-089 says."""
    asked = await a_turn_asked_with(ContextBudget(tokens=1))

    assert "jour 1" not in asked, "the oldest talk was dropped"
    assert "jour 5" in asked, "and the recent talk was kept"
    assert "Note 1" in asked, "the notebook survives whatever happens (D-088)"


# --- A whole game never comes close to a window (J7.3.4, D-063) --------------

#: A speech and an analysis at the limits D-021 sets, so the game measured below
#: is the most expensive one the rules can produce rather than a quiet one.
A_LONG_SPEECH = "Je pense que Basile ment depuis hier soir et je vais le dire. " * 8
A_LONG_ANALYSIS = "Basile a changé trois fois de version depuis ce matin. " * 8


def talking(schema: type, messages: object) -> str:
    """A table where everybody speaks at length, every time they are asked."""
    if schema is BidAnswer:
        return BidAnswer(urgency=90, intention="Répondre à Basile.").model_dump_json()
    if schema is ReflectionAnswer:
        return ReflectionAnswer(reasoning=A_LONG_ANALYSIS).model_dump_json()
    return TurnAnswer(reasoning=A_LONG_ANALYSIS, speech=A_LONG_SPEECH).model_dump_json()


async def test_a_whole_game_of_talkers_never_reaches_the_window_of_its_model() -> None:
    """D-063 in numbers: a game is about fifteen thousand tokens, a window is 128k.

    This is the measurement the decision rests on, so it is made rather than
    asserted — a full game, everybody talking to their word limit, and the
    largest conversation it produced weighed against a real window.
    """
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng)
    provider = FakeCompletions(invent=talking)
    budget = budget_for(
        "mistral-small-latest",
        SystemOptions(context_windows={"mistral-small-latest": 128_000}),
    )
    agents = {player.id: seated(provider, budget=budget) for player in state.players}

    result = await play_game(state, agents, max_rounds=10, rng=rng)

    spoken = [event for event in result.journal if isinstance(event.payload, SpeechDelivered)]
    assert len(spoken) > 50, "a quiet game would put nothing in a prompt worth measuring"

    peak = max(
        sum(estimated_tokens(message.content) for message in asked.messages)
        for asked in provider.asked
    )
    assert budget.tokens is not None
    assert peak < budget.tokens, f"no game of V1 reaches its window: {peak} of {budget.tokens}"
    assert peak < 30_000, f"and it stays in the order of magnitude D-063 claims: {peak}"
