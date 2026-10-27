from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[3]
PAIRS = [("came", "game"), ("back", "bag")]


def enabled() -> bool:
    return (
        os.getenv("TINY_IPA_ENABLE_LISTENING_PREVIEW", "false") == "true"
        and os.getenv("TINY_IPA_ENV", "development") == "development"
    )


def initialize(conn: sqlite3.Connection):
    conn.execute("""CREATE TABLE IF NOT EXISTS listening_previews (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        status TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL)""")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS listening_one_active "
        "ON listening_previews(user_id) WHERE status='active'"
    )


def materials() -> dict:
    manifest = json.loads((ROOT / "deploy/jingyun/core100-content-audio.manifest.json").read_text())
    source = json.loads((ROOT / "content/core_100_words.json").read_text())
    words = {w["word_id"]: w for w in source["words"]}
    assets = {a["word_id"]: a for a in manifest["audio"]["assets"]}
    root = Path(os.getenv("TINY_IPA_AUDIO_DIR", str(ROOT / "audio")))
    for wid in sum((list(p) for p in PAIRS), []):
        path = root / assets[wid]["path"]
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != assets[wid]["sha256"]
        ):
            raise HTTPException(409, detail={"error": "LISTENING_AUDIO_NOT_READY"})
    return words


def _words() -> dict:
    source = json.loads((ROOT / "content/core_100_words.json").read_text())
    return {w["word_id"]: w for w in source["words"]}


def _audio(wid: str) -> str:
    return f"/audio/us/{wid}.mp3"


def present(row) -> dict | None:
    if row is None:
        return None
    state = json.loads(row["state"])
    items = state["items"]
    cursor = state["cursor"]
    current = items[cursor]
    phase = (
        "completed" if row["status"] == "completed" else ("question" if state["begun"] else "demo")
    )
    words = _words()
    answers = [
        {
            "index": i,
            "selected": x["answer"],
            "correct": x["target"],
            "is_correct": x["answer"] == x["target"],
            "audio_url": _audio(x["target"]),
        }
        for i, x in enumerate(items)
        if x["answer"]
    ]
    return {
        "id": row["id"],
        "phase": phase,
        "cursor": cursor,
        "demo": [{"word": w, "ipa": words[w]["ipa_us"], "audio_url": _audio(w)} for w in PAIRS[0]],
        "item": None
        if phase != "question"
        else {
            "index": cursor,
            "choices": current["choices"],
            "audio_url": _audio(current["target"]),
            "heard": current["heard"],
            "feedback": next((a for a in answers if a["index"] == cursor), None),
        },
        "answers": answers,
        "summary": {
            "correct": sum(a["is_correct"] for a in answers),
            "total": len(answers),
            "practice_correct": sum(a["is_correct"] for a in answers if a["index"] < 4),
            "new_words_correct": sum(a["is_correct"] for a in answers if a["index"] >= 4),
        },
    }


def current(conn, owner: str):
    return present(
        conn.execute(
            "SELECT * FROM listening_previews WHERE user_id=? "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,"
            "created_at DESC,rowid DESC LIMIT 1",
            (owner,),
        ).fetchone()
    )


def start(conn, owner: str):
    materials()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT * FROM listening_previews WHERE user_id=? AND status='active'", (owner,)
    ).fetchone()
    if row:
        return present(row)
    lesson_id = uuid.uuid4().hex
    rng = random.Random(lesson_id)
    items = []
    for pair in PAIRS:
        targets = list(pair) * 2
        rng.shuffle(targets)
        sides = [0, 0, 1, 1]
        rng.shuffle(sides)
        for target, side in zip(targets, sides):
            other = pair[1] if target == pair[0] else pair[0]
            choices = [target, other] if side == 0 else [other, target]
            items.append({"target": target, "choices": choices, "answer": None, "heard": False})
    state = {"begun": False, "cursor": 0, "items": items}
    conn.execute(
        "INSERT INTO listening_previews VALUES(?,?,'active',?,?)",
        (
            lesson_id,
            owner,
            json.dumps(state),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return current(conn, owner)


def act(conn, owner: str, lesson_id: str, body: dict):
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT * FROM listening_previews WHERE id=? AND user_id=?", (lesson_id, owner)
    ).fetchone()
    if not row:
        raise HTTPException(404, detail={"error": "LISTENING_NOT_FOUND"})
    state = json.loads(row["state"])
    action = body.get("action")
    if not isinstance(action, str):
        raise HTTPException(400, detail={"error": "LISTENING_INVALID_ACTION"})
    index = body.get("index")
    if action == "answer" and type(index) is int and 0 <= index < 8:
        saved = state["items"][index]["answer"]
        if saved is not None:
            if saved != body.get("selected_answer"):
                raise HTTPException(409, detail={"error": "LISTENING_ALREADY_ANSWERED"})
            return {**present(row), "replayed": True}
    if row["status"] == "completed":
        raise HTTPException(409, detail={"error": "LISTENING_COMPLETED"})
    if action == "begin":
        state["begun"] = True
    elif action in {"played", "answer", "next"}:
        if not state["begun"] or type(index) is not int or index != state["cursor"]:
            raise HTTPException(409, detail={"error": "LISTENING_ITEM_CHANGED"})
        item = state["items"][index]
        if action == "played":
            item["heard"] = True
        elif action == "answer":
            if not item["heard"] or body.get("selected_answer") not in item["choices"]:
                raise HTTPException(409, detail={"error": "LISTENING_PLAY_BEFORE_ANSWER"})
            item["answer"] = body["selected_answer"]
        else:
            if item["answer"] is None:
                raise HTTPException(409, detail={"error": "LISTENING_ANSWER_REQUIRED"})
            state["cursor"] = min(index + 1, 7)
    else:
        raise HTTPException(400, detail={"error": "LISTENING_INVALID_ACTION"})
    completed = action == "next" and index == 7
    conn.execute(
        "UPDATE listening_previews SET state=?,status=? WHERE id=?",
        (
            json.dumps(state),
            "completed" if completed else "active",
            lesson_id,
        ),
    )
    return present(
        conn.execute("SELECT * FROM listening_previews WHERE id=?", (lesson_id,)).fetchone()
    )
