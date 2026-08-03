"""Lupus Ex Machina — a werewolf simulator played by autonomous LLM agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lupus-ex-machina")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
