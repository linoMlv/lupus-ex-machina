# Lupus Ex Machina

> Un simulateur de parties de Loup-Garou jouées par des agents LLM autonomes, rendu en 3D lowpoly.

Chaque joueur est un agent qui reçoit un rôle, les règles du jeu et celles du système, puis joue une
partie complète sans supervision : débat diurne, votes, actions nocturnes. Avant d'agir, il analyse
la situation pour lui-même et tient un carnet privé de déductions.

L'objectif n'est pas de faire « tourner » une partie, mais de produire une **dynamique sociale
crédible** — prise de parole spontanée, réactions à chaud, mensonge, coordination secrète.

---

## Ce qui distingue le projet

**La parole n'est pas un tour de rôle.** Un LLM ne veut rien tant qu'on ne lui demande rien.
Après chaque prise de parole, tous les agents évaluent à bas coût leur envie de parler — une urgence
de 0 à 100 assortie d'une intention courte — et le moteur arbitre avec des bonus (être interpellé
nommément, être accusé) et des malus (avoir monopolisé la parole). Ceux qui n'ont rien à dire se
taisent, et ce silence devient lui-même une information sociale.

**Voter coûte le droit de parole.** Il n'y a pas de chronomètre. Un joueur qui vote perd
définitivement sa parole pour le tour, et le tour se clôt quand tout le monde a voté. Voter devient
un arbitrage : verrouiller le débat au prix de son silence, ou continuer à parler en le laissant
ouvert. On sait toujours *qui* a voté, jamais *pour qui* avant le dépouillement.

**La scène se lit sans qu'on ait à lire.** Les têtes se tournent vers celui qui parle. Un joueur
nommé sursaute. Au dépouillement, tous les regards convergent simultanément vers leur cible et le
graphe d'accusation devient visible en une seconde. À chaque mort, un lampadaire s'éteint, le cercle
se resserre autour du brasero, et un fantôme de plus regarde depuis la périphérie.

---

## Modes

| Mode | Description |
|---|---|
| **Spectateur** | Vue omnisciente : paroles, pensées internes, carnets, votes secrets, canal privé des loups. |
| **Joueur** | Vous incarnez un personnage et ne voyez que l'information publique. Un bouton pour demander la parole, un autre pour la prendre en priorité juste après quelqu'un. |

## Rôles

Villageois, loup-garou, voyante, sorcière, chasseur — de 6 à 8 joueurs.

Presque tout est configurable avant la partie : composition, révélation des rôles à la mort,
visibilité de l'historique des votes, ce que la voyante apprend, règles d'égalité, limites de mots,
modèle et personnalité de chaque siège.

---

## État du projet

**En cours de développement.** La conception est terminée — architecture, règles, direction
artistique — et l'implémentation démarre. Le dépôt ne contient pour l'instant que les assets 3D.

## Stack

**Backend** — Python, asyncio, FastAPI, Pydantic
**Frontend** — TypeScript, React, Vite, three.js
**Modèles** — n'importe quelle API compatible OpenAI

---

## Crédits

Les assets 3D proviennent des packs [Kenney](https://kenney.nl) *Mini Characters*,
*Graveyard Kit* et *Mini Forest*, publiés en **CC0**.

## Licence

Ce projet est distribué sous **[EUPL v1.2](LICENSE)** (European Union Public Licence).
