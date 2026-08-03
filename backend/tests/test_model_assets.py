"""The 3D models are served by the API process, under /models.

A GLB delivered under the wrong media type is rejected by some browsers, and the
failure surfaces far from its cause — hence an explicit test.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lupus_ex_machina.app import create_app
from lupus_ex_machina.config import REPOSITORY_ROOT, Settings

GLTF_BINARY_MEDIA_TYPE = "model/gltf-binary"

# A model the graveyard kit is guaranteed to ship; used to prove the real
# repository layout is wired correctly, not just a synthetic directory.
KNOWN_MODEL = "kenney_graveyard-kit_5.0/Models/GLB format/fire-basket.glb"


def build_models_dir(directory: Path) -> Path:
    """Create a model directory holding a single, minimal GLB file."""
    (directory / "characters").mkdir(parents=True)
    (directory / "characters" / "character-female-a.glb").write_bytes(b"glTF\x02\x00\x00\x00")
    return directory


def test_glb_model_is_served_with_the_gltf_binary_media_type(tmp_path: Path) -> None:
    settings = Settings(models_dir=build_models_dir(tmp_path / "assets"))

    response = TestClient(create_app(settings)).get("/models/characters/character-female-a.glb")

    assert response.status_code == 200
    assert response.headers["content-type"] == GLTF_BINARY_MEDIA_TYPE
    assert response.content == b"glTF\x02\x00\x00\x00"


def test_models_are_served_with_a_long_lived_cache(tmp_path: Path) -> None:
    settings = Settings(models_dir=build_models_dir(tmp_path / "assets"))

    response = TestClient(create_app(settings)).get("/models/characters/character-female-a.glb")

    assert "immutable" in response.headers["cache-control"]
    assert "max-age=31536000" in response.headers["cache-control"]


def test_non_model_files_keep_their_own_media_type(tmp_path: Path) -> None:
    """The asset packs ship their licences next to the models; those stay text."""
    models_dir = build_models_dir(tmp_path / "assets")
    (models_dir / "License.txt").write_text("CC0\n", encoding="utf-8")

    response = TestClient(create_app(Settings(models_dir=models_dir))).get("/models/License.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "immutable" in response.headers["cache-control"]


def test_unchanged_model_answers_not_modified(tmp_path: Path) -> None:
    """A revalidated model must stay a bare 304, without entity headers."""
    settings = Settings(models_dir=build_models_dir(tmp_path / "assets"))
    client = TestClient(create_app(settings))
    path = "/models/characters/character-female-a.glb"

    served = client.get(path)
    revalidated = client.get(path, headers={"if-none-match": served.headers["etag"]})

    assert revalidated.status_code == 304
    assert "content-type" not in revalidated.headers


def test_unknown_model_is_not_found(tmp_path: Path) -> None:
    settings = Settings(models_dir=build_models_dir(tmp_path / "assets"))

    response = TestClient(create_app(settings)).get("/models/characters/nope.glb")

    assert response.status_code == 404


def test_application_starts_without_a_models_directory(tmp_path: Path) -> None:
    settings = Settings(models_dir=tmp_path / "missing")

    client = TestClient(create_app(settings))

    assert client.get("/health").status_code == 200
    assert client.get("/models/characters/character-female-a.glb").status_code == 404


@pytest.mark.skipif(
    not (REPOSITORY_ROOT / "assets" / KNOWN_MODEL).is_file(),
    reason="the Kenney assets are not present in this checkout",
)
def test_a_known_model_of_the_repository_is_reachable() -> None:
    response = TestClient(create_app()).get(f"/models/{KNOWN_MODEL}")

    assert response.status_code == 200
    assert response.headers["content-type"] == GLTF_BINARY_MEDIA_TYPE
