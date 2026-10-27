from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prepare_core100", ROOT / "backend/scripts/prepare_core100_audio.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MANIFEST = ROOT / "deploy/jingyun/core100-content-audio.manifest.json"


@pytest.fixture(autouse=True)
def script_module_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "backend/scripts"))


def test_expanded_manifest_preserves_original_ten_and_reports_remaining_gap():
    value = json.loads(MANIFEST.read_text())
    old = json.loads((ROOT / "deploy/jingyun/p1b-content-audio.manifest.json").read_text())
    assert len(value["audio"]["assets"]) == 99
    assert value["build"]["missing_word_ids"] == ["wood"]
    assert value["build"]["source_content_sha256"] == old["content"]["sha256"]
    assets = {a["word_id"]: a for a in value["audio"]["assets"]}
    for a in old["audio"]["assets"]:
        assert assets[a["word_id"]] == a
    credits = (ROOT / "deploy/jingyun/core100-audio-attribution.md").read_bytes()
    assert hashlib.sha256(credits).hexdigest() == value["audio"]["credits"]["sha256"]
    for wid, source in value["build"]["sources"].items():
        assert source["sha256"] == assets[wid]["sha256"]
        if "file_page" in source:
            assert source["file_page"] in credits.decode()
            assert source["license_url"] in credits.decode()
            assert source["creator"]
            assert source["license"] in ("CC BY-SA 3.0", "Public domain")


def fixture_package(tmp_path):
    repo = tmp_path / "repo"
    (repo / "content").mkdir(parents=True)
    (repo / "deploy/jingyun").mkdir(parents=True)
    for name in ("core_100_words.json", "phonemes.json"):
        (repo / "content" / name).write_bytes((ROOT / "content" / name).read_bytes())
    credits = ROOT / "deploy/jingyun/core100-audio-attribution.md"
    (repo / "deploy/jingyun" / credits.name).write_bytes(credits.read_bytes())
    manifest = copy.deepcopy(json.loads(MANIFEST.read_text()))
    manifest["audio"]["assets"] = manifest["audio"]["assets"][:2]
    required = [a["word_id"] for a in manifest["audio"]["assets"]]
    manifest["audio"]["required_word_ids"] = required
    manifest["build"]["sources"] = {wid: manifest["build"]["sources"][wid] for wid in required}
    content = json.loads((repo / "content/core_100_words.json").read_text())
    manifest["build"]["missing_word_ids"] = sorted(
        w["word_id"] for w in content["words"] if w["word_id"] not in required
    )
    for word in content["words"]:
        word["audio_us"] = (
            f"/audio/us/{word['word_id']}.mp3" if word["word_id"] in required else None
        )
    derived = (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode()
    manifest["content"]["sha256"] = hashlib.sha256(derived).hexdigest()
    payloads = {}
    for asset in manifest["audio"]["assets"]:
        data = ("synthetic-integrity-fixture:" + asset["word_id"]).encode()
        asset.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
        source = manifest["build"]["sources"][asset["word_id"]]
        source["sha256"] = asset["sha256"]
        payloads[source["url"]] = data
    path = repo / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, repo, tmp_path / "package", tmp_path / "cache", payloads


def test_integrity_fixture_download_requires_opt_in_and_cache_replays_offline(tmp_path):
    path, repo, package, cache, payloads = fixture_package(tmp_path)
    called = []

    def fetch(url):
        called.append(url)
        return payloads[url]

    with pytest.raises(ValueError, match="allow-download"):
        MODULE.prepare(path, repo, package, cache, fetcher=fetch)
    assert not called
    report = MODULE.prepare(path, repo, package, cache, allow_download=True, fetcher=fetch)
    assert report["status"] == "manifest_integrity_verified"
    assert report["audio_count"] == 2
    assert report["media_checked"] == 0  # Synthetic integrity bytes are not playback evidence.
    MODULE.prepare(path, repo, package, cache, fetcher=lambda _: pytest.fail("unexpected network"))
    assert len(called) == 2


def test_bad_download_checksum_is_never_published(tmp_path):
    path, repo, package, cache, _ = fixture_package(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        MODULE.prepare(
            path, repo, package, cache, allow_download=True, fetcher=lambda _: b"corrupt"
        )
    assert list((package / "us").iterdir()) == []
    assert list(cache.iterdir()) == []


def test_existing_wrong_bytes_are_preserved(tmp_path):
    path, repo, package, cache, _ = fixture_package(tmp_path)
    manifest = json.loads(path.read_text())
    target = package / manifest["audio"]["assets"][0]["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes(b"do not overwrite")
    with pytest.raises(ValueError, match="checksum"):
        MODULE.prepare(path, repo, package, cache)
    assert target.read_bytes() == b"do not overwrite"


@pytest.mark.parametrize("damage", ["path", "hash", "source", "coverage"])
def test_invalid_bindings_fail_before_assets_are_written(tmp_path, damage):
    path, repo, package, cache, _ = fixture_package(tmp_path)
    m = json.loads(path.read_text())
    if damage == "path":
        m["audio"]["assets"][0]["path"] = "../escape.mp3"
    elif damage == "hash":
        m["audio"]["assets"][0]["sha256"] = "../../bad"
    elif damage == "source":
        m["build"]["source_content_sha256"] = "0" * 64
    else:
        m["build"]["missing_word_ids"] = []
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):
        MODULE.prepare(path, repo, package, cache)
    assert not package.exists()


def test_candidate_symlink_root_is_refused(tmp_path):
    path, repo, package, cache, _ = fixture_package(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    package.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        MODULE.prepare(path, repo, package, cache)
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://upload.wikimedia.org/x",
        "https://example.com/audio.mp3",
        "https://upload.wikimedia.org:22/wikipedia/commons/a.mp3",
        "https://user:password@upload.wikimedia.org/wikipedia/commons/a.mp3",
    ],
)
def test_download_source_allowlist_rejects_before_network(url):
    with pytest.raises(ValueError):
        MODULE.download(url)


def test_audio_activation_only_adds_urls_and_preserves_all_other_data(tmp_path):
    import sqlite3

    spec = importlib.util.spec_from_file_location(
        "activate_audio", ROOT / "backend/scripts/activate_core100_audio.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = json.loads((ROOT / "content/core_100_words.json").read_text())
    expanded = copy.deepcopy(original)
    required = json.loads(MANIFEST.read_text())["audio"]["required_word_ids"]
    for word in expanded["words"]:
        word["audio_us"] = (
            f"/audio/us/{word['word_id']}.mp3" if word["word_id"] in required else None
        )
    conn = sqlite3.connect(tmp_path / "activation.sqlite")
    conn.executescript(
        "CREATE TABLE words(id TEXT PRIMARY KEY,word TEXT,ipa_us TEXT,audio_us TEXT);"
        "CREATE TABLE settings(user_id TEXT,daily_word_count INT);"
        "INSERT INTO settings VALUES('learner',3);"
        "CREATE TABLE attempts(id TEXT,selected_answer TEXT);"
        "INSERT INTO attempts VALUES('keep','private-fixture');"
    )
    for word in original["words"]:
        conn.execute(
            "INSERT INTO words VALUES(?,?,?,?)",
            (word["word_id"], word["word"], word["ipa_us"], word["audio_us"]),
        )
    conn.commit()
    before = list(conn.execute("SELECT id,word,ipa_us FROM words ORDER BY id"))
    planned = module.plan(conn, expanded, "manifest-fixture-hash")
    assert planned["change_count"] == 89
    result = module.apply(conn, expanded, "manifest-fixture-hash", planned["plan_sha256"])
    assert result["updated"] == 89
    assert list(conn.execute("SELECT id,word,ipa_us FROM words ORDER BY id")) == before
    assert conn.execute("SELECT * FROM settings").fetchall() == [("learner", 3)]
    assert conn.execute("SELECT * FROM attempts").fetchall() == [("keep", "private-fixture")]
    assert conn.execute("SELECT count(*) FROM words WHERE audio_us IS NOT NULL").fetchone()[0] == 99
    assert module.plan(conn, expanded, "manifest-fixture-hash")["change_count"] == 0
    with pytest.raises(ValueError, match="changed"):
        module.apply(conn, expanded, "manifest-fixture-hash", planned["plan_sha256"])
    conn.close()


def test_audio_activation_rejects_drift_without_partial_updates(tmp_path):
    import sqlite3

    spec = importlib.util.spec_from_file_location(
        "activate_audio_drift", ROOT / "backend/scripts/activate_core100_audio.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = {
        "words": [
            {
                "word_id": "about",
                "word": "about",
                "ipa_us": "/əˈbaʊt/",
                "audio_us": "/audio/us/about.mp3",
            }
        ]
    }
    conn = sqlite3.connect(tmp_path / "drift.sqlite")
    conn.execute("CREATE TABLE words(id TEXT,word TEXT,ipa_us TEXT,audio_us TEXT)")
    conn.execute("INSERT INTO words VALUES('about','about','/əˈbaʊt/',NULL)")
    conn.commit()
    planned = module.plan(conn, content, "manifest")
    conn.execute("UPDATE words SET audio_us='/existing/custom.mp3'")
    conn.commit()
    with pytest.raises(ValueError):
        module.apply(conn, content, "manifest", planned["plan_sha256"])
    assert conn.execute("SELECT audio_us FROM words").fetchone()[0] == "/existing/custom.mp3"
    assert not conn.in_transaction
    conn.close()
