#!/usr/bin/env bash
#
# Build the production image, run it, and prove it actually serves the
# application: the health probe answers, the container reaches the healthy
# state, the front end is served, and a GLB model comes back with the right
# media type.
#
# Usage: scripts/check-image.sh [image-tag] [container-name]

set -euo pipefail

IMAGE="${1:-lupus-ex-machina}"
CONTAINER="${2:-lupus-ex-machina-check}"
HOST_PORT="${HOST_PORT:-8099}"
# The Kenney packs use directory names with a space, so the path is written
# percent-encoded here: curl does not encode it for us.
KNOWN_MODEL="kenney_graveyard-kit_5.0/Models/GLB%20format/fire-basket.glb"
REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[31mÉCHEC : %s\033[0m\n' "$1" >&2; exit 1; }

cleanup() {
    docker rm --force "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cd "$REPOSITORY_ROOT"

step "Construction de l'image $IMAGE"
docker build --tag "$IMAGE" .

step "Démarrage du conteneur sur le port $HOST_PORT"
cleanup
docker run --detach --name "$CONTAINER" --publish "$HOST_PORT:8000" "$IMAGE" >/dev/null

step "Attente de l'état healthy (HEALTHCHECK du conteneur)"
for _ in $(seq 1 60); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo unknown)"
    case "$status" in
        healthy) break ;;
        unhealthy) docker logs "$CONTAINER"; fail "le conteneur est passé unhealthy" ;;
    esac
    sleep 1
done
[ "${status:-}" = "healthy" ] || { docker logs "$CONTAINER"; fail "le conteneur n'est jamais devenu healthy"; }
printf 'état du conteneur : %s\n' "$status"

base_url="http://127.0.0.1:$HOST_PORT"

step "Vérification de GET /health"
health="$(curl --silent --show-error --fail "$base_url/health")"
[ "$health" = '{"status":"ok"}' ] || fail "réponse inattendue de /health : $health"
printf '/health -> %s\n' "$health"

step "Vérification du service de l'interface"
curl --silent --show-error --fail "$base_url/" | grep --quiet "Lupus Ex Machina" \
    || fail "la racine ne sert pas l'interface"
printf '/ -> interface servie\n'

step "Vérification du service des modèles 3D"
content_type="$(curl --silent --show-error --fail --output /dev/null \
    --write-out '%{content_type}' "$base_url/models/$KNOWN_MODEL")"
[ "$content_type" = "model/gltf-binary" ] || fail "type MIME inattendu pour un GLB : $content_type"
printf '/models/... -> %s\n' "$content_type"

step "Image vérifiée"
docker image inspect "$IMAGE" --format 'taille de l'"'"'image : {{.Size}} octets'
