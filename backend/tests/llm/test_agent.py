"""An agent that plays a seat with a model behind it (J7.4).

Never over the network: the provider is the fake one, so a whole game is played
in a test, for free and instantly (GL-2). What is under test is the translation
in both directions — a projected view into a prompt, and a model's answer into
an intent the engine will take.
"""

import json

from lupus_ex_machina.configuration.agents import Personality
from lupus_ex_machina.engine.intents import PriorityPoint, RoleAction, SharePriority, TakeTurn
from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleActionName
from lupus_ex_machina.engine.rules import GameRules, NightOptions
from lupus_ex_machina.engine.runner import play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.turn import AddNote, DropNote
from lupus_ex_machina.engine.views import project
from lupus_ex_machina.llm.agent import LlmAgent
from lupus_ex_machina.llm.answers import (
    BidAnswer,
    Emote,
    PriorityAnswer,
    ReflectionAnswer,
    TurnAnswer,
)
from lupus_ex_machina.llm.fake import FakeCompletions
from lupus_ex_machina.llm.personalities import personalities

#: A pack made to leave every night with a victim, so a table of models that
#: never names anybody still reaches an end (D-078, D-081).
FORCED = GameRules(night=NightOptions(require_werewolf_target=True))


def answering(schema: type, messages: object) -> str:
    """A plausible answer for each shape, with nothing but a thought in it.

    Enough to play a whole game: nobody names anybody, so the day is closed by
    the forced vote and the night by the lot (D-060, D-081).
    """
    if schema is BidAnswer:
        return BidAnswer(urgency=50, intention="Peut-être parler.").model_dump_json()
    if schema is ReflectionAnswer:
        return ReflectionAnswer(reasoning="Ce tour m'a appris peu de choses.").model_dump_json()
    return TurnAnswer(reasoning="Je regarde qui parle le plus.").model_dump_json()


def seated(provider: FakeCompletions, personality: Personality = Personality.INTJ) -> LlmAgent:
    return LlmAgent(
        completions=provider,
        personality=personalities()[personality],
        bidding_model="ministral-3b-latest",
        generation_model="mistral-small-latest",
    )


async def test_a_whole_game_is_played_by_models_without_a_network() -> None:
    """The exit criterion of J7.1.6, and what every test of J8 will lean on."""
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng)
    provider = FakeCompletions(invent=answering)
    agents = {player.id: seated(provider) for player in state.players}

    result = await play_game(state, agents, max_rounds=10, rng=rng)

    assert result.state.phase.value == "ended"
    assert provider.asked, "a game where no model was asked anything would prove nothing"


async def test_what_a_model_said_becomes_a_turn_the_engine_takes() -> None:
    """The translation that matters: a name into a player, a text into a speech."""
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng).entering(Phase.DAY, day=2)
    speaker, accused = state.players[0], state.players[1]
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Basile est trop silencieux.",
                notebook=(AddNote(note="Surveiller Basile."),),
                emote=Emote.INSISTENCE,
                speech="Tu n'as rien dit de la journée.",
                addressed=accused.name,
                accused=accused.name,
                vote=accused.name,
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(state, speaker.id), ())

    note = turn.notebook[0]
    assert isinstance(note, AddNote)
    assert note.note == "Surveiller Basile."

    played = turn.intent
    assert isinstance(played, TakeTurn)
    assert turn.reasoning == "Basile est trop silencieux."
    assert played.speech == "Tu n'as rien dit de la journée."
    assert played.accused == accused.id, "the name became the player it belongs to"
    assert played.vote is not None
    assert played.vote.target == accused.id


async def test_a_name_no_one_at_the_table_bears_is_dropped_rather_than_played() -> None:
    """A model invents a player now and then; the turn is worth keeping anyway."""
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng).entering(Phase.DAY, day=2)
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Je vise quelqu'un qui n'existe pas.",
                speech="Je me méfie.",
                accused="Personne-Qui-N-Existe-Pas",
                vote="Personne-Qui-N-Existe-Pas",
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(state, state.players[0].id), ())

    played = turn.intent
    assert isinstance(played, TakeTurn)
    assert played.accused is None
    assert played.vote is None, "an invented target is not a blank vote either"


async def test_a_night_answer_becomes_the_power_it_names() -> None:
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng)
    seer = next(player for player in state.players if player.role.value == "seer")
    night = state.entering(Phase.DAY, day=1).entering(Phase.RESOLUTION).entering(Phase.NIGHT)
    target = next(player for player in night.living if player.id != seer.id)
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Je sonde le plus discret.",
                action=RoleActionName.INSPECT,
                target=target.name,
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(night, seer.id), ())

    played = turn.intent
    assert isinstance(played, RoleAction)
    assert played.action is RoleActionName.INSPECT
    assert played.target == target.id


async def test_a_bid_carries_the_urgency_the_model_gave() -> None:
    provider = FakeCompletions(script=[json.dumps({"urgency": 73, "intention": "Répondre."})])
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)

    bid = await seated(provider).bid(project(state, state.players[0].id), ())

    assert bid.intention == "Répondre."
    assert bid.urgency >= 0


async def test_the_bid_runs_on_the_cheap_model_and_the_turn_on_the_capable_one() -> None:
    """D-077: two models per seat is what makes the project viable on a free tier."""
    provider = FakeCompletions(invent=answering)
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    view = project(state, state.players[0].id)
    agent = seated(provider)

    await agent.bid(view, ())
    await agent.decide(view, ())

    assert [asked.model for asked in provider.asked] == [
        "ministral-3b-latest",
        "mistral-small-latest",
    ]


async def test_a_pack_answer_becomes_the_spread_it_describes() -> None:
    """The night designates by weight, and a wolf answers with names (D-008)."""
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng)
    wolf = next(player for player in state.players if player.role.value == "werewolf")
    night = state.entering(Phase.DAY, day=1).entering(Phase.RESOLUTION).entering(Phase.NIGHT)
    prey = next(player for player in night.living if player.role.value != "werewolf")
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Je pèse sur la plus discrète.",
                priorities=(
                    PriorityAnswer(target=prey.name, points=80),
                    PriorityAnswer(target="Personne-Qui-N-Existe-Pas", points=20),
                ),
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(night, wolf.id), ())

    played = turn.intent
    assert isinstance(played, SharePriority)
    assert played.allocations == (PriorityPoint(target=prey.id, points=80),), (
        "the invented prey is dropped"
    )


async def test_what_a_model_writes_is_cut_to_the_words_the_rules_allow() -> None:
    """D-021, applied by the engine: a prompt asking for brevity does not enforce it."""
    rng = create_rng(4)
    state = create_game(FORCED, rng=rng).entering(Phase.DAY, day=2)
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning=" ".join(f"mot{rank}" for rank in range(200)),
                notebook=(AddNote(note=" ".join(f"note{rank}" for rank in range(50))),),
                speech=" ".join(f"parole{rank}" for rank in range(200)),
                votes_blank=True,
            ).model_dump_json()
        ]
    )
    view = project(state, state.players[0].id)

    turn = await seated(provider).decide(view, ())

    played = turn.intent
    assert isinstance(played, TakeTurn)
    assert played.speech is not None
    assert len(played.speech.split()) == view.limits.speech_words
    assert played.speech.endswith("…"), "cut, and saying so"
    assert turn.reasoning is not None
    assert len(turn.reasoning.split()) == view.limits.analysis_words
    note = turn.notebook[0]
    assert isinstance(note, AddNote)
    assert len(note.note.split()) == view.limits.notebook_words


async def test_an_extravert_bids_higher_than_an_introvert_on_the_same_answer() -> None:
    """D-064: a temperament shifts the auction, it does not merely colour the prose."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    view = project(state, state.players[0].id)
    answered = json.dumps({"urgency": 50, "intention": "Parler."})

    outspoken = await seated(FakeCompletions(script=[answered]), Personality.ENFP).bid(view, ())
    reserved = await seated(FakeCompletions(script=[answered]), Personality.INTJ).bid(view, ())

    assert outspoken.urgency > reserved.urgency


async def test_an_urgency_never_leaves_its_scale_whatever_the_temperament() -> None:
    """The bias is applied to a number the auction reads, so it stays a number it can read."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    view = project(state, state.players[0].id)

    highest = await seated(
        FakeCompletions(script=[json.dumps({"urgency": 100, "intention": "Tout."})]),
        Personality.ENFP,
    ).bid(view, ())
    lowest = await seated(
        FakeCompletions(script=[json.dumps({"urgency": 0, "intention": "Rien."})]),
        Personality.INTJ,
    ).bid(view, ())

    assert (highest.urgency, lowest.urgency) == (100, 0)


async def test_a_note_a_model_strikes_out_survives_the_trimming_untouched() -> None:
    """A deletion carries no text, which is why it is its own type (D-005)."""
    state = create_game(FORCED, rng=create_rng(4)).entering(Phase.DAY, day=2)
    provider = FakeCompletions(
        script=[
            TurnAnswer(
                reasoning="Cette note ne vaut plus rien.",
                notebook=(DropNote(entry=2),),
                votes_blank=True,
            ).model_dump_json()
        ]
    )

    turn = await seated(provider).decide(project(state, state.players[0].id), ())

    assert turn.notebook == (DropNote(entry=2),)


def test_a_seat_says_which_model_it_bids_with() -> None:
    """Read by the console command, and by the spectator later (D-077)."""
    agent = seated(FakeCompletions())

    assert agent.bidding_model == "ministral-3b-latest"
