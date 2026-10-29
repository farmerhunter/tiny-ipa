import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/scripts"))
from activate_core100_audio import apply as audio_apply  # noqa: E402
from activate_core100_audio import plan as audio_plan  # noqa: E402
from activate_sound_compare import apply as pair_apply  # noqa: E402
from activate_sound_compare import plan as pair_plan  # noqa: E402
from correct_core100_tags import apply as tag_apply  # noqa: E402
from correct_core100_tags import load_corrections  # noqa: E402
from correct_core100_tags import plan as tag_plan  # noqa: E402
from import_words import import_words  # noqa: E402
from prepare_core100_audio import prepare  # noqa: E402

from app.db import get_connection  # noqa: E402
from app.main import app  # noqa: E402
from tests.auth_helpers import authenticated_client, bootstrap_owner_user  # noqa: E402

EVIDENCE = ROOT / "content/sound_compare_pairs_candidate.json"


def snapshot(conn, omit_pairs=False):
    tables = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    result = {}
    for table in tables:
        columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
        rows = list(conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'))
        if table == "words" and omit_pairs:
            rows = [
                tuple(v for k, v in zip(columns, row) if k != "minimal_pair_group") for row in rows
            ]
        result[table] = [tuple(row) for row in rows]
    return result


@pytest.fixture(scope="session")
def activation_media(tmp_path_factory):
    root = tmp_path_factory.mktemp("activation-audio").resolve()
    spec = importlib.util.spec_from_file_location(
        "activation_fixture", ROOT / "frontend/tests/e2e/support/prepare_core100_real_db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = ROOT / "deploy/jingyun/core100-content-audio.manifest.json"
    module.seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core100-media.zip",
        json.loads(manifest.read_text()),
        root / "cache",
    )
    prepare(manifest, ROOT, root / "audio", root / "cache")
    return root / "audio"


@pytest.fixture
def baseline(tmp_path, activation_media, monkeypatch):
    database = tmp_path / "baseline.sqlite"
    assert import_words(
        ROOT / "content/core_100_words.json", ROOT / "content/phonemes.json", str(database)
    )["committed"]
    bootstrap_owner_user(str(database))
    conn = get_connection(str(database))
    content = json.loads((ROOT / "content/generated/core_100_audio_candidate.json").read_text())
    p = audio_plan(conn, content, "fixture")
    audio_apply(conn, content, "fixture", p["plan_sha256"])
    _, tags = load_corrections()
    p = tag_plan(conn, tags)
    tag_apply(conn, tags, p["plan_sha256"])
    conn.execute("UPDATE settings SET daily_word_count=8")
    conn.commit()
    monkeypatch.setattr("app.db.DEFAULT_DB_PATH", str(database))
    monkeypatch.setenv("TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH", str(EVIDENCE))
    yield conn, activation_media
    conn.close()


def pair(conn, audio, action="enable"):
    p = pair_plan(conn, action, ROOT, EVIDENCE, audio)
    return pair_apply(conn, action, ROOT, EVIDENCE, audio, p["plan_sha256"])


def test_pair_readonly_enable_noop_stale_and_only_field_scope(baseline):
    conn, audio = baseline
    before = snapshot(conn, True)
    p = pair_plan(conn, "enable", ROOT, EVIDENCE, audio)
    assert p["change_count"] == 8 and not conn.in_transaction
    assert pair_apply(conn, "enable", ROOT, EVIDENCE, audio, p["plan_sha256"])["updated"] == 8
    assert before == snapshot(conn, True)
    with pytest.raises(ValueError, match="stale"):
        pair_apply(conn, "enable", ROOT, EVIDENCE, audio, p["plan_sha256"])
    assert pair(conn, audio)["status"] == "no_change"
    assert pair(conn, None, "disable")["updated"] == 8
    assert pair(conn, None, "disable")["status"] == "no_change"
    assert snapshot(conn, True) == before


def test_pending_past_date_disable_refuses_and_completed_replay_survives(baseline):
    conn, audio = baseline
    pair(conn, audio)
    client = authenticated_client(TestClient(app))
    group = client.post("/api/practice/minimal-pairs").json()
    conn.execute("UPDATE daily_sessions SET session_date='2001-01-01'")
    conn.commit()
    first = group["items"][0]
    payload = {"session_item_id": first["session_item_id"], "selected_answer": first["display_ipa"]}
    assert client.post("/api/attempt", json=payload).json()["is_correct"]
    before = snapshot(conn)
    result = pair(conn, None, "disable")
    assert result == {"status": "blocked_unfinished_sessions", "updated": 0, "blocked_sessions": 1}
    assert before == snapshot(conn)
    for item in group["items"][1:]:
        assert client.post(
            "/api/attempt",
            json={
                "session_item_id": item["session_item_id"],
                "selected_answer": item["display_ipa"],
            },
        ).json()["is_correct"]
    p = pair_plan(conn, "disable", ROOT, EVIDENCE)
    assert p["blocked_sessions"] == 0
    assert pair_apply(conn, "disable", ROOT, EVIDENCE, None, p["plan_sha256"])["updated"] == 8
    history = snapshot(conn)
    assert client.post("/api/attempt", json=payload).json()["replayed"]
    # Auth readback can refresh last_seen; learner answers/history are otherwise untouched.
    after = snapshot(conn)
    assert after["attempts"] == history["attempts"]
    assert client.post("/api/practice/minimal-pairs").json()["status"] == "empty"


@pytest.mark.parametrize("damage", ["mixed", "third", "ipa", "tag", "status", "audio", "inventory"])
def test_pair_conflicts_fail_without_writes(baseline, damage):
    conn, audio = baseline
    if damage == "mixed":
        conn.execute("UPDATE words SET minimal_pair_group='kg_final' WHERE id='back'")
    elif damage == "third":
        conn.execute("UPDATE words SET minimal_pair_group='kg_final' WHERE id='bus'")
    elif damage == "ipa":
        conn.execute("UPDATE words SET ipa_us='/wrong/' WHERE id='cat'")
    elif damage == "tag":
        conn.execute("UPDATE words SET phoneme_tags_us='[]' WHERE id='cat'")
    elif damage == "status":
        conn.execute("UPDATE words SET content_status='disabled' WHERE id='cat'")
    elif damage == "audio":
        conn.execute("UPDATE words SET audio_us=NULL WHERE id='cat'")
    else:
        conn.execute("DELETE FROM phonemes WHERE id='/h/'")
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(ValueError):
        pair(conn, audio)
    assert snapshot(conn) == before


def test_pair_atomic_fault_and_new_activity_does_not_stale_enable(baseline):
    conn, audio = baseline
    p = pair_plan(conn, "enable", ROOT, EVIDENCE, audio)
    conn.execute(
        "CREATE TRIGGER fail_pair BEFORE UPDATE OF minimal_pair_group ON words "
        "WHEN NEW.id='cat' BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(sqlite3.IntegrityError):
        pair_apply(conn, "enable", ROOT, EVIDENCE, audio, p["plan_sha256"])
    assert snapshot(conn) == before
    # Separate fixture transaction leaves the operator's source/content plan valid.
    client = authenticated_client(TestClient(app))
    item = client.post("/api/practice/next-normal").json()["items"][0]
    assert client.post(
        "/api/attempt",
        json={"session_item_id": item["session_item_id"], "selected_answer": item["display_ipa"]},
    ).json()["is_correct"]
    assert pair_plan(conn, "enable", ROOT, EVIDENCE, audio)["plan_sha256"] == p["plan_sha256"]


@pytest.mark.parametrize("damage", ["missing", "wrong"])
def test_pair_missing_media_blocks_enable_but_not_disable(baseline, tmp_path, damage):
    conn, audio = baseline
    before = snapshot(conn)
    bad = tmp_path.resolve() / "audio"
    (bad / "us").mkdir(parents=True)
    if damage == "wrong":
        (bad / "us/back.mp3").write_bytes(b"wrong")
    with pytest.raises((ValueError, OSError)):
        pair(conn, bad)
    assert snapshot(conn) == before
    pair(conn, audio)
    assert pair(conn, bad, "disable")["updated"] == 8


def test_enable_after_new_activity_preserves_all_learner_rows(baseline):
    conn, audio = baseline
    p = pair_plan(conn, "enable", ROOT, EVIDENCE, audio)
    client = authenticated_client(TestClient(app))
    item = client.post("/api/practice/next-normal").json()["items"][0]
    client.post(
        "/api/attempt",
        json={"session_item_id": item["session_item_id"], "selected_answer": item["display_ipa"]},
    )
    before = snapshot(conn, True)
    assert pair_apply(conn, "enable", ROOT, EVIDENCE, audio, p["plan_sha256"])["updated"] == 8
    assert snapshot(conn, True) == before


@pytest.fixture(scope="session")
def increment_media(activation_media):
    from insert_core300_increment import prepare_media

    root = activation_media.parent
    manifest = json.loads((ROOT / "deploy/jingyun/core300-content-audio.manifest.json").read_text())
    selected = [
        a for a in manifest["audio"]["assets"] if a["word_id"] in manifest["build"]["new_word_ids"]
    ]
    spec = importlib.util.spec_from_file_location(
        "increment_fixture", ROOT / "frontend/tests/e2e/support/prepare_core100_real_db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.seed_audio_cache(
        ROOT / "frontend/tests/fixtures/core300-extra-media.zip",
        {"audio": {"assets": selected, "credits": manifest["audio"]["credits"]}},
        root / "extra-cache",
    )
    old = {p.name: p.read_bytes() for p in (activation_media / "us").iterdir()}
    result = prepare_media(ROOT, activation_media, root / "extra-cache", validate_media=False)
    assert result["audio_count"] == 12 and result["audio_bytes"] == 175220
    assert all((activation_media / "us" / name).read_bytes() == data for name, data in old.items())
    assert prepare_media(ROOT, activation_media, root / "extra-cache")["audio_count"] == 12
    return activation_media


def increment(conn, audio):
    from insert_core300_increment import apply, plan

    p = plan(conn, ROOT, audio)
    return apply(conn, ROOT, audio, p["plan_sha256"])


def test_increment_only_twelve_explicit_rows_idempotence_stale_and_history(
    baseline, increment_media
):
    from insert_core300_increment import COLUMNS, apply, plan, source, stored

    conn, _ = baseline
    p = plan(conn, ROOT, increment_media)
    assert p["change_count"] == 12 and p["insert_fields"] == list(COLUMNS)
    assert not conn.in_transaction
    client = authenticated_client(TestClient(app))
    item = client.post("/api/practice/next-normal").json()["items"][0]
    assert client.post(
        "/api/attempt",
        json={"session_item_id": item["session_item_id"], "selected_answer": item["display_ipa"]},
    ).json()["is_correct"]
    before = snapshot(conn)
    assert apply(conn, ROOT, increment_media, p["plan_sha256"])["updated"] == 12
    after = snapshot(conn)
    for table in before:
        if table != "words":
            assert after[table] == before[table]
    rows = {r[0]: tuple(r) for r in conn.execute("SELECT * FROM words")}
    assert all(rows[r[0]] == r for r in before["words"])
    assert conn.execute("SELECT count(*), count(audio_us) FROM words").fetchone()[:] == (112, 111)
    for word in source(ROOT)[0]:
        assert dict(
            zip(
                COLUMNS,
                conn.execute(
                    "SELECT " + ",".join(COLUMNS) + " FROM words WHERE id=?", (word["word_id"],)
                ).fetchone(),
            )
        ) == stored(word)
    with pytest.raises(ValueError, match="stale"):
        apply(conn, ROOT, increment_media, p["plan_sha256"])
    assert increment(conn, increment_media)["status"] == "no_change"
    assert "feb" not in rows and rows["wood"][8] is None


@pytest.mark.parametrize("damage", ["partial", "row", "old", "extra", "inventory", "schema"])
def test_increment_conflicts_never_upsert_or_bootstrap(baseline, increment_media, damage):
    from insert_core300_increment import COLUMNS, source

    conn, _ = baseline
    if damage == "partial":
        values = __import__("insert_core300_increment").stored(source(ROOT)[0][0])
        conn.execute(
            "INSERT INTO words ("
            + ",".join(COLUMNS)
            + ") VALUES ("
            + ",".join("?" for _ in COLUMNS)
            + ")",
            list(values.values()),
        )
    elif damage == "row":
        increment(conn, increment_media)
        conn.execute("UPDATE words SET meaning_zh='conflict' WHERE id='book'")
    elif damage == "old":
        conn.execute("UPDATE words SET meaning_zh='drift' WHERE id='cat'")
    elif damage == "extra":
        conn.execute("UPDATE words SET id='unexpected' WHERE id='cat'")
    elif damage == "inventory":
        conn.execute("UPDATE phonemes SET accent_scope='UK' WHERE id='/b/'")
    else:
        # A malformed isolated catalog must not be repaired by a content tool.
        conn.execute("ALTER TABLE words RENAME COLUMN ipa_uk TO absent_ipa_uk")
    conn.commit()
    before = snapshot(conn)
    with pytest.raises(ValueError):
        increment(conn, increment_media)
    assert snapshot(conn) == before


def test_increment_midtransaction_failure_rolls_back_without_removing_prepared_audio(
    baseline, increment_media
):
    conn, _ = baseline
    conn.execute(
        "CREATE TRIGGER fail_insert BEFORE INSERT ON words WHEN NEW.id='father' "
        "BEGIN SELECT RAISE(ABORT,'injected'); END"
    )
    conn.commit()
    before = snapshot(conn)
    files = {p.name: p.read_bytes() for p in (increment_media / "us").iterdir()}
    with pytest.raises(sqlite3.IntegrityError):
        increment(conn, increment_media)
    assert snapshot(conn) == before
    assert files == {p.name: p.read_bytes() for p in (increment_media / "us").iterdir()}


def test_ab_ba_composition_fresh_plans_and_stale_catalog_preconditions(
    baseline, increment_media, tmp_path
):
    from insert_core300_increment import apply, plan

    conn, _ = baseline
    reverse = sqlite3.connect(tmp_path / "reverse.sqlite")
    conn.backup(reverse)
    before = snapshot(conn)
    stale_b = plan(conn, ROOT, increment_media)
    pair(conn, increment_media)
    with pytest.raises(ValueError, match="stale"):
        apply(conn, ROOT, increment_media, stale_b["plan_sha256"])
    increment(conn, increment_media)
    stale_a = pair_plan(reverse, "enable", ROOT, EVIDENCE, increment_media)
    increment(reverse, increment_media)
    with pytest.raises(ValueError, match="stale"):
        pair_apply(reverse, "enable", ROOT, EVIDENCE, increment_media, stale_a["plan_sha256"])
    pair(reverse, increment_media)
    assert snapshot(conn) == snapshot(reverse)
    final = snapshot(conn)
    assert len(final["words"]) == 112
    for table in before:
        if table != "words":
            assert final[table] == before[table]
    assert pair(conn, None, "disable")["updated"] == 8
    assert conn.execute("SELECT count(*),count(audio_us) FROM words").fetchone()[:] == (112, 111)
    assert increment(conn, increment_media)["status"] == "no_change"
    reverse.close()


def test_increment_missing_wrong_media_and_collisions_leave_database_unchanged(
    baseline, increment_media, tmp_path
):
    from insert_core300_increment import prepare_media

    conn, _ = baseline
    before = snapshot(conn)
    with pytest.raises((OSError, ValueError)):
        increment(conn, tmp_path.resolve())
    target = tmp_path.resolve() / "collision"
    (target / "us").mkdir(parents=True)
    (target / "us/book.mp3").write_bytes(b"wrong")
    with pytest.raises(ValueError, match="different"):
        prepare_media(ROOT, target, increment_media.parent / "extra-cache")
    assert (target / "us/book.mp3").read_bytes() == b"wrong" and snapshot(conn) == before
    target2 = tmp_path.resolve() / "symlink"
    target2.symlink_to(increment_media, target_is_directory=True)
    with pytest.raises(ValueError):
        increment(conn, target2)


@pytest.mark.parametrize(
    "damage", ["source", "correction", "manifest_duplicate", "manifest_path", "credit"]
)
def test_increment_source_bindings_fail_closed(baseline, increment_media, tmp_path, damage):
    from insert_core300_increment import plan, source

    conn, _ = baseline
    root = tmp_path.resolve() / "source-copy"
    for name in source(ROOT)[4]:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    if damage == "source":
        (root / "content/core_300_words.json").write_text("{}")
    elif damage == "correction":
        (root / "content/core_300_phoneme_corrections.json").write_text("{}")
    elif damage == "credit":
        (root / "deploy/jingyun/core300-audio-attribution.md").write_text("wrong")
    else:
        path = root / "deploy/jingyun/core300-content-audio.manifest.json"
        m = json.loads(path.read_text())
        if damage == "manifest_duplicate":
            m["audio"]["assets"].append(m["audio"]["assets"][-1])
        else:
            next(a for a in m["audio"]["assets"] if a["word_id"] == "book")["path"] = "../book.mp3"
        path.write_text(json.dumps(m))
    before = snapshot(conn)
    with pytest.raises((ValueError, KeyError)):
        plan(conn, root, increment_media)
    assert snapshot(conn) == before


def test_cli_default_plan_is_readonly_and_explicit_database_required(baseline, increment_media):
    import subprocess

    conn, _ = baseline
    path = next(r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main")
    before = snapshot(conn)
    command = [
        sys.executable,
        str(ROOT / "backend/scripts/insert_core300_increment.py"),
        "--repo-root",
        str(ROOT),
        "--audio-root",
        str(increment_media),
        "--db",
        path,
    ]
    response = subprocess.run(command, capture_output=True, text=True)
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout)["change_count"] == 12 and snapshot(conn) == before
    response = subprocess.run(command[:-2], capture_output=True, text=True)
    assert response.returncode != 0 and "explicit --db" in response.stderr


def test_all_twelve_recordings_decode_with_existing_media_tools(increment_media):
    from insert_core300_increment import source
    from prepare_core100_audio import check_media

    assets = source(ROOT)[1]
    assert len(assets) == 12
    for asset in assets:
        assert check_media(increment_media / asset["path"])["decoded"]
