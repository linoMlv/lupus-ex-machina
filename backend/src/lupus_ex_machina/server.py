"""Console entry point serving the application.

The ASGI application is built once and handed to uvicorn as an object rather
than an import string: there is no reload in production, and building it here
keeps the settings resolution in a single place.
"""

import uvicorn

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import Settings


def main() -> None:
    """Read the settings from the environment and serve the application."""
    settings = Settings()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
