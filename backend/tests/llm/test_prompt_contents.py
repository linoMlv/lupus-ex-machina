"""What the turn and bid prompts lay out for a seat (J7.2.3, J7.5.1, D-021).

Kept together: the two are built from the same day, and the bid prompt is
measured against the turn prompt it has to stay far shorter than (GL-7).
"""

from lupus_ex_machina.engine.events import NotebookEntryRecorded, SpeechDelivered
from lupus_ex_machina.engine.intents import PriorityPoint
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.llm.prompting import bid_prompt, turn_prompt
from support.prompts import OTHER, OTHER_WOLF, SEER, VILLAGER, WOLF, a_game

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
