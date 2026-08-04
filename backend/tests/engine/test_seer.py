"""The seer (D-031).

She looks at one player a night and is told something about them. What exactly
she is told is configurable — the role itself, or only whether it is a wolf —
because the two make very different games, and the choice belongs to whoever
sets one up.

The speaking variant announces her finding to the table **without the name of the
player she looked at**. Revealing the name would empty the role of its interest,
which is why the announcement is a fact of its own rather than the private one
with a wider audience.
"""

import pytest

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.errors import IllegalIntentError
from lupus_ex_machina.engine.events import Fact, SeerFindingAnnounced, SeerInspected
from lupus_ex_machina.engine.intents import RoleAction
from lupus_ex_machina.engine.journal import Journal
from lupus_ex_machina.engine.night import Revelation, findings_of
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.players import Player, PlayerId
from lupus_ex_machina.engine.policy import InformationPolicy
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.validation import validate_intent

SEER = PlayerId("p0")
WOLF = PlayerId("p1")
WITCH = PlayerId("p2")
VILLAGER = PlayerId("p3")

TABLE = (
    Player(id=SEER, name="Adèle", seat=0, role=RoleName.SEER),
    Player(id=WOLF, name="Basile", seat=1, role=RoleName.WEREWOLF),
    Player(id=WITCH, name="Camille", seat=2, role=RoleName.WITCH),
    Player(id=VILLAGER, name="Diane", seat=3, role=RoleName.VILLAGER),
)

EXACT = InformationPolicy(seer_learns_exact_role=True)
BINARY = InformationPolicy(seer_learns_exact_role=False)
SPEAKING = InformationPolicy(seer_learns_exact_role=True, speaking_seer=True)


def night() -> GameState:
    return (
        GameState.initial(TABLE)
        .entering(Phase.DAY, day=1)
        .entering(Phase.RESOLUTION)
        .entering(Phase.NIGHT)
    )


def inspect(target: PlayerId) -> RoleAction:
    return RoleAction(action=RoleActionName.INSPECT, target=target)


def looked_at(target: PlayerId) -> GameState:
    return night().with_night_choice_from(SEER, RoleActionName.INSPECT, target)


# --- Whom she may look at (J4.4.1) -------------------------------------------


def test_the_seer_may_look_at_another_living_player() -> None:
    validate_intent(night(), SEER, inspect(WOLF))


def test_the_seer_may_not_look_at_herself() -> None:
    """She already knows what she is; the view never offers it either."""
    with pytest.raises(IllegalIntentError, match="themselves"):
        validate_intent(night(), SEER, inspect(SEER))


def test_the_seer_may_not_look_at_the_dead() -> None:
    state = night().with_players_killed([WOLF])

    with pytest.raises(IllegalIntentError, match="dead"):
        validate_intent(state, SEER, inspect(WOLF))


def test_the_seer_looks_at_one_player_a_night() -> None:
    with pytest.raises(IllegalIntentError, match="already"):
        validate_intent(looked_at(WOLF), SEER, inspect(VILLAGER))


def test_nobody_but_the_seer_may_look() -> None:
    with pytest.raises(IllegalIntentError, match="cannot inspect"):
        validate_intent(night(), WITCH, inspect(WOLF))


def test_the_seer_only_looks_at_night() -> None:
    day = GameState.initial(TABLE).entering(Phase.DAY, day=2)

    with pytest.raises(IllegalIntentError, match="not played during"):
        validate_intent(day, SEER, inspect(WOLF))


# --- What she is told (J4.4.2) -----------------------------------------------


def test_she_learns_the_exact_role_when_that_is_the_setting() -> None:
    (finding,) = findings_of(looked_at(WITCH), policy=EXACT)

    assert finding.seer == SEER
    assert finding.target == WITCH
    assert finding.revelation.role is RoleName.WITCH


def test_she_learns_only_wolf_or_not_when_that_is_the_setting() -> None:
    (finding,) = findings_of(looked_at(WITCH), policy=BINARY)

    assert finding.revelation.role is None
    assert finding.revelation.is_werewolf is False


def test_the_binary_setting_still_names_a_wolf_as_one() -> None:
    (finding,) = findings_of(looked_at(WOLF), policy=BINARY)

    assert finding.revelation.is_werewolf is True


def test_the_exact_setting_tells_a_wolf_apart_too() -> None:
    (finding,) = findings_of(looked_at(WOLF), policy=EXACT)

    assert finding.revelation.role is RoleName.WEREWOLF


def test_a_night_she_sat_out_reveals_nothing() -> None:
    assert findings_of(night(), policy=EXACT) == ()


def test_only_what_the_seer_did_becomes_a_finding() -> None:
    """Other powers land in the same collection and must not be mistaken for hers."""
    state = looked_at(WOLF).with_night_choice_from(WITCH, RoleActionName.POISON, VILLAGER)

    findings = findings_of(state, policy=EXACT)

    assert [finding.target for finding in findings] == [WOLF]


# --- What the table hears (J4.4.3) -------------------------------------------


def played(policy: InformationPolicy) -> GameResult:
    """A game where the seat holding the seer always looks at someone."""
    rng = create_rng(4)
    state = create_game(8, rng=rng)
    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}
    return play_game(state, agents, journal=Journal(), policy=policy)


def facts_of[FactT: Fact](result: GameResult, kind: type[FactT]) -> list[FactT]:
    return [event.payload for event in result.journal if isinstance(event.payload, kind)]


def test_the_announcement_can_carry_no_name_at_all() -> None:
    """The guarantee is the shape of the fact, not the care of whoever fills it.

    An announcement that could name the player she looked at would empty the
    role of its interest, so the field simply does not exist (D-031).
    """
    announced = SeerFindingAnnounced(revelation=Revelation(role=RoleName.WEREWOLF))

    assert "target" not in announced.model_dump()
    assert set(announced.model_dump()) == {"kind", "revelation"}


def test_a_speaking_seer_tells_the_table_what_she_found() -> None:
    result = played(SPEAKING)

    assert facts_of(result, SeerFindingAnnounced)


def test_a_silent_seer_tells_the_table_nothing() -> None:
    result = played(EXACT)

    assert facts_of(result, SeerInspected), "she still looked"
    assert facts_of(result, SeerFindingAnnounced) == []


def test_every_announcement_matches_a_finding_she_actually_made() -> None:
    result = played(SPEAKING)

    announced = [fact.revelation for fact in facts_of(result, SeerFindingAnnounced)]
    found = [fact.revelation for fact in facts_of(result, SeerInspected)]

    assert announced == found
