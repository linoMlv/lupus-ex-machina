"""Play a full game in the console, with scripted agents.

No model, no server, no network: this is what makes the rules cheap to exercise
(GL-2). Everything a game does comes from one seed, so a surprising game can be
replayed exactly.

Output is French because it is read on screen; the code around it is English
(HR-6).
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.composition import (
    MAXIMUM_PLAYERS,
    MINIMUM_PLAYERS,
    UnsupportedPlayerCountError,
)
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.rules import GameRules, TableOptions
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import create_game
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.labels import OUTCOME_LABELS, ROLE_LABELS

# The table this command deals when the user says nothing. Read from the schema
# rather than restated: the defaults of a game live in one place (D-068), and the
# `play` target of the Makefile leans on the same ones.
DEFAULTS = TableOptions()


def main(argv: Sequence[str] | None = None) -> int:
    """Run one game and report it. Returns the process exit code."""
    options = _parse_arguments(argv)

    rng = create_rng(options.seed)
    try:
        rules = GameRules(table=TableOptions(player_count=options.players, seed=options.seed))
        state = create_game(rules, rng=rng)
    except (UnsupportedPlayerCountError, ValidationError):
        print(
            f"Effectif non pris en charge : {options.players}. "
            f"La V1 accepte {MINIMUM_PLAYERS} à {MAXIMUM_PLAYERS} joueurs.",
            file=sys.stderr,
        )
        return 1

    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}

    _announce_table(state, seed=options.seed)
    # The engine runs on a loop (D-087); a console command is the one caller
    # that has to open one.
    _report(asyncio.run(play_game(state, agents)))
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lupus-play",
        description="Joue une partie complète avec des agents scriptés, sans aucun modèle.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULTS.seed, help="graine de la partie")
    parser.add_argument(
        "--players",
        type=int,
        default=DEFAULTS.player_count,
        help=f"nombre de joueurs ({MINIMUM_PLAYERS} à {MAXIMUM_PLAYERS})",
    )
    return parser.parse_args(argv)


def _announce_table(state: GameState, *, seed: int) -> None:
    """Announce the table as a player would see it: names, no roles."""
    print(f"Partie de {len(state.players)} joueurs — graine {seed}")
    print("Nuit 0 : tout le monde s'observe, personne n'agit.")
    print("Jour 1 : le débat s'ouvre, seul le vote blanc est possible.\n")

    print("À la table :")
    for player in state.players:
        print(f"  siège {player.seat} · {player.name}")
    print()


def _report(result: GameResult) -> None:
    """Report the end of the game, revealing the roles only now."""
    print(f"{OUTCOME_LABELS[result.outcome]} après {result.rounds} tours.")
    print(f"Intentions refusées par le moteur : {result.rejected_intents}.")
    print()

    print("Rôles :")
    for player in result.state.players:
        fate = "survit" if player.alive else "meurt"
        print(f"  {player.name} — {ROLE_LABELS[player.role]} — {fate}")
