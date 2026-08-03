"""Application factory.

Everything is built through :func:`create_app` rather than a module-level
instance, so tests can build as many independent applications as they need,
each with its own settings.
"""

from fastapi import FastAPI

from lupus_ex_machina import __version__
from lupus_ex_machina.api import health
from lupus_ex_machina.config import Settings
from lupus_ex_machina.web import static


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application serving the API, the models and the front end."""
    settings = settings or Settings()

    app = FastAPI(
        title="Lupus Ex Machina",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings

    app.include_router(health.router)

    # Order matters: the front end mount answers every path left, so it comes last.
    static.mount_models(app, settings.models_dir)
    static.mount_frontend(app, settings.frontend_dist)

    return app
