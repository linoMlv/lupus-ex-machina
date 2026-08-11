"""The person keeps a notebook, like everybody else at the table (J8.5.3, D-017).

Written down by the same Scribe as anybody's, which is the whole of the claim:
the engine holds the record, so a notebook line entered by a person goes through
the one door every fact goes through, and carries the audience that fact carries
(D-004). Nothing here widens anything, because nothing here writes anything.

It fills at **both** moments a person is asked something — the turn they play,
and the stock they take once a round has closed (D-086, D-108). The second is
the one that teaches most: the count and the resolution are what a round is
learnt from, and a notebook written before them would miss it.
"""

from collections.abc import Sequence

from lupus_ex_machina.engine.bidding import Bid
from lupus_ex_machina.engine.events import Event, NotebookEntryRecorded
from lupus_ex_machina.engine.intents import Wait
from lupus_ex_machina.engine.turn import AddNote, Reflection, Turn
from lupus_ex_machina.engine.views import PlayerView
from lupus_ex_machina.hosting.game import HostedGame
from support.hosted import a_provider, played_with_a_person
from support.persons import PLAYED_FROM_SEAT_ZERO

ON_A_TURN = "Écrit pendant mon tour."
ON_TAKING_STOCK = "Écrit après le dépouillement."


class TakesNotes:
    """A hand that writes a line every time it is asked anything, and nothing else.

    The scripted agents of J2 deliberately keep no notebook — a table of rules
    learns nothing from a round closing — so a notebook has to come from
    somewhere for this to be a property of anything at all.
    """

    async def bid(self, view: PlayerView, journal: Sequence[Event]) -> Bid:
        """Never ask for the floor: this hand is here for its notebook alone."""
        return Bid(urgency=0, intention="Rien à dire.")

    async def decide(self, view: PlayerView, journal: Sequence[Event]) -> Turn:
        """Write a line, and do nothing — `Wait` being legal everywhere (D-048)."""
        return Turn(notebook=(AddNote(note=ON_A_TURN),), intent=Wait())

    async def reflect(self, view: PlayerView, journal: Sequence[Event]) -> Reflection:
        """Write another line, once the round has closed (D-086)."""
        return Reflection(notebook=(AddNote(note=ON_TAKING_STOCK),))


async def test_what_the_person_writes_in_their_notebook_is_recorded() -> None:
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None

    await played_with_a_person(game, TakesNotes())

    written = [entry.note for entry in _notebook_of(game, person.player)]
    assert ON_A_TURN in written, "a line written on a turn reaches the journal"
    assert ON_TAKING_STOCK in written, "and so does one written once the round closed"


async def test_the_lines_are_theirs_and_turn_up_under_no_other_name() -> None:
    """The seat is the author, and the fact carries it — which is what D-004 rests on.

    The count comes first on purpose: "nothing turned up elsewhere" is true of a
    game where nothing was written at all, and a property over an empty set
    proves nothing.
    """
    game = HostedGame(PLAYED_FROM_SEAT_ZERO, provider=a_provider)
    person = game.person
    assert person is not None

    await played_with_a_person(game, TakesNotes())

    assert _notebook_of(game, person.player), "the person wrote lines to look for"
    theirs = {ON_A_TURN, ON_TAKING_STOCK}
    elsewhere = [
        entry
        for entry in _every_notebook_line(game)
        if entry.note in theirs and entry.player != person.player
    ]
    assert not elsewhere, f"lines of the person turned up under another name: {elsewhere}"


def _notebook_of(game: HostedGame, player: str) -> list[NotebookEntryRecorded]:
    return [entry for entry in _every_notebook_line(game) if entry.player == player]


def _every_notebook_line(game: HostedGame) -> list[NotebookEntryRecorded]:
    return [
        event.payload for event in game.events if isinstance(event.payload, NotebookEntryRecorded)
    ]
