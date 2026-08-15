"""What a registry of providers is once written down (D-112).

One JSON file rather than a directory of them, unlike the template library of J6
(D-068): a registry holds a handful of entries and is always read whole, so a
file per provider would multiply the reads without buying anything back.

Split out of the registry itself when the entry grew a second kind of content in
J8bis.3 (HR-7). The line is the one the registry's own docstring drew: *what is
on disk* is one thing, *what the registry offers* is another, and only the first
has anything to do with JSON.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from lupus_ex_machina.providers.verdicts import Verdict

ENCODING = "utf-8"


class Entry(BaseModel):
    """One provider as it is written down.

    A model rather than a bare dictionary, so that what a file contains is
    validated on the way in: this shape grew a second kind of content once, and
    one that is only ever assumed drifts silently.
    """

    model_config = ConfigDict(frozen=True)

    base_url: str
    api_key: str
    """Sealed, always. The clear key exists only inside ``ProviderRegistry``."""
    verdicts: dict[str, Verdict] = Field(default_factory=dict)
    """What a compatibility probe concluded of each of its models (D-115).

    Kept beside the provider rather than in a file of their own, and that is a
    correctness matter: forgetting a provider must forget what was learnt of it,
    or a name registered again — pointing somewhere else — would inherit the
    verdicts of an endpoint it has nothing to do with.

    Absent from files written before J8bis.3, hence the default: an installation
    that registered providers yesterday reads them today.
    """


#: How the file is read back. One adapter rather than a loop, so a file that has
#: drifted fails at the door instead of halfway through a screen.
_ON_FILE = TypeAdapter(dict[str, Entry])


def read_from(path: Path) -> dict[str, Entry]:
    """Everything on file, or nothing at all.

    A registry that has never kept anything has no file to read, which is not an
    error: it is what an installation looks like before its first provider.
    """
    if not path.is_file():
        return {}
    return _ON_FILE.validate_json(path.read_text(encoding=ENCODING))


def write_to(path: Path, kept: dict[str, Entry]) -> None:
    """Put the whole registry back, creating its directory if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = {name: entry.model_dump(mode="json") for name, entry in kept.items()}
    path.write_text(
        json.dumps(written, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding=ENCODING,
    )
