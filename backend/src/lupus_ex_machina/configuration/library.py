"""Configurations saved to come back to (D-068).

JSON files in a directory. V1 is one private game with one user (D-045), so a
folder is the whole of what is needed — no database, no accounts, nothing to
migrate.

Two guards, and both are about what a *user* hands over. A name is a name and
never a path, because the file system would happily honour ``../..``. And a
template carries the schema version it was written under, so one that outlives
a change is refused rather than quietly read as something else.
"""

import json
import re
from pathlib import Path

from pydantic import ValidationError

from lupus_ex_machina.configuration.schema import CONFIGURATION_VERSION, GameConfiguration

#: What a template may be called: a slug, and nothing that means anything to a
#: file system. Accented letters are in, because the names are French.
TEMPLATE_NAME = re.compile(r"^[\w-]{1,64}$", re.UNICODE)

SUFFIX = ".json"
ENCODING = "utf-8"


class TemplateError(Exception):
    """Something a saved configuration could not be asked to do."""


class InvalidTemplateNameError(TemplateError):
    """A name that would not stay inside the library."""


class UnknownTemplateError(TemplateError):
    """No template of that name was ever saved."""


class OutdatedTemplateError(TemplateError):
    """A template written under a schema this version no longer reads."""


class ConfigurationLibrary:
    """The saved configurations of this installation."""

    def __init__(self, directory: Path) -> None:
        """Hold the directory templates live in. It is created when first written to."""
        self._directory = directory

    def names(self) -> tuple[str, ...]:
        """Every saved template, in a stable order.

        Sorted rather than left to the file system: an order that wanders makes
        a list that reorders itself between two visits.
        """
        if not self._directory.is_dir():
            return ()
        return tuple(sorted(saved.stem for saved in self._directory.glob(f"*{SUFFIX}")))

    def save(self, name: str, configuration: GameConfiguration) -> None:
        """Write that configuration under that name, replacing what was there.

        Saving over is what editing a template *is*; the alternative would be
        two files of the same name with different contents.
        """
        path = self._path_of(name)
        self._directory.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(configuration.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding=ENCODING,
        )

    def load(self, name: str) -> GameConfiguration:
        """Read back the template of that name."""
        path = self._path_of(name)
        if not path.is_file():
            raise UnknownTemplateError(f"Le modèle de configuration « {name} » est introuvable")

        written = json.loads(path.read_text(encoding=ENCODING))
        self._ensure_this_version_reads_it(name, written)
        try:
            return GameConfiguration.model_validate(written)
        except ValidationError as invalid:
            raise TemplateError(
                f"Le modèle de configuration « {name} » n'est pas lisible : {invalid}"
            ) from invalid

    def delete(self, name: str) -> None:
        """Remove that template."""
        path = self._path_of(name)
        if not path.is_file():
            raise UnknownTemplateError(f"Le modèle de configuration « {name} » est introuvable")
        path.unlink()

    def _path_of(self, name: str) -> Path:
        """The file that template lives in, refusing anything that is not a name."""
        if not TEMPLATE_NAME.match(name):
            raise InvalidTemplateNameError(
                f"« {name} » n'est pas un nom de modèle : lettres, chiffres, "
                f"tirets et soulignés uniquement"
            )
        return self._directory / f"{name}{SUFFIX}"

    @staticmethod
    def _ensure_this_version_reads_it(name: str, written: object) -> None:
        """Refuse a template from another version of the schema.

        Loudly, because the alternative is reading a key that has moved on and
        silently playing a game nobody configured.
        """
        version = written.get("version") if isinstance(written, dict) else None
        if version != CONFIGURATION_VERSION:
            raise OutdatedTemplateError(
                f"Le modèle « {name} » a été écrit en version {version}, "
                f"et cette application lit la version {CONFIGURATION_VERSION}"
            )
