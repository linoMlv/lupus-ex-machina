"""Play a full game in the console, with real models behind every seat.

The exit criterion of J7: a whole game, from Night 0 to a winner, with nobody
intervening. It is also the only thing in the project that reaches the network,
which is why it is a command rather than a test — the suite stays offline, free
and instant (GL-2, D-090).

What it reports at the end is the budget of the game: how many calls it took,
and how many of them were auctions. That is an acceptance criterion, not a
curiosity (GL-7).

Output is French because it is read on screen; the code around it is English
(HR-6).
"""

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence

from lupus_ex_machina.config import Settings
from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, NightOptions, TableOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.labels import OUTCOME_LABELS, ROLE_LABELS
from lupus_ex_machina.llm.agent import LlmAgent
from lupus_ex_machina.llm.client import ChatClient
from lupus_ex_machina.llm.completions import Completions
from lupus_ex_machina.llm.table import seat_agents

DEFAULTS = TableOptions()


def main(argv: Sequence[str] | None = None, *, completions: Completions | None = None) -> int:
    """Run one game against real models and report it. Returns the exit code.

    A provider may be handed in, which is what lets the wiring be tested without
    reaching anything: left alone, the command builds the real client from the
    settings.
    """
    options = _parse_arguments(argv)
    provider = completions if completions is not None else configured_provider(Settings())
    if provider is None:
        print(
            "Aucune clé d'API configurée. Renseignez LUPUS_LLM_API_KEY "
            "dans votre .env pour jouer avec de vrais modèles.",
            file=sys.stderr,
        )
        return 1

    configuration = GameConfiguration(rules=_rules_of(options))
    rng = create_rng(options.seed)
    state = create_game(configuration.rules, rng=rng)
    agents = seat_agents(
        state,
        configuration.agents,
        completions=provider,
        seed=options.seed,
        system=configuration.system,
    )

    _announce_table(state, agents, seed=options.seed)
    result = asyncio.run(play_game(state, dict(agents), rng=rng))
    _report(result, asked=_calls_made(provider))
    return 0


def configured_provider(settings: Settings) -> Completions | None:
    """The client the settings describe, or nothing when there is no key (D-090).

    Building it reaches nobody — a client is a base URL and a header until it is
    asked something — which is what lets this be tested without a network.
    """
    if settings.llm_api_key is None:
        return None
    return ChatClient(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def _rules_of(options: argparse.Namespace) -> GameRules:
    """The rules this run is played by, from the arguments it was given."""
    return GameRules(
        table=TableOptions(player_count=options.players, seed=options.seed),
        night=NightOptions(require_werewolf_target=options.forced_designation),
    )


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lupus-play-llm",
        description="Joue une partie complète avec de vrais modèles de langage.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULTS.seed, help="graine de la partie")
    parser.add_argument(
        "--players", type=int, default=DEFAULTS.player_count, help="nombre de joueurs"
    )
    parser.add_argument(
        "--forced-designation",
        action="store_true",
        help="la meute doit repartir avec une victime (sinon une partie peut ne pas avancer)",
    )
    return parser.parse_args(argv)


def _calls_made(completions: Completions) -> int:
    """How many times a model was asked something.

    Read off the provider rather than counted here: it is what knows, and a
    second tally would be a second thing to keep in agreement (GL-7).
    """
    return len(completions.asked)


def _announce_table(state: GameState, agents: Mapping[PlayerId, LlmAgent], *, seed: int) -> None:
    """Announce the table: names, models and temperaments, but never roles."""
    print(f"Partie de {len(state.players)} joueurs — graine {seed}")
    print("Nuit 0 : tout le monde s'observe, personne n'agit.\n")

    print("À la table :")
    for player in state.players:
        agent = agents[player.id]
        print(
            f"  siège {player.seat} · {player.name} — {agent.generation_model} "
            f"· {agent.personality.name}"
        )
    print()


def _report(result: GameResult, *, asked: int) -> None:
    """Report the end of the game, and what it cost to get there."""
    print(f"\n{OUTCOME_LABELS[result.outcome]} après {result.rounds} tours.")
    print(f"Intentions refusées par le moteur : {result.rejected_intents}.")
    print(f"Appels aux modèles : {asked}.")
    print()

    print("Rôles :")
    for player in result.state.players:
        fate = "survit" if player.alive else "meurt"
        print(f"  {player.name} — {ROLE_LABELS[player.role]} — {fate}")
