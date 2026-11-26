"""Prepare a frozen three-word audio candidate without a database or network target."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from correct_core100_tags import derive
from correct_expanded_tags import load_pack
from prepare_core100_audio import REPO, VERIFIER, _directory, _write, check_media
from validate_content import import_structure_errors, load_phoneme_set, validate_words

SELECTED = frozenset(("family", "how", "better"))


def candidate(root: Path = REPO):
    manifest = json.loads(
        VERIFIER._regular_under(root, "content/core300_next_audio_candidate.json").read_text()
    )
    if (
        manifest["schema"] != "tiny-ipa-next-core300-audio-candidate/v1"
        or manifest["status"] != "development-only"
        or manifest["existing_word_attachments"]
        or {a["word_id"] for a in manifest["selected_new_words"]} != SELECTED
        or len(manifest["selected_new_words"]) != 3
    ):
        raise ValueError("expected three new words and no existing-word attachments")
    required_bindings = {
        "content/core_300_words.json",
        "content/core_300_phoneme_corrections.json",
        "deploy/jingyun/core300-content-audio.manifest.json",
        "content/phonemes.json",
    }
    if set(manifest["source_bindings"]) != required_bindings:
        raise ValueError("next candidate source binding set differs")
    for name, checksum in manifest["source_bindings"].items():
        if hashlib.sha256(VERIFIER._regular_under(root, name).read_bytes()).hexdigest() != checksum:
            raise ValueError("next candidate source changed")
    raw, patch = load_pack(300, root)
    words = {w["word_id"]: w for w in derive(raw, patch)["words"]}
    selected = []
    for asset in manifest["selected_new_words"]:
        wid = asset["word_id"]
        if (
            asset["path"] != f"us/{wid}.mp3"
            or asset["license"] != "CC BY-SA 3.0"
            or not (
                "US English" in asset["accent_evidence"]
                or "United States English" in asset["accent_evidence"]
            )
            or not 0 < asset["bytes"] < 10485760
        ):
            raise ValueError("unqualified next audio asset")
        word = words[wid].copy()
        if (
            word["level"] != "beginner"
            or word["content_status"] == "disabled"
            or not any("\u4e00" <= ch <= "\u9fff" for ch in word["meaning_zh"])
        ):
            raise ValueError("next word source status or meaning differs")
        word["audio_us"] = f"/audio/{asset['path']}"
        selected.append(word)
    if (
        import_structure_errors(selected)
        or validate_words(selected, load_phoneme_set(root / "content/phonemes.json"))["errors"]
    ):
        raise ValueError("invalid next candidate word fields")
    credits = manifest["credits"]
    if (
        hashlib.sha256(VERIFIER._regular_under(root, credits["source"]).read_bytes()).hexdigest()
        != credits["sha256"]
    ):
        raise ValueError("next candidate attribution differs")
    if credits["path"] != f"ATTRIBUTION-{credits['sha256'][:16]}.md":
        raise ValueError("unsafe next attribution path")
    return selected, manifest


def prepare(root: Path, audio_root: Path, cache: Path, *, decode=False):
    words, manifest = candidate(root)
    allowed = (
        root / "audio"
        if root.resolve() in audio_root.resolve().parents
        else Path(tempfile.gettempdir()).resolve()
    )
    audio_root = _directory(audio_root, allowed)
    _directory(audio_root / "us", audio_root)
    for asset in manifest["selected_new_words"]:
        data = VERIFIER._regular_under(cache, asset["sha256"] + ".mp3").read_bytes()
        if len(data) != asset["bytes"]:
            raise ValueError("next cached asset size differs")
        target = audio_root / asset["path"]
        _write(target, data, asset["sha256"])
        if decode:
            check_media(target)
    credits = manifest["credits"]
    _write(audio_root / credits["path"], (root / credits["source"]).read_bytes(), credits["sha256"])
    return {
        "status": "offline-candidate-prepared",
        "audio_count": 3,
        "audio_bytes": sum(a["bytes"] for a in manifest["selected_new_words"]),
        "new_words": words,
        "existing_word_attachments": [],
        "deferred_ids": [d["word_id"] for d in manifest["deferrals"]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--check-media", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(args.repo_root, args.audio_root, args.cache_root, decode=args.check_media),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
