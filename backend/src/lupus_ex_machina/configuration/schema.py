"""The root of the configuration schema.

One model, from which the front end derives its form and the engine reads its
rules (D-068). Field names, keys and enum values are English because they are
code; every ``description`` is French, because the JSON Schema carries it to the
screen (HR-6).
"""

from pydantic import BaseModel, ConfigDict, Field

from lupus_ex_machina.configuration.agents import AgentOptions
from lupus_ex_machina.configuration.display import DisplayOptions
from lupus_ex_machina.configuration.system import SystemOptions
from lupus_ex_machina.engine.rules import GameRules

#: Version of the schema itself. A saved template carries the version it was
#: written under, so a template that outlives a change is refused rather than
#: read wrongly.
CONFIGURATION_VERSION = 1


class GameConfiguration(BaseModel):
    """Everything a game can be set to.

    Nine categories (D-069), in two groups. ``rules`` gathers the six the engine
    reads and is what a game is handed; the other three are read by J7, J10 and
    J11. The grouping is what keeps the engine from having to know which model
    sits in which seat in order to read a rule of the vote.
    """

    model_config = ConfigDict(frozen=True)

    version: int = Field(
        default=CONFIGURATION_VERSION,
        description="Version du schéma de configuration sous laquelle ce réglage a été écrit.",
    )
    rules: GameRules = Field(
        default_factory=GameRules,
        title="Règles de la partie",
        description=(
            "Les six catégories que le moteur lit : table, rôles, information, débat, vote, nuit."
        ),
    )
    agents: AgentOptions = Field(
        default_factory=AgentOptions,
        title="Agents",
        description="Les modèles et les personnalités qui occupent les sièges.",
    )
    display: DisplayOptions = Field(
        default_factory=DisplayOptions,
        title="Affichage et rythme",
        description="Le rythme des bulles et les effets de la mise en scène.",
    )
    system: SystemOptions = Field(
        default_factory=SystemOptions,
        title="Système",
        description="Les réglages techniques : fenêtres de contexte, débit, journalisation.",
    )
