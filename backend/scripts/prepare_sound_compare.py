"""Emit an opt-in development content candidate, without opening any database."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from correct_core100_tags import derive, load_corrections
from correct_expanded_tags import load_pack
from select_candidates import SUPPORTED_PHONEMES, estimate_syllable_count

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.sound_compare import validate_pair_evidence  # noqa: E402


def load_pairs(root: Path = ROOT) -> dict:
    manifest = json.loads((root / "content/sound_compare_pairs_candidate.json").read_text())
    validate_pair_evidence(manifest)
    if (
        manifest["schema"] != "tiny-ipa-sound-compare-candidate/v1"
        or manifest["status"] != "development-only"
    ):
        raise ValueError("unexpected comparison candidate contract")
    if set(manifest["sources"]) != {f"content/core_{n}_words.json" for n in (100, 300)}:
        raise ValueError("unexpected comparison sources")
    if manifest["audio_manifest"] != "deploy/jingyun/core100-content-audio.manifest.json":
        raise ValueError("unexpected audio manifest")
    audio_bytes = (root / manifest["audio_manifest"]).read_bytes()
    if hashlib.sha256(audio_bytes).hexdigest() != manifest["audio_manifest_sha256"]:
        raise ValueError("comparison audio binding changed")
    assets = {a["word_id"]: a for a in json.loads(audio_bytes)["audio"]["assets"]}
    sources = []
    for path, sha in manifest["sources"].items():
        raw = (root / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError("comparison source changed")
        sources.append({w["word_id"]: w for w in json.loads(raw)["words"]})
    for pair in manifest["pairs"]:
        for member in pair["members"]:
            wid, phones = member["word_id"], member["ordered_phones_us"]
            if any(p not in SUPPORTED_PHONEMES for p in phones):
                raise ValueError("invalid comparison word/phones")
            normalized = member["ipa_us"].replace("ɡ", "g")
            if (
                normalized != "/ˈ" + "".join(p[1:-1] for p in phones) + "/"
                or estimate_syllable_count(normalized) != 1
            ):
                raise ValueError("ordered phones/stress differ from bound monosyllabic IPA")
            for words in sources:
                word = words.get(wid)
                if (
                    not word
                    or word["ipa_us"] != member["ipa_us"]
                    or word["word"] != member["word_id"]
                    or member["before"] is not None
                    or word.get("minimal_pair_group") is not None
                    or word.get("content_status") == "disabled"
                ):
                    raise ValueError("comparison word preimage differs")
            asset = assets.get(wid)
            if (
                not asset
                or member["audio_url"] != f"/audio/{asset['path']}"
                or member["audio_sha256"] != asset["sha256"]
            ):
                raise ValueError("comparison recording binding differs")
    return manifest


def derive_pairs(content: dict, manifest: dict) -> dict:
    candidate = copy.deepcopy(content)
    groups = {m["word_id"]: pair["group"] for pair in manifest["pairs"] for m in pair["members"]}
    for word in candidate["words"]:
        if word["word_id"] in groups:
            word["minimal_pair_group"] = groups[word["word_id"]]
    return candidate


def candidate(size: int, root: Path = ROOT) -> dict:
    manifest = load_pairs(root)
    content, tags = load_corrections(root) if size == 100 else load_pack(size, root)
    if size not in (100, 300):
        raise ValueError("comparison candidate supports Entry only")
    return derive_pairs(derive(content, tags), manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=int, choices=(100, 300), default=300)
    args = parser.parse_args()
    print(json.dumps(candidate(args.pack), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
