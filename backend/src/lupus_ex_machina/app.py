"""Application factory.

Everything is built through :func:`create_app` rather than a module-level
instance, so tests can build as many independent applications as they need,
each with its own settings.
"""

from fastapi import FastAPI

from lupus_ex_machina import __version__
from lupus_ex_machina.api import auth, games, health, stream
from lupus_ex_machina.config import Settings
from lupus_ex_machina.hosting import GameHost
from lupus_ex_machina.hosting.host import Provider
from lupus_ex_machina.llm.provider import provider_for
from lupus_ex_machina.web import static


def create_app(settings: Settings | None = None, *, provider: Provider | None = None) -> FastAPI:
    """Build the ASGI application serving the API, the models and the front end.

    A way of building a provider may be handed in, which is what lets a whole
    game be played in a test without reaching anything (GL-2). Left alone, the
    application builds the real client from the settings — and hosts nothing at
    all when there is no key, rather than dealing a table it could never play
    (D-090).
    """
    settings = settings or Settings()

    app = FastAPI(
        title="Lupus Ex Machina",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.host = hosting_with(settings, provider)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(games.router)
    app.include_router(stream.router)

    # Order matters: the front end mount answers every path left, so it comes last.
    static.mount_models(app, settings.models_dir)
    static.mount_frontend(app, settings.frontend_dist)

    return app


def hosting_with(settings: Settings, provider: Provider | None) -> GameHost | None:
    """The host this application plays games through, or nothing.

    Nothing when there is no way to play: an application without a key hosts no
    game at all, rather than dealing a table and discovering on start that
    nobody can answer for it (D-090).

    What the host is handed is a *way* of building a provider rather than one,
    because how a client waits is a setting of the game it plays (D-092) — and
    at start-up there is no game to read a policy from.
    """
    if provider is not None:
        return GameHost(provider=provider)

    build = provider_for(settings)
    return GameHost(provider=build) if build is not None else None
