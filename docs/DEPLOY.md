# Déploiement

Le projet se déploie comme **une seule image Docker** : un unique conteneur sert l'API, l'interface
et les modèles 3D. Il n'y a ni base de données, ni second service, ni reverse proxy à configurer.

---

## 1. Construire et vérifier l'image en local

```bash
make build-image     # docker build -t lupus-ex-machina .
make check-image     # construit, démarre, et vérifie /health, l'interface et un modèle GLB
```

`make check-image` échoue avec un code de sortie non nul si le conteneur n'atteint pas l'état
`healthy`, si `/health` ne répond pas `{"status":"ok"}`, si la racine ne sert pas l'interface, ou si
un GLB n'est pas servi avec le type MIME `model/gltf-binary`.

---

## 2. Variables d'environnement

Toutes les variables sont préfixées par `LUPUS_`. Toutes ont un défaut utilisable — à deux exceptions près : `LUPUS_PASSWORD`, sans lequel **personne ne peut entrer**, et `LUPUS_LLM_API_KEY`, sans laquelle aucune partie ne peut être jouée par des modèles. L'image fixe déjà
les valeurs nécessaires à son propre agencement. Le modèle complet est dans
[`.env.example`](../.env.example).

| Variable | Valeur dans l'image | Rôle |
|---|---|---|
| `LUPUS_HOST` | `0.0.0.0` | Interface d'écoute. **Ne pas mettre `127.0.0.1`** dans un conteneur : le service deviendrait injoignable de l'extérieur. |
| `LUPUS_PORT` | `8000` | Port d'écoute. À aligner avec le port exposé si la plateforme en impose un autre. |
| `LUPUS_LOG_LEVEL` | `info` | `critical`, `error`, `warning`, `info`, `debug` ou `trace`. |
| `LUPUS_FRONTEND_DIST` | `/app/frontend/dist` | Interface compilée. Si le chemin est absent, l'API démarre quand même mais **ne sert plus l'interface**. |
| `LUPUS_MODELS_DIR` | `/app/assets` | Modèles GLB exposés sous `/models`. |
| `LUPUS_PASSWORD` | *(vide)* | Mot de passe derrière lequel l'application est cachée (D-045). **Laissé vide, personne n'entre** : oublier de le définir ferme la porte plutôt que de l'ouvrir. Gardé en clair, il n'y a qu'un utilisateur et vous détenez déjà le secret. |
| `LUPUS_SECRET_KEY` | *(tirée au démarrage)* | **Deux usages, et deux exigences différentes.** Elle signe le cookie de session : non définie, une clé est tirée à chaque démarrage, ce qui déconnecte tout le monde au redémarrage. Mais elle chiffre aussi les **clés d'API des fournisseurs** : tant qu'elle est vide, **enregistrer un fournisseur est refusé** — une clé chiffrée avec un secret tiré au démarrage serait illisible au redémarrage suivant. **À définir avant d'ajouter le moindre fournisseur.** N'importe quelle longue chaîne aléatoire convient ; **la changer rend illisibles les clés déjà enregistrées**, qu'il faut alors ressaisir. |
| `LUPUS_LLM_API_KEY` | *(vide)* | Clé du fournisseur compatible OpenAI. **Le seul secret du projet** : à définir dans la plateforme, jamais dans l'image ni dans le dépôt. Sans elle, aucune partie ne peut être jouée par des modèles. |
| `LUPUS_LLM_BASE_URL` | `https://api.mistral.ai/v1` | Endpoint du fournisseur. Mistral est consommé par son API compatible OpenAI ; tout endpoint compatible convient. |

> **Aucun secret n'est nécessaire à ce stade.** Les clés d'API des modèles de langage seront
> introduites au jalon J7, et devront être fournies **comme variables d'exécution** — jamais comme
> arguments de build, qui resteraient lisibles dans l'historique des couches de l'image.

---

## 3. Déploiement sur Coolify

1. **Créer une ressource** de type *Application* → *Dockerfile*, pointant sur le dépôt et la
   branche à déployer.
2. **Laisser Coolify construire depuis le `Dockerfile`** à la racine. Aucun `docker-compose` n'est
   nécessaire.
3. **Port exposé : `8000`.** Si Coolify injecte un autre port, définir `LUPUS_PORT` avec la même
   valeur — le `HEALTHCHECK` de l'image lit cette variable.
4. **Variables d'environnement** : aucune n'est obligatoire. N'en ajouter que pour s'écarter du
   tableau ci-dessus.
5. **Domaine et HTTPS** : gérés par Coolify via son proxy. L'application ne termine pas le TLS.
6. **Sonde de santé** : `GET /health`. L'image embarque déjà un `HEALTHCHECK` équivalent, visible
   avec `docker inspect`.

---

## 4. Vérifier un déploiement

```bash
curl https://<domaine>/health          # attendu : {"status":"ok"}
curl -I https://<domaine>/             # attendu : 200, text/html
```

Et dans un navigateur, la racine doit afficher la page d'accueil de Lupus Ex Machina.

---

## 5. Diagnostic

| Symptôme | Cause probable |
|---|---|
| Le conteneur reste `unhealthy` | Le port réel diffère de `LUPUS_PORT` : la sonde interroge le mauvais port. |
| `/health` répond mais la racine renvoie 404 | `LUPUS_FRONTEND_DIST` pointe sur un répertoire sans `index.html`. Les journaux du démarrage le signalent explicitement. |
| Les modèles 3D ne se chargent pas | `LUPUS_MODELS_DIR` est absent, ou le chemin demandé n'est pas encodé — les répertoires des packs Kenney contiennent une espace (`GLB format` → `GLB%20format`). |
| Le service est injoignable alors que le conteneur tourne | `LUPUS_HOST` vaut `127.0.0.1` au lieu de `0.0.0.0`. |
