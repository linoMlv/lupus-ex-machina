"""Play a full game in the console, with scripted agents.

No model, no server, no network: this is what makes the rules cheap to exercise
(GL-2). Everything a game does comes from one seed, so a surprising game can be
replayed exactly.

Output is French because it is read on screen; the code around it is English
(HR-6).
"""

import argparse
import sys
from collections.abc import Sequence

from lupus_ex_machina.agents.scripted import RandomAgent
from lupus_ex_machina.engine.agent import Agent
from lupus_ex_machina.engine.players import PlayerId
from lupus_ex_machina.engine.rng import create_rng
from lupus_ex_machina.engine.roles import RoleName
from lupus_ex_machina.engine.runner import GameResult, play_game
from lupus_ex_machina.engine.setup import (
    MAXIMUM_PLAYERS,
    MINIMUM_PLAYERS,
    UnsupportedPlayerCountError,
    create_game,
)
from lupus_ex_machina.engine.state import GameState
from lupus_ex_machina.engine.victory import Outcome

# Keyed by the enum members rather than by their raw values, so a mistyped key is
# a type error. Completeness is not something a type checker can prove, so a test
# holds it: without it, a role added in J4 would only fail at the very end of a
# finished game, when the roles are revealed.
ROLE_LABELS: dict[RoleName, str] = {
    RoleName.VILLAGER: "villageois",
    RoleName.WEREWOLF: "loup-garou",
}
OUTCOME_LABELS: dict[Outcome, str] = {
    Outcome.VILLAGE_WINS: "Victoire du village",
    Outcome.WEREWOLVES_WIN: "Victoire des loups-garous",
}

DEFAULT_PLAYERS = 8
# Same default as the `play` target of the Makefile, so both entry points run
# the same game when no seed is given.
DEFAULT_SEED = 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run one game and report it. Returns the process exit code."""
    options = _parse_arguments(argv)

    rng = create_rng(options.seed)
    try:
        state = create_game(options.players, rng=rng)
    except UnsupportedPlayerCountError:
        print(
            f"Effectif non pris en charge : {options.players}. "
            f"La V1 accepte {MINIMUM_PLAYERS} à {MAXIMUM_PLAYERS} joueurs.",
            file=sys.stderr,
        )
        return 1

    agents: dict[PlayerId, Agent] = {player.id: RandomAgent(rng=rng) for player in state.players}

    _announce_table(state, seed=options.seed)
    _report(play_game(state, agents))
    return 0


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lupus-play",
        description="Joue une partie complète avec des agents scriptés, sans aucun modèle.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="graine de la partie")
    parser.add_argument(
        "--players",
        type=int,
        default=DEFAULT_PLAYERS,
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
