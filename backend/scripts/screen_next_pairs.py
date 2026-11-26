"""Deterministic offline comparison screening; never mutate a database."""

from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

from content_activation import media
from insert_core300_increment import source
from prepare_sound_compare import ROOT, load_pairs
from select_candidates import SUPPORTED_PHONEMES, estimate_syllable_count, parse_ipa_to_phonemes

from app.services.sound_compare import validate_pair_evidence

NEW_IDS = frozenset(("fun", "sun", "cup", "cut"))


def baseline(root: Path = ROOT):
    selected, _, original, old, _, _ = source(root)
    words = {w["word_id"]: w for w in [*original, *selected]}
    manifest = json.loads((root / "deploy/jingyun/core300-content-audio.manifest.json").read_text())
    assets = {a["word_id"]: a for a in manifest["audio"]["assets"]}
    if len(assets) != 111 or not set(assets) <= set(words):
        raise ValueError("screening requires the frozen111 recording set")
    return words, assets, old


def ordered(word):
    phones, unknown = parse_ipa_to_phonemes(word["ipa_us"])
    if (
        unknown
        or len(phones) < 2
        or any(p not in SUPPORTED_PHONEMES for p in phones)
        or word["ipa_us"].replace("ɡ", "g") != "/ˈ" + "".join(p[1:-1] for p in phones) + "/"
        or estimate_syllable_count(word["ipa_us"]) != 1
    ):
        return None
    return phones


def load_next(root: Path = ROOT):
    manifest = json.loads((root / "content/sound_compare_next_pairs_candidate.json").read_text())
    validate_pair_evidence(manifest, SUPPORTED_PHONEMES)
    words, assets, old = baseline(root)
    old_ids = {m["word_id"] for p in old["pairs"] for m in p["members"]}
    if (
        manifest["sources"] != old["sources"]
        or manifest["audio_manifest"] != old["audio_manifest"]
        or manifest["audio_manifest_sha256"] != old["audio_manifest_sha256"]
        or manifest["base_evidence_sha256"]
        != hashlib.sha256(
            (root / "content/sound_compare_pairs_candidate.json").read_bytes()
        ).hexdigest()
        or manifest["tag_correction_sha256"]
        != hashlib.sha256(
            (root / "content/core_100_phoneme_corrections.json").read_bytes()
        ).hexdigest()
        or len(manifest["pairs"]) != 2
    ):
        raise ValueError("next-pair provenance changed")
    members = [m for p in manifest["pairs"] for m in p["members"]]
    if {m["word_id"] for m in members} != NEW_IDS or NEW_IDS & old_ids:
        raise ValueError("next pair members must be disjoint from original groups")
    if {p["group"] for p in manifest["pairs"]} & {p["group"] for p in old["pairs"]}:
        raise ValueError("next group identity collides with original group")
    for member in members:
        word, asset = words[member["word_id"]], assets[member["word_id"]]
        if (
            member["before"] is not None
            or member["ipa_us"] != word["ipa_us"]
            or member["ordered_phones_us"] != ordered(word)
            or member["source_tags_us"] != word["phoneme_tags_us"]
            or member["audio_url"] != "/audio/" + asset["path"]
            or member["audio_sha256"] != asset["sha256"]
        ):
            raise ValueError("next pair source/ordered-IPA/audio identity differs")
    return manifest


def screen(root: Path = ROOT, audio_root: Path | None = None):
    words, assets, old = baseline(root)
    if audio_root is not None:
        media(audio_root, list(assets.values()))
    old_ids = {m["word_id"] for p in old["pairs"] for m in p["members"]}
    eligible = {
        wid: ordered(words[wid])
        for wid in sorted(assets)
        if wid not in old_ids
        and words[wid]["word"] == wid
        and words[wid]["level"] == "beginner"
        and words[wid]["content_status"] != "disabled"
    }
    eligible = {wid: phones for wid, phones in eligible.items() if phones is not None}
    existing_contrasts = {
        frozenset(m["ordered_phones_us"][pair["contrast_index"]] for m in pair["members"])
        for pair in old["pairs"]
    }
    candidates = []
    for left, right in itertools.combinations(sorted(eligible), 2):
        a, b = eligible[left], eligible[right]
        differences = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(a) == len(b) and len(differences) == 1 and differences[0] in (0, len(a) - 1):
            index = differences[0]
            if frozenset((a[index], b[index])) not in existing_contrasts:
                candidates.append(
                    {
                        "word_ids": [left, right],
                        "position": "initial" if index == 0 else "final",
                        "contrast": [a[index], b[index]],
                    }
                )
    selected = load_next(root)
    for pair in selected["pairs"]:
        ids = sorted(m["word_id"] for m in pair["members"])
        if not any(c["word_ids"] == ids for c in candidates):
            raise ValueError("selected pair is absent from deterministic screen")
    return {
        "status": "development-only",
        "recording_count": 111,
        "media_check": "all111-bytes-verified" if audio_root is not None else "manifest-bound-only",
        "excluded_existing_members": sorted(old_ids),
        "excluded_existing_contrasts": sorted(sorted(c) for c in existing_contrasts),
        "eligible_word_count": len(eligible),
        "candidates": candidates,
        "selected_groups": selected["pairs"],
        "selection_effect": "two disjoint new contrasts; no automatic DB activation",
    }


def combined_evidence(root: Path = ROOT):
    old = copy.deepcopy(load_pairs(root))
    old["pairs"].extend(copy.deepcopy(load_next(root)["pairs"]))
    validate_pair_evidence(old, SUPPORTED_PHONEMES)
    if len(old["pairs"]) != 6:
        raise ValueError("expected four existing plus two candidate groups")
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--audio-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(screen(args.repo_root, args.audio_root), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
