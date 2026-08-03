"""Static serving of the front-end build and of the 3D models.

Both mounts are optional: a backend started without a front-end build, or
without the asset directory, must still boot and answer the API. Only the
corresponding routes disappear.
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

logger = logging.getLogger(__name__)

MODELS_ROUTE = "/models"
GLTF_BINARY_MEDIA_TYPE = "model/gltf-binary"
GLB_SUFFIX = ".glb"

# Models never change in place: a new model is a new file. Caching them for a
# year keeps reloads from pulling megabytes of GLB over and over.
MODELS_CACHE_CONTROL = "public, max-age=31536000, immutable"


class ModelFiles(StaticFiles):
    """Static files serving GLB models with an explicit media type and a long cache.

    Python already maps ``.glb`` to ``model/gltf-binary``, but that table can be
    shadowed by the system MIME files of the host. A browser rejects a model
    served under the wrong type, and the failure surfaces far from its cause, so
    the header is set here rather than trusted.
    """

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        """Return the file response, with the model headers enforced."""
        response = super().file_response(full_path, stat_result, scope, status_code)
        if response.status_code != 200:  # a 304 must not carry entity headers
            return response
        if Path(full_path).suffix.lower() == GLB_SUFFIX:
            response.headers["content-type"] = GLTF_BINARY_MEDIA_TYPE
        response.headers["cache-control"] = MODELS_CACHE_CONTROL
        return response


def mount_models(app: FastAPI, models_dir: Path) -> bool:
    """Expose the 3D models under ``/models``. Returns whether they were mounted."""
    if not models_dir.is_dir():
        logger.warning("Aucun modèle 3D servi : le répertoire %s est introuvable.", models_dir)
        return False

    app.mount(MODELS_ROUTE, ModelFiles(directory=models_dir), name="models")
    return True


def mount_frontend(app: FastAPI, frontend_dist: Path) -> bool:
    """Serve the front-end build at the root. Returns whether it was mounted.

    This mount must be registered last: it answers every remaining path.
    """
    if not (frontend_dist / "index.html").is_file():
        logger.warning(
            "Aucune interface servie : le build front est introuvable dans %s. "
            "Lancez « make build-frontend », ou utilisez le serveur de développement Vite.",
            frontend_dist,
        )
        return False

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return True
