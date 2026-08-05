"""The rules a game is played by.

Six categories of the catalogue (D-069) live here rather than in
``configuration/``: they are what the *engine* reads, and the engine must stay
readable without knowing which model sits in which seat. The three remaining
categories — agents, display, system — are assembled around these ones by
:mod:`lupus_ex_machina.configuration.schema`.

Every default lives here and nowhere else (D-068). A caller that supplies none
gets the decided game; a caller that supplies one is not silently corrected.

Names, keys and enum values are English because they are code. Every
``description`` is French, because the JSON Schema carries it to the screen
(HR-6).
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lupus_ex_machina.engine.composition import Composition
from lupus_ex_machina.engine.roles import ROLES, RoleName


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


class RoleOptions(BaseModel):
    """What each role may do, where the rules leave a choice."""

    model_config = ConfigDict(frozen=True)

    seer_learns_exact_role: bool = Field(
        default=True,
        description="La voyante lit le rôle exact. Sinon, elle apprend seulement « loup ou non ».",
    )
    """The two make very different games, and the richer one is taken: the poorer
    is a deliberate handicap rather than an obvious default (D-031)."""

    speaking_seer: bool = Field(
        default=False,
        description="La voyante annonce publiquement ce qu'elle a lu, sans dire sur qui.",
    )
    """Off by default: it hands the village a great deal, and the option exists
    to be turned on knowingly (D-031)."""

    witch_may_save_herself: bool = Field(
        default=True,
        description="La sorcière peut se soigner elle-même quand la meute l'a désignée.",
    )
    """D-029 says she may. Turned off, the potion of life still exists but never
    reaches its owner, which is the classic handicap some tables play with."""

    hunter_must_shoot: bool = Field(
        default=True,
        description="Le tir du chasseur est obligatoire : sans cible, le moteur vise pour lui.",
    )
    """On by default, and "non-renounceable" is taken literally: a rule the
    agents could quietly opt out of would not be a rule (D-055)."""


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

    show_personalities: bool = Field(
        default=True,
        description="Le spectateur voit la personnalité MBTI de chaque agent.",
    )
    """On by default: a spectator already sees private reasoning and notebooks
    (D-064), so hiding the personality would be an odd place to stop."""


class DebateOptions(BaseModel):
    """What the floor costs, and what it is worth (D-002).

    Held in configuration rather than in the code because D-002 is explicit that
    these values are indicative and will have to be calibrated by playing.
    """

    model_config = ConfigDict(frozen=True)

    addressed_bonus: int = Field(
        default=25,
        ge=0,
        description="Bonus d'enchère pour un joueur que le dernier orateur interpellait.",
    )
    accused_bonus: int = Field(
        default=40,
        ge=0,
        description="Bonus d'enchère pour un joueur que le dernier orateur accusait.",
    )
    """Worth more than merely being talked to, and D-002 already said so: an
    answer owed to the whole table is more pressing than one owed to a person."""

    recency_penalty: int = Field(
        default=30,
        ge=0,
        description="Malus d'enchère pour celui qui vient de parler, qui s'estompe ensuite.",
    )
    """The anti-monopoly of D-002, and what makes a debate move: the surest way
    to lose the next auction is to have won the last one."""

    recency_window: int = Field(
        default=3,
        ge=1,
        description="Nombre de tours au bout desquels le malus de récence est retombé à zéro.",
    )
    word_quota: int = Field(
        default=300,
        ge=0,
        description=(
            "Nombre de mots qu'un joueur peut dépenser dans la journée avant d'être pénalisé."
        ),
    )
    quota_penalty: int = Field(
        default=50,
        ge=0,
        description="Malus d'enchère appliqué une fois le quota de mots du jour dépassé.",
    )
    """Answers the verbosity of language models with something other than a
    truncation: a player who has said a great deal has to want the floor markedly
    more than one who has been listening."""

    minimum_urgency: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Urgence en dessous de laquelle une enchère n'emporte pas la parole.",
    )
    """Zero is today's behaviour exactly, and that is deliberate: a rule of the
    game is not created in a jalon about configuration. Above zero, a round where
    nobody bids hard enough is a debate that has run out (D-060)."""

    waiting_allowed: bool = Field(
        default=True,
        description="Un joueur peut ne rien faire de son tour : ni parler, ni voter.",
    )
    """D-048 makes waiting legal, and strategically sound. Turned off, a table
    can no longer stall — at the price of the silence that says something."""

    turns_per_player_per_day: int = Field(
        default=5,
        ge=1,
        description="Nombre maximal de prises de parole par joueur et par journée.",
    )
    """A ceiling on model calls (GL-7), not a rule: a debate is meant to end when
    the last player votes (D-013), or when nobody has anything left to say."""

    speech_word_limit: int = Field(
        default=50,
        ge=1,
        description="Nombre maximal de mots d'une prise de parole.",
    )
    analysis_word_limit: int = Field(
        default=40,
        ge=1,
        description="Nombre maximal de mots d'une analyse privée.",
    )
    notebook_word_limit: int = Field(
        default=20,
        ge=1,
        description="Nombre maximal de mots d'une note de carnet.",
    )


class VoteOptions(BaseModel):
    """How a round is closed.

    The blank vote is not an option here, and cannot be: Day 1 has no other way
    out (D-032), so switching it off would describe a game with no legal move.
    """

    model_config = ConfigDict(frozen=True)

    hold_a_runoff_on_a_tie: bool = Field(
        default=True,
        description=(
            "Une égalité rouvre le vote une fois, sans débat, entre les seuls ex æquo. "
            "Sinon, une égalité n'élimine personne."
        ),
    )
    turns_before_forced_vote: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Nombre de prises de parole avant que le meneur de jeu ne déclenche le vote. "
            "Vide, le débat n'est pas écourté."
        ),
    )


class NightOptions(BaseModel):
    """How the night is run."""

    model_config = ConfigDict(frozen=True)

    require_werewolf_target: bool = Field(
        default=False,
        description="La meute doit repartir avec une victime ; à défaut, elle est tirée au sort.",
    )
    """False by default: the rules do not force a designation, and a game that
    does not progress is an admitted state rather than a bug (D-078)."""

    priority_budget: int = Field(
        default=100,
        ge=1,
        description="Points qu'un loup répartit entre les proies pour peser sur la désignation.",
    )
    """A ceiling rather than a quota (D-008): spending less is legal, and costs
    influence."""

    hold_a_runoff_on_a_tie: bool = Field(
        default=True,
        description=(
            "Une égalité entre proies rouvre la désignation une fois, entre les seules ex æquo."
        ),
    )
    wake_order: tuple[RoleName, ...] = Field(
        default=(RoleName.SEER, RoleName.WEREWOLF, RoleName.WITCH),
        description="Ordre dans lequel la nuit appelle les rôles.",
    )
    """A sequence rather than ranks: the order *is* the position, so there is no
    numbering to keep in agreement with itself. The registry no longer holds one
    (D-010) — two places giving the rank end up disagreeing."""

    @model_validator(mode="after")
    def _calls_every_role_that_wakes_exactly_once(self) -> Self:
        """Refuse an order that leaves a role out, or calls one twice.

        A role that acts at night and is never called would hold a power the
        game never offers it — an incoherent table rather than a variant.
        """
        called = list(self.wake_order)
        if len(set(called)) != len(called):
            raise ValueError("Un rôle ne peut être appelé qu'une fois dans la nuit")

        expected = {role for role, declared in ROLES.items() if declared.wakes_at_night}
        if set(called) != expected:
            missing = sorted(expected - set(called))
            extra = sorted(set(called) - expected)
            raise ValueError(
                f"L'ordre de réveil doit appeler exactement les rôles qui se réveillent "
                f"(manquants : {missing}, en trop : {extra})"
            )
        return self

    @model_validator(mode="after")
    def _wakes_the_witch_after_the_pack(self) -> Self:
        """Refuse a night that shows the witch a prey nobody has chosen yet.

        She is told whom the pack took and may pour her potion of life on them
        (D-029). Woken first, she would be asked to answer a question that has
        not been put — which is not a variant of the rules but a broken one.
        """
        called = list(self.wake_order)
        if called.index(RoleName.WITCH) < called.index(RoleName.WEREWOLF):
            raise ValueError(
                "La sorcière voit la proie de la meute : elle est réveillée après elle"
            )
        return self


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
