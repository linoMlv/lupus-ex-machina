"""Who sits at the table, and which game is being dealt."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lupus_ex_machina.engine.composition import Composition


class GameMode(StrEnum):
    """Whether the user watches the game or sits at the table (D-045)."""

    SPECTATOR = "spectator"
    PLAYER = "player"


class TableOptions(BaseModel):
    """Who sits at the table, and which game is being dealt."""

    model_config = ConfigDict(frozen=True)

    player_count: int = Field(
        default=8,
        ge=6,
        le=8,
        description="Nombre de joueurs à la table (6 à 8 en V1).",
    )
    composition: Composition | None = Field(
        default=None,
        description=(
            "Composition personnalisée. Vide, la table reçoit la composition "
            "par défaut de son effectif."
        ),
    )
    seed: int = Field(
        default=1,
        description="Graine de la partie. Deux parties de même graine se déroulent à l'identique.",
    )
    mode: GameMode = Field(
        default=GameMode.SPECTATOR,
        description="Spectateur : la partie se joue seule. Joueur : vous occupez un siège.",
    )
    human_seat: int | None = Field(
        default=None,
        ge=0,
        description="Siège occupé par le joueur humain, en mode joueur uniquement.",
    )

    @model_validator(mode="after")
    def _seats_the_human_where_a_seat_exists(self) -> Self:
        """Refuse a human seat that no game would hand out.

        Checked on the model rather than on the field: a seat number is not
        wrong on its own, it is wrong for the mode and the table it comes with.
        """
        if self.mode is GameMode.PLAYER and self.human_seat is None:
            raise ValueError("En mode joueur, il faut dire quel siège vous occupez")
        if self.mode is GameMode.SPECTATOR and self.human_seat is not None:
            raise ValueError("En mode spectateur, personne n'occupe de siège")
        if self.human_seat is not None and self.human_seat >= self.player_count:
            raise ValueError(
                f"Le siège {self.human_seat} n'existe pas à une table de {self.player_count}"
            )
        return self

    @model_validator(mode="after")
    def _deals_a_composition_that_fills_the_table(self) -> Self:
        """Refuse a composition that does not seat exactly this many players.

        A composition is one role per seat, so a table of eight dealt six roles
        describes two games. Left to the deal, one of the two numbers would win
        silently — and the other would be what the user thought they had set.
        """
        if self.composition is not None and self.composition.size != self.player_count:
            raise ValueError(
                f"La composition donne {self.composition.size} rôles "
                f"pour {self.player_count} joueurs"
            )
        return self
