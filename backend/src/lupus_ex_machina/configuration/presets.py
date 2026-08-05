"""Configurations the application ships with (D-068).

Three games worth playing without setting anything up, so the form of J11 opens
on a choice rather than on forty controls.

Each preset is a *whole* configuration rather than a set of differences. A patch
would read better here and would drift the day a default moves: the preset that
"changes nothing" would quietly start changing something.

Names are keys and stay English; labels and summaries are read on screen and are
French (HR-6).
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.configuration.schema import GameConfiguration
from lupus_ex_machina.engine.rules import (
    GameRules,
    InformationOptions,
    NightOptions,
    RoleOptions,
    TableOptions,
)


class UnknownPresetError(Exception):
    """No preset of that name is shipped."""


class Preset(BaseModel):
    """One shipped configuration, and how to present it."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, description="Identifiant du préréglage.")
    label: str = Field(min_length=1, description="Nom affiché du préréglage.")
    summary: str = Field(min_length=1, description="Ce que ce préréglage change, en une phrase.")
    configuration: GameConfiguration = Field(description="La configuration complète, telle quelle.")


PRESETS: tuple[Preset, ...] = (
    Preset(
        name="classic",
        label="Partie classique",
        summary=(
            "Huit joueurs, deux loups, et tout ce que la table apprend d'ordinaire : "
            "le rôle des morts et le détail des votes."
        ),
        configuration=GameConfiguration(),
    ),
    Preset(
        name="initiation",
        label="Initiation",
        summary=(
            "Six joueurs et une voyante qui annonce ses lectures : le village part "
            "avec l'avantage, de quoi découvrir le jeu."
        ),
        configuration=GameConfiguration(
            rules=GameRules(
                table=TableOptions(player_count=6),
                roles=RoleOptions(speaking_seer=True),
            )
        ),
    ),
    Preset(
        name="dark_night",
        label="Nuit aveugle",
        summary=(
            "Les morts emportent leur rôle, les votes restent secrets, la voyante ne "
            "lit qu'« loup ou non » — et la meute repart toujours avec une victime."
        ),
        configuration=GameConfiguration(
            rules=GameRules(
                roles=RoleOptions(seer_learns_exact_role=False),
                information=InformationOptions(
                    reveal_role_on_death=False,
                    reveal_ballots_at_the_count=False,
                ),
                night=NightOptions(require_werewolf_target=True),
            )
        ),
    ),
)


def preset(name: str) -> Preset:
    """The shipped preset of that name."""
    for shipped in PRESETS:
        if shipped.name == name:
            return shipped
    raise UnknownPresetError(f"Le préréglage « {name} » est inconnu")
