"""Derive source-bound expanded tag candidates; never open a database."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from correct_core100_tags import derive
from select_candidates import parse_ipa_to_phonemes

ROOT = Path(__file__).resolve().parents[2]


def load_pack(size: int, root: Path = ROOT) -> tuple[dict, dict]:
    if size not in (300, 1000):
        raise ValueError("unsupported correction pack")
    patch = json.loads((root / f"content/core_{size}_phoneme_corrections.json").read_text())
    expected_source = f"content/core_{size}_words.json"
    if (
        patch["schema"] != "tiny-ipa-expanded-tag-corrections/v1"
        or patch["source"] != expected_source
    ):
        raise ValueError("unexpected correction schema/source")
    source = (root / expected_source).read_bytes()
    if hashlib.sha256(source).hexdigest() != patch["source_sha256"]:
        raise ValueError("frozen correction source changed")
    content = json.loads(source)
    words = {w["word_id"]: w for w in content["words"]}
    if len(words) != len(content["words"]):
        raise ValueError("duplicate source word identity")
    seen = set()
    for change in patch["changes"]:
        wid = change["word_id"]
        if wid in seen or wid not in words:
            raise ValueError("invalid correction identity")
        seen.add(wid)
        word = words[wid]
        note = word.get("_phoneme_override_note") or word.get("phoneme_override_note")
        if not note or change["normalization_note"] != note:
            raise ValueError("correction normalization provenance differs")
        if word["ipa_us"] != change["ipa_us"] or word["phoneme_tags_us"] != change["before"]:
            raise ValueError("correction preimage differs")
        parsed, unknown = parse_ipa_to_phonemes(word["ipa_us"])
        expected = [{"/ə/": "/ʌ/", "/ɝ/": "/ɚ/"}.get(t, t) for t in parsed]
        if unknown or change["after"] != expected:
            raise ValueError("correction must preserve parsed tags and documented normalization")
    return content, patch


def prepare_import(source: Path, words: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    bindings, changes = [], []
    prepared = words
    for size in (300, 1000):
        content, patch = load_pack(size)
        changes.extend(patch["changes"])
        if source_sha == patch["source_sha256"]:
            prepared = derive(content, patch)["words"]
            bindings.append(
                {
                    "source": patch["source"],
                    "source_sha256": source_sha,
                    "corrected_word_ids": [c["word_id"] for c in patch["changes"]],
                }
            )
        elif source.resolve() == (ROOT / patch["source"]).resolve():
            raise ValueError("frozen import source changed; review a new correction binding")
    return prepared, bindings, changes


def check_regression(connection, words: list[dict], changes: list[dict]) -> None:
    reviewed = {c["word_id"]: c for c in changes}
    for word in words:
        wid = word.get("word_id") or word.get("id")
        change = reviewed.get(wid)
        if not change:
            continue
        row = connection.execute("SELECT phoneme_tags_us FROM words WHERE id=?", (wid,)).fetchone()
        if row and set(json.loads(row[0])) == set(change["after"]):
            if set(word.get("phoneme_tags_us") or []) != set(change["after"]):
                raise ValueError(
                    f"refusing tag regression for {wid}; derive the corrected candidate"
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=int, choices=(300, 1000), required=True)
    args = parser.parse_args()
    content, patch = load_pack(args.pack)
    print(json.dumps(derive(content, patch), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
