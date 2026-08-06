"""Building what a model is handed, out of what its player is allowed to know.

Two properties matter here, and they are the reason this module exists rather
than a few f-strings scattered about:

  - a prompt is built from the **projected view and the projected journal**, and
    from nothing else (GL-3, J7.2.6). Two games differing only by a secret must
    hand an unentitled player the very same prompt;
  - the prompts themselves live in files (J7.2.1). They will be rewritten
    constantly during calibration, and rewriting them must never mean touching
    the code.
"""

import ast
import pathlib

import pytest

import lupus_ex_machina.llm
from lupus_ex_machina.engine.events import NotebookEntryRecorded, SpeechDelivered
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.journal import Journal, project_journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.engine.visibility import Recipient
from lupus_ex_machina.llm.prompting import Briefing, bid_prompt, system_prompt, turn_prompt

SEER = PlayerId("p0")
WOLF = PlayerId("p1")
VILLAGER = PlayerId("p2")
OTHER = PlayerId("p3")

OTHER_WOLF = PlayerId("p4")

TABLE = (
    Player(id=SEER, name="Adèle", seat=0, role=RoleName.SEER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=VILLAGER, name="Camille", seat=2, role=RoleName.VILLAGER),
    Player(id=OTHER, name="Diane", seat=3, role=RoleName.HUNTER),
    Player(id=OTHER_WOLF, name="Émile", seat=4, role=RoleName.WEREWOLF),
)

A_PERSONALITY = "Tu es méthodique et tu détestes les conclusions hâtives."


def briefing() -> Briefing:
    return Briefing(personality=A_PERSONALITY)


def a_game(*, other_role: RoleName = RoleName.HUNTER) -> GameState:
    """The same table, with one player's role changed — a secret nobody else has."""
    table = tuple(
        player.model_copy(update={"role": other_role}) if player.id == OTHER else player
        for player in TABLE
    )
    return GameState.initial(table)


# --- What the system prompt has to say (J7.2.2) ------------------------------


def test_the_system_prompt_states_the_rules_the_role_and_the_temperament() -> None:
    state = a_game()

    written = system_prompt(project(state, SEER), briefing=briefing())

    assert "loup-garou" in written.lower(), "the rules of the game"
    assert "voyante" in written.lower(), "the role this seat was dealt"
    assert A_PERSONALITY in written, "the temperament of D-058"


def test_the_system_prompt_disarms_anything_written_inside_a_block() -> None:
    """D-067: what a block holds is a claim, never an instruction."""
    written = system_prompt(project(a_game(), SEER), briefing=briefing())

    assert "<parole>" in written
    assert "instruction" in written.lower()


def test_the_system_prompt_frames_lying_as_a_rule_of_the_game() -> None:
    """The countermeasure to a model that will not lie, and denounces itself (BS-001)."""
    written = system_prompt(project(a_game(), WOLF), briefing=briefing())

    assert "mensonge" in written.lower() or "mentir" in written.lower()


def test_a_wolf_is_told_who_its_pack_is_and_a_villager_is_not() -> None:
    """The one thing a role knows about somebody else's (D-032)."""
    state = a_game()

    assert "Émile" in system_prompt(project(state, WOLF), briefing=briefing())
    assert "Émile" not in system_prompt(project(state, VILLAGER), briefing=briefing())


# --- The prompt holds nothing the view does not (J7.2.6, GL-3) --------------


def transcript_of(state: GameState, viewer: PlayerId) -> tuple[str, str, str]:
    """The three prompts a seat would be handed in that state."""
    journal = project_journal(Journal().events, Recipient.of(state.player(viewer)))
    view = project(state, viewer)
    return (
        system_prompt(view, briefing=briefing()),
        turn_prompt(view, journal=journal),
        bid_prompt(view, journal=journal),
    )


@pytest.mark.parametrize("viewer", [SEER, WOLF, VILLAGER], ids=["seer", "wolf", "villager"])
def test_a_secret_nobody_is_entitled_to_changes_nothing_in_their_prompts(viewer: PlayerId) -> None:
    """Whole prompts compared, so a leak under any wording makes them differ.

    The same reason the projections of J3 are compared whole rather than field by
    field: a test looking for one name would be blind to a leak worded any other
    way.
    """
    as_a_hunter = transcript_of(a_game(other_role=RoleName.HUNTER), viewer)
    as_a_witch = transcript_of(a_game(other_role=RoleName.WITCH), viewer)

    assert as_a_hunter == as_a_witch


def test_the_player_whose_role_changed_does_see_the_difference() -> None:
    """Guard the test above: prompts identical for everybody would pass it too."""
    as_a_hunter = transcript_of(a_game(other_role=RoleName.HUNTER), OTHER)
    as_a_witch = transcript_of(a_game(other_role=RoleName.WITCH), OTHER)

    assert as_a_hunter != as_a_witch


# --- The prompts live in files (J7.2.1) --------------------------------------


def python_modules() -> list[pathlib.Path]:
    return sorted(pathlib.Path(lupus_ex_machina.llm.__file__).parent.rglob("*.py"))


def prose_in(module: pathlib.Path) -> list[str]:
    """Every long string literal in a module, docstrings aside."""
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    docstrings = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value) > 120
        and node.value not in docstrings
    ]


def test_no_prompt_is_written_in_the_code() -> None:
    """They are rewritten constantly while calibrating; that must not touch code."""
    offenders = {module.name: prose_in(module) for module in python_modules() if prose_in(module)}

    assert offenders == {}


def test_the_guard_actually_reads_the_modules() -> None:
    """Guard the guard: an empty scan would make the test above vacuous."""
    assert len(python_modules()) > 5


# --- What the turn prompt lays out (J7.2.3, D-021) ---------------------------


def a_day(state: GameState) -> GameState:
    """The same game, moved to a day where the floor and the vote are open."""
    return state.entering(Phase.DAY, day=2)


def spoken_journal(state: GameState, speech: str, *, speaker: PlayerId = VILLAGER) -> Journal:
    journal = Journal()
    journal.record(SpeechDelivered(speaker=speaker, speech=speech), at=state)
    return journal


def test_the_turn_prompt_offers_what_the_view_says_is_legal() -> None:
    """Read off the view, so what is offered is exactly what the validator takes."""
    state = a_day(a_game())

    written = turn_prompt(project(state, SEER), journal=())

    assert "Prendre la parole" in written
    assert "Voter contre" in written
    assert "Basile" in written, "the players this seat may name"


def test_the_turn_prompt_says_when_a_seat_may_only_watch() -> None:
    """Night 0 gives nobody a move, and a heading with nothing under it reads as withheld."""
    written = turn_prompt(project(a_game(), SEER), journal=())

    assert "observer" in written


def test_the_turn_prompt_offers_a_power_and_the_prey_it_answers() -> None:
    """The witch is told the victim, because her potion only saves that one (D-029)."""
    state = (
        a_game()
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
        .with_priority_share_from(WOLF, (PriorityPoint(target=VILLAGER, points=100),))
        .with_priority_share_from(OTHER_WOLF, (PriorityPoint(target=VILLAGER, points=100),))
    )
    witch = state.player(OTHER).model_copy(update={"role": RoleName.WITCH})
    state = GameState.initial(
        tuple(witch if player.id == OTHER else player for player in state.players)
    ).model_copy(
        update={"phase": state.phase, "day": state.day, "priority_shares": state.priority_shares}
    )

    written = turn_prompt(project(state, OTHER), journal=())

    assert "potion" in written
    assert "La meute a désigné Camille." in written


def test_the_turn_prompt_carries_the_notebook_with_its_numbers() -> None:
    """An agent refers to a note by its number, so the number has to be in front of it."""
    state = a_day(a_game())
    journal = Journal()
    journal.record(NotebookEntryRecorded(player=SEER, entry=4, note="Basile ment."), at=state)

    written = turn_prompt(project(state, SEER), journal=journal.events)

    assert "[4] Basile ment." in written


def test_the_turn_prompt_carries_the_transcript_in_blocks() -> None:
    """Every speech reaches a model inside a block, and none of them naked (D-067)."""
    state = a_day(a_game())
    journal = spoken_journal(state, "Je me méfie d'Adèle.")

    written = turn_prompt(project(state, SEER), journal=journal.events)

    assert '<parole locuteur="Camille" jour="2" ordre="1">' in written
    assert "Je me méfie d'Adèle." in written


def test_the_turn_prompt_states_the_word_limits_of_the_game() -> None:
    """D-021, read from the view like everything else in a prompt."""
    written = turn_prompt(project(a_day(a_game()), SEER), journal=())

    assert "50 mots au maximum" in written, "speech"
    assert "40 mots au maximum" in written, "analysis"
    assert "20 mots au maximum" in written, "a note"


# --- What the bid prompt lays out (D-002, GL-7) ------------------------------


def test_the_bid_prompt_shows_the_turn_it_answers() -> None:
    state = a_day(a_game())
    journal = spoken_journal(state, "Adèle n'a rien dit de la journée.")

    written = bid_prompt(project(state, SEER), journal=journal.events)

    assert "Adèle n'a rien dit de la journée." in written
    assert "<parole" in written


def test_the_bid_prompt_says_so_when_nobody_has_spoken_yet() -> None:
    written = bid_prompt(project(a_day(a_game()), SEER), journal=())

    assert "Personne n'a encore parlé." in written


def test_the_bid_prompt_stays_far_shorter_than_a_turn_prompt() -> None:
    """The call a game makes most often (GL-7): handing it the transcript would cost as much."""
    state = a_day(a_game())
    journal = spoken_journal(state, "Une phrase quelconque.")
    view = project(state, SEER)

    assert len(bid_prompt(view, journal=journal.events)) < len(
        turn_prompt(view, journal=journal.events)
    )


def test_day_one_offers_the_blank_vote_and_nothing_else() -> None:
    """Its only legal vote (D-032), and the prompt says so rather than listing nobody."""
    written = turn_prompt(project(a_game().entering(Phase.DAY, day=1), SEER), journal=())

    assert "seul vote possible" in written
    assert "Voter contre" not in written


def test_a_wolf_is_told_what_it_has_to_spread_and_over_whom() -> None:
    """The pack designates by weight, blind to what the others put (D-008, D-085)."""
    state = a_game().entering(Phase.DAY, day=1).entering(Phase.RESOLUTION).entering(Phase.NIGHT)

    written = turn_prompt(project(state, WOLF), journal=())

    assert "Répartir 100 points" in written
    assert "ne voient pas ta répartition" in written
