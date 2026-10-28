from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prepare_core300_test", ROOT / "backend/scripts/prepare_core100_audio.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MANIFEST = ROOT / "deploy/jingyun/core300-content-audio.manifest.json"


@pytest.fixture(autouse=True)
def script_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "backend/scripts"))


def fixture_package(tmp_path):
    repo = tmp_path / "repo"
    (repo / "content").mkdir(parents=True)
    (repo / "deploy/jingyun").mkdir(parents=True)
    for name in [
        "content/core_300_words.json",
        "content/core_300_phoneme_corrections.json",
        "content/phonemes.json",
        "deploy/jingyun/core100-content-audio.manifest.json",
        "deploy/jingyun/core300-audio-attribution.md",
    ]:
        (repo / name).write_bytes((ROOT / name).read_bytes())
    path = repo / "manifest.json"
    path.write_bytes(MANIFEST.read_bytes())
    manifest = json.loads(path.read_text())
    cache = tmp_path / "cache"
    cache.mkdir()
    for fixture_name in ["core100-media.zip", "core300-extra-media.zip"]:
        with zipfile.ZipFile(ROOT / "frontend/tests/fixtures" / fixture_name) as archive:
            for asset in manifest["audio"]["assets"]:
                if asset["path"] in archive.namelist():
                    data = archive.read(asset["path"])
                    assert hashlib.sha256(data).hexdigest() == asset["sha256"]
                    (cache / f"{asset['sha256']}.mp3").write_bytes(data)
    return path, repo, tmp_path / "package", cache


def test_source_bound_overlay_preserves_existing_assets_and_declares_gaps(tmp_path):
    from correct_core100_tags import derive
    from correct_expanded_tags import load_pack

    path, repo, output, cache = fixture_package(tmp_path)
    value = json.loads(path.read_text())
    old = json.loads((ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_text())
    assets = {a["word_id"]: a for a in value["audio"]["assets"]}
    for a in old["audio"]["assets"]:
        assert assets[a["word_id"]] == a
    report = MODULE.prepare(
        path,
        repo,
        output,
        cache,
        pack_size=300,
        fetcher=lambda _: pytest.fail("unexpected network"),
    )
    assert report["audio_count"] == 111 and report["word_count"] == 300
    source, patch = load_pack(300)
    corrected = derive(source, patch)
    candidate = json.loads((repo / value["content"]["path"]).read_text())
    for before, after in zip(corrected["words"], candidate["words"]):
        assert {k: v for k, v in before.items() if k != "audio_us"} == {
            k: v for k, v in after.items() if k != "audio_us"
        }
        assert after["audio_us"] == (
            f"/audio/us/{after['word_id']}.mp3" if after["word_id"] in assets else None
        )
    assert len(report["missing_word_ids"]) == 189
    assert value["build"]["disabled_word_ids"] == ["feb"]
    assert len(value["build"]["new_word_ids"]) == 12
    assert {
        w["word_id"]
        for w in candidate["words"]
        if w["content_status"] == "disabled" and w["audio_us"]
    } == set()
    credits = (ROOT / "deploy/jingyun/core300-audio-attribution.md").read_text()
    for wid in value["build"]["new_word_ids"]:
        s = value["build"]["sources"][wid]
        assert s["file_page"] in credits and s["license_url"] in credits
        assert s["creator"] == "Dvortygirl" and s["license"] == "CC BY-SA 3.0"
    assert (repo / "content/core_300_words.json").read_bytes() == (
        ROOT / "content/core_300_words.json"
    ).read_bytes()


@pytest.mark.parametrize(
    "damage", ["source", "tags", "reuse", "reuse_asset", "disabled", "path", "addition_list"]
)
def test_bad_binding_rejects_before_package_write(tmp_path, damage):
    path, repo, output, cache = fixture_package(tmp_path)
    m = json.loads(path.read_text())
    if damage == "source":
        m["build"]["source_content_sha256"] = "0" * 64
    elif damage == "tags":
        m["build"]["tag_corrections"]["sha256"] = "0" * 64
    elif damage == "reuse":
        m["build"]["reuse_manifest"]["sha256"] = "0" * 64
    elif damage == "reuse_asset":
        m["audio"]["assets"][0]["bytes"] += 1
    elif damage == "disabled":
        m["audio"]["required_word_ids"].append("feb")
    elif damage == "path":
        asset = next(a for a in m["audio"]["assets"] if a["word_id"] == "book")
        asset["path"] = "../escape.mp3"
    else:
        m["build"]["new_word_ids"] = []
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        MODULE.prepare(path, repo, output, cache, pack_size=300)
    assert not output.exists()


@pytest.mark.parametrize("damage", ["missing", "wrong_cache", "collision"])
def test_missing_wrong_or_collision_preserves_existing_bytes(tmp_path, damage):
    path, repo, output, cache = fixture_package(tmp_path)
    manifest = json.loads(path.read_text())
    asset = next(a for a in manifest["audio"]["assets"] if a["word_id"] == "book")
    target = output / asset["path"]
    if damage == "missing":
        cache = tmp_path / "empty-cache"
        cache.mkdir()
    elif damage == "wrong_cache":
        (cache / f"{asset['sha256']}.mp3").write_bytes(b"wrong")
    else:
        target.parent.mkdir(parents=True)
        target.write_bytes(b"preserve collision")
    with pytest.raises(ValueError):
        MODULE.prepare(path, repo, output, cache, pack_size=300)
    if damage == "collision":
        assert target.read_bytes() == b"preserve collision"
    if damage == "wrong_cache":
        assert (cache / f"{asset['sha256']}.mp3").read_bytes() == b"wrong"


def test_core300_requires_explicit_pack_selection(tmp_path):
    path, repo, output, cache = fixture_package(tmp_path)
    with pytest.raises(ValueError, match="source content"):
        MODULE.prepare(path, repo, output, cache)
    assert not output.exists()
