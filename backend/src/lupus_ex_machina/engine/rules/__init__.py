"""The rules a game is played by.

Six categories of the catalogue (D-069) live here rather than in
``configuration/``: they are what the *engine* reads, and the engine must stay
readable without knowing which model sits in which seat. The three remaining
categories — agents, display, system — are assembled around these ones by
:mod:`lupus_ex_machina.configuration.schema`.

One module per category, which is also how the user meets them in the
configuration screen: :mod:`table`, :mod:`roles`, :mod:`information`,
:mod:`debate`, :mod:`voting`, :mod:`night`.

Every default lives here and nowhere else (D-068). A caller that supplies none
gets the decided game; a caller that supplies one is not silently corrected.

Names, keys and enum values are English because they are code. Every
``description`` is French, because the JSON Schema carries it to the screen
(HR-6).
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.engine.rules.debate import DebateOptions
from lupus_ex_machina.engine.rules.information import InformationOptions
from lupus_ex_machina.engine.rules.night import NightOptions
from lupus_ex_machina.engine.rules.roles import RoleOptions
from lupus_ex_machina.engine.rules.table import GameMode, TableOptions
from lupus_ex_machina.engine.rules.voting import VoteOptions


class GameRules(BaseModel):
    """Everything the engine reads about how this game is played.

    Carried by :class:`~lupus_ex_machina.engine.state.GameState` rather than
    passed from call to call. The view handed to an agent is derived from the
    state alone, so rules known only to a caller would offer moves the validator
    refuses — the same reason ``runoff_targets`` lives in the state.
    """

    model_config = ConfigDict(frozen=True)

    table: TableOptions = Field(
        default_factory=TableOptions,
        title="Partie",
        description="Effectif, composition, graine, mode de jeu et siège du joueur humain.",
    )
    roles: RoleOptions = Field(
        default_factory=RoleOptions,
        title="Rôles",
        description="L'étendue des pouvoirs de chaque rôle, là où les règles laissent le choix.",
    )
    information: InformationOptions = Field(
        default_factory=InformationOptions,
        title="Information et visibilité",
        description="Ce que la table et les agents ont le droit d'apprendre.",
    )
    debate: DebateOptions = Field(
        default_factory=DebateOptions,
        title="Débat et parole",
        description="Les enchères de parole, leurs bonus et malus, et les limites de mots.",
    )
    vote: VoteOptions = Field(
        default_factory=VoteOptions,
        title="Vote",
        description="Le sort d'une égalité, et le moment où le meneur de jeu appelle le vote.",
    )
    night: NightOptions = Field(
        default_factory=NightOptions,
        title="Nuit",
        description="L'ordre des réveils, la désignation de la meute et son budget de points.",
    )


__all__ = [
    "DebateOptions",
    "GameMode",
    "GameRules",
    "InformationOptions",
    "NightOptions",
    "RoleOptions",
    "TableOptions",
    "VoteOptions",
]
