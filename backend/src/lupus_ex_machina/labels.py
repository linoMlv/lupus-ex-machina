"""What the things of the game are called, in French.

Read on screen and read by the models, which is exactly what HR-6 allows French
for. Kept in one place because there is no version of this project where the
console and the prompts may disagree on what a role is called.

Indexed by the enum members rather than by their raw values, so a mistyped key
is a type error. Completeness is not something a type checker can prove, so
tests hold it.
"""

from lupus_ex_machina.engine.phases import Phase
from lupus_ex_machina.engine.roles import RoleActionName, RoleName
from lupus_ex_machina.engine.victory import Outcome

ROLE_LABELS: dict[RoleName, str] = {
    RoleName.VILLAGER: "villageois",
    RoleName.WEREWOLF: "loup-garou",
    RoleName.SEER: "voyante",
    RoleName.WITCH: "sorcière",
    RoleName.HUNTER: "chasseur",
}

OUTCOME_LABELS: dict[Outcome, str] = {
    Outcome.VILLAGE_WINS: "Victoire du village",
    Outcome.WEREWOLVES_WIN: "Victoire des loups-garous",
}

PHASE_LABELS: dict[Phase, str] = {
    Phase.NIGHT_ZERO: "la nuit d'ouverture",
    Phase.DAY: "le jour",
    Phase.NIGHT: "la nuit",
    Phase.RESOLUTION: "la résolution",
    Phase.AVENGING_SHOT: "le tir du chasseur",
    Phase.ENDED: "la fin de la partie",
}

ACTION_LABELS: dict[RoleActionName, str] = {
    RoleActionName.DEVOUR: "dévorer",
    RoleActionName.INSPECT: "sonder",
    RoleActionName.HEAL: "sauver avec ta potion de vie",
    RoleActionName.POISON: "empoisonner avec ta potion de mort",
    RoleActionName.SHOOT: "tirer sur",
}
