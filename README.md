<div align="center">

# 🐺 Lupus Ex Machina

**Un simulateur de parties de Loup-Garou jouées par des agents LLM autonomes, rendu en 3D lowpoly.**

[![Statut](https://img.shields.io/badge/statut-en%20développement-orange?style=flat-square)](#état-du-projet)
[![Licence](https://img.shields.io/badge/licence-EUPL%20v1.2-1f5fa9?style=flat-square)](LICENSE)
[![Assets](https://img.shields.io/badge/assets-CC0-9a5fb0?style=flat-square)](#crédits)

[![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=flat-square&logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![three.js](https://img.shields.io/badge/three.js-000000?style=flat-square&logo=threedotjs&logoColor=white)](https://threejs.org)

*Huit intelligences artificielles s'accusent, mentent et votent autour d'un brasero.*

</div>

---

## Sommaire

- [Le concept](#le-concept)
- [Ce qui distingue le projet](#ce-qui-distingue-le-projet)
  - [La parole n'est pas un tour de rôle](#la-parole-nest-pas-un-tour-de-rôle)
  - [Voter coûte le droit de parole](#voter-coûte-le-droit-de-parole)
  - [La scène se lit sans qu'on ait à lire](#la-scène-se-lit-sans-quon-ait-à-lire)
- [Modes de jeu](#modes-de-jeu)
- [Rôles et configuration](#rôles-et-configuration)
- [Direction artistique](#direction-artistique)
- [État du projet](#état-du-projet)
- [Démarrage](#démarrage)
- [Stack technique](#stack-technique)
- [Origine du projet](#origine-du-projet)
- [Crédits](#crédits)
- [Licence](#licence)

---

## Le concept

Chaque joueur est un agent qui reçoit un rôle, les règles du jeu et celles du système, puis joue une
partie complète sans supervision : débat diurne, votes, actions nocturnes.

Avant d'agir, il **analyse la situation pour lui-même** — un monologue intérieur que personne
d'autre n'entend — et tient un **carnet privé** de déductions qu'il révise au fil de la partie.

L'objectif n'est pas de faire « tourner » une partie, mais de produire une **dynamique sociale
crédible** : prise de parole spontanée, réactions à chaud, mensonge, coordination secrète.

---

## Ce qui distingue le projet

### La parole n'est pas un tour de rôle

Un modèle de langage ne veut rien tant qu'on ne lui demande rien. Faire parler des agents chacun
leur tour produit une conversation morte.

Ici, après chaque prise de parole, **tous les agents enchérissent** : ils évaluent à bas coût leur
envie de parler — une urgence de 0 à 100 assortie d'une intention courte — et le moteur arbitre avec
des bonus (être interpellé nommément, être accusé) et des malus (avoir monopolisé la parole).

Ceux qui n'ont rien à dire se taisent. Et ce silence devient à son tour une information sociale.

### Voter coûte le droit de parole

Il n'y a pas de chronomètre. Un joueur qui vote **perd définitivement sa parole** pour le tour, et
le tour se clôt quand tout le monde a voté.

Voter devient donc un arbitrage : verrouiller le débat au prix de son propre silence, ou continuer à
parler en le laissant ouvert. On sait toujours **qui** a voté — jamais **pour qui** avant le
dépouillement. Voir qu'il ne reste que deux personnes à voter change la façon de jouer.

### La scène se lit sans qu'on ait à lire

Les têtes se tournent vers celui qui parle. Un joueur nommé dans une accusation sursaute.

Au dépouillement, **tous les regards convergent simultanément vers leur cible** : le graphe
d'accusation devient visible en une seconde.

Et à chaque mort, un lampadaire s'éteint, le cercle se resserre autour du brasero, un fantôme de plus
regarde depuis la périphérie. L'état de la partie se lit sans un seul chiffre à l'écran.

---

## Modes de jeu

| Mode | Description |
|:--|:--|
| **🔭 Spectateur** | Vue omnisciente. Paroles, pensées internes, carnets, votes secrets, canal privé des loups — tout est visible. |
| **🎭 Joueur** | Vous incarnez un personnage et ne voyez que l'information publique. Un bouton pour demander la parole, un autre pour la prendre en priorité juste après quelqu'un. |

L'étanchéité entre les deux modes est traitée comme une propriété testée, appliquée **côté serveur
avant émission** : en mode joueur, une information interdite ne transite jamais jusqu'au navigateur.

---

## Rôles et configuration

**Villageois · Loup-garou · Voyante · Sorcière · Chasseur** — de 6 à 8 joueurs.

Presque tout se règle avant la partie :

| Catégorie | Exemples d'options |
|:--|:--|
| **Partie** | Effectif, composition personnalisée, graine aléatoire |
| **Rôles** | Ce que la voyante apprend, voyante parlante, réveil de la sorcière sans potions, tir du chasseur obligatoire |
| **Information** | Révélation du rôle à la mort, historique des votes public, révélation des votes au dépouillement |
| **Débat** | Limites de mots, bonus et malus d'enchère, seuil d'urgence, garde-fous de fin de débat |
| **Agents** | Par siège : modèle d'enchère, modèle de génération, paramètres, personnalité MBTI |

Chaque siège peut tourner sur un modèle différent — de quoi créer des asymétries de compétence
volontaires, ou comparer deux modèles dans une même partie.

---

## Direction artistique

Une **place de village adossée au cimetière**, la nuit. Les joueurs forment un cercle autour d'un
brasero qui projette de longues ombres radiales.

Le rendu est en 3D lowpoly cartoon, dans un cadre contemporain assumé : dallage, lampadaires, bancs
et clôtures de fer au premier plan, cryptes et obélisques repoussés en silhouette dans la brume.

Pendant qu'un agent réfléchit, la caméra se rapproche de son visage, la scène s'assombrit, un
vignettage se referme — et l'on assiste à ses pensées.

> *Aucune capture d'écran pour l'instant : l'implémentation démarre.*

---

## État du projet

> **🚧 En cours de développement.**

La phase de conception est terminée — architecture, règles, direction artistique, plan
d'implémentation en douze jalons. Le développement suit une approche **TDD stricte**.

**Jalon 1 sur 12 terminé** : fondations du dépôt et chaîne de livraison. Le squelette applicatif
répond, l'interface et les modèles 3D sont servis, et l'image Docker se construit et se vérifie
d'une seule commande. Le moteur de jeu (jalon 2) est la prochaine étape.

---

## Démarrage

**Prérequis** : [uv](https://docs.astral.sh/uv/), Node 22 ou plus, et Docker pour l'image.

```bash
make install         # dépendances backend et frontend
make test            # suite de tests backend, avec couverture
make lint            # ruff, mypy strict, oxlint, prettier, tsc
```

Pour développer, deux processus : l'API d'un côté, Vite de l'autre — le serveur de développement
relaie vers l'API les chemins qui lui appartiennent.

```bash
make run             # API sur http://127.0.0.1:8000
make run-frontend    # interface sur http://127.0.0.1:5173, avec rechargement à chaud
```

Pour servir l'ensemble depuis un seul processus, comme en production :

```bash
make build-frontend  # compile l'interface dans frontend/dist
make run             # http://127.0.0.1:8000 sert l'API, l'interface et les modèles
```

Et pour l'image de production :

```bash
make check-image     # construit l'image, la démarre et vérifie qu'elle sert tout
```

`make help` liste toutes les cibles. Le déploiement est documenté dans
[`docs/DEPLOY.md`](docs/DEPLOY.md).

---

## Stack technique

| Couche | Technologies |
|:--|:--|
| **Backend** | Python · asyncio · FastAPI · Pydantic |
| **Frontend** | TypeScript · React · Vite · three.js |
| **Modèles** | Toute API compatible OpenAI |
| **Déploiement** | Image Docker, un seul conteneur |

---

## Origine du projet

**L'idée n'est pas de moi.** Elle vient de la vidéo
[**Ma simulation fait jouer 8 IA au Loup-Garou**](https://www.youtube.com/watch?v=dydilQuPREs)
du youtubeur **Elif TI**.

Ce dépôt en est une implémentation personnelle, avec ses propres choix de conception — notamment le
protocole d'enchères de parole et la règle du vote qui clôt le droit de parler.

---

## Crédits

Les assets 3D proviennent des packs [**Kenney**](https://kenney.nl) — *Mini Characters*,
*Graveyard Kit* et *Mini Forest* — publiés en **CC0**.

Douze personnages partageant un squelette commun et trente-deux animations, plus une centaine
d'éléments de décor.

---

## Licence

Ce projet est distribué sous **[EUPL v1.2](LICENSE)** — European Union Public Licence, une licence
copyleft compatible avec la GPL et l'AGPL.
