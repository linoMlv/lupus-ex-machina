"""What the table, and the agents, are allowed to learn.

Every option here decides whether a fact is *produced*, never who may read one:
the audience belongs to the fact itself (D-009). That is the shape an
information setting has to take on this project.
"""

from pydantic import BaseModel, ConfigDict, Field


class InformationOptions(BaseModel):
    """What the table, and the agents, are allowed to learn."""

    model_config = ConfigDict(frozen=True)

    reveal_role_on_death: bool = Field(
        default=True,
        description="Le rôle d'un joueur qui meurt est annoncé à toute la table.",
    )
    """On by default, as classic Werewolf plays it: the role of the deceased is
    the main engine of information the village works with, and a table that
    learns nothing from its dead deduces very little (D-080, settled by the
    project owner on 2026-08-05).

    Death itself is never configurable: it is always public. Only what the
    deceased *was* may be kept back, which is what makes the ghosts of J10 safe
    to keep on stage (D-072)."""

    reveal_ballots_at_the_count: bool = Field(
        default=True,
        description="Au dépouillement, la table apprend qui a voté contre qui.",
    )
    """Who voted is public in real time and whom they named is not (D-051); the
    count is where that ends. Revealing it is the direct counter to models voting
    in herds, and the moment the staging of J10 is built on (D-013, D-082)."""

    reveal_priorities_at_the_designation: bool = Field(
        default=True,
        description="Une fois la proie désignée, la meute apprend combien chacun a mis sur qui.",
    )
    """The night's counterpart to the count of the day (D-082). The wolves
    spread their points blind (D-085), so this is what lets a pack coordinate
    from one night to the next — without ever being able to answer a spread
    while it could still be answered."""

    public_vote_history: bool = Field(
        default=True,
        description="L'historique des votes des tours passés reste accessible aux agents.",
    )

    reveal_everything_to_the_dead: bool = Field(
        default=True,
        description="Une fois mort, le joueur voit toute la partie, y compris ce qu'il a manqué.",
    )
    """The custom of Werewolf, and the same reading of D-080 the project owner
    already chose for the role of the deceased (D-105). It covers the *whole*
    journal, the nights never seen included: the recipient becomes the spectator,
    and a projection filters the whole sequence with it. Showing only what comes
    after would need a second filtering rule, and would have a player watch
    others react to facts they will never see.

    It is not a way round the mode being fixed at creation (D-100): the game
    decides this, never the client."""

    show_personalities: bool = Field(
        default=True,
        description="Le spectateur voit la personnalité MBTI de chaque agent.",
    )
    """On by default: a spectator already sees private reasoning and notebooks
    (D-064), so hiding the personality would be an odd place to stop."""
