#!/usr/bin/env python3
"""CANDIDATE - DO NOT APPLY. Verify frozen P1b content and audio assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath


class VerificationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_under(root: Path, relative: str) -> Path:
    value = PurePosixPath(relative)
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise VerificationError("unsafe relative path")
    declared_root = Path(os.path.abspath(root))
    current_root = Path(declared_root.anchor)
    for part in declared_root.parts[1:]:
        current_root /= part
        if stat.S_ISLNK(current_root.lstat().st_mode):
            raise VerificationError("asset root has a symlink component")
    root_metadata = declared_root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise VerificationError("asset root is not a directory")
    root = declared_root.resolve(strict=True)
    current = root
    for part in value.parts:
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise VerificationError("symlink path component")
    resolved = current.resolve(strict=True)
    if resolved.parent != root and root not in resolved.parents:
        raise VerificationError("path escaped root")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise VerificationError("asset is not a regular file")
    return resolved


def verify(manifest_path: Path, repo_root: Path, audio_root: Path) -> dict[str, object]:
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value.get("schema") != "tiny-ipa-p1b-content-audio/v1":
        raise VerificationError("manifest schema mismatch")
    if value.get("status") != "ready":
        raise VerificationError(f"manifest status is {value.get('status', 'missing')}")
    if value.get("frontend") != {
        "api_base": "/api",
        "build_revision_binding": "frozen_operator_packet",
    }:
        raise VerificationError("frontend binding mismatch")

    content = value.get("content")
    if not isinstance(content, dict):
        raise VerificationError("content binding missing")
    if content.get("import_content_level") != "auto":
        raise VerificationError("content import level mismatch")
    content_path = _regular_under(repo_root, content.get("path", ""))
    phonemes_path = _regular_under(repo_root, content.get("phonemes_path", ""))
    if _sha256(content_path) != content.get("sha256"):
        raise VerificationError("content checksum mismatch")
    if _sha256(phonemes_path) != content.get("phonemes_sha256"):
        raise VerificationError("phoneme checksum mismatch")
    words_value = json.loads(content_path.read_text(encoding="utf-8"))
    words = words_value.get("words") if isinstance(words_value, dict) else None
    if not isinstance(words, list) or len(words) != content.get("word_count"):
        raise VerificationError("content word count mismatch")
    words_by_id = {item.get("word_id"): item for item in words if isinstance(item, dict)}

    audio = value.get("audio")
    if not isinstance(audio, dict) or audio.get("host_root") != "/var/lib/tiny-ipa/audio":
        raise VerificationError("audio root binding mismatch")
    required = audio.get("required_word_ids")
    assets = audio.get("assets")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        raise VerificationError("required word ids invalid")
    if not isinstance(assets, list) or len(assets) != len(required):
        raise VerificationError("audio coverage incomplete")

    credits = audio.get("credits")
    if not isinstance(credits, dict) or set(credits) != {"path", "public_url", "sha256"}:
        raise VerificationError("audio credits binding missing")
    if credits["path"] != "ATTRIBUTION.md" or credits["public_url"] != "/audio/ATTRIBUTION.md":
        raise VerificationError("audio credits path mismatch")
    credits_path = _regular_under(audio_root, credits["path"])
    if _sha256(credits_path) != credits["sha256"]:
        raise VerificationError("audio credits checksum mismatch")

    seen: set[str] = set()
    total_bytes = 0
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {
            "word_id", "path", "sha256", "bytes", "source", "license"
        }:
            raise VerificationError("audio asset shape mismatch")
        word_id = asset["word_id"]
        if word_id in seen or word_id not in required or word_id not in words_by_id:
            raise VerificationError("audio word binding mismatch")
        if not isinstance(asset["source"], str) or not asset["source"].strip():
            raise VerificationError("audio source missing")
        if not isinstance(asset["license"], str) or not asset["license"].strip():
            raise VerificationError("audio license missing")
        expected_path = f"us/{word_id}.mp3"
        if asset["path"] != expected_path:
            raise VerificationError("audio path mismatch")
        if words_by_id[word_id].get("audio_us") != f"/audio/{expected_path}":
            raise VerificationError("content audio URL mismatch")
        path = _regular_under(audio_root, asset["path"])
        size = path.stat().st_size
        if size <= 0 or size > 10 * 1024 * 1024 or size != asset["bytes"]:
            raise VerificationError("audio size mismatch")
        if _sha256(path) != asset["sha256"]:
            raise VerificationError("audio checksum mismatch")
        seen.add(word_id)
        total_bytes += size
    if seen != set(required):
        raise VerificationError("audio coverage incomplete")

    return {
        "status": "manifest_integrity_verified",
        "word_count": len(words),
        "audio_count": len(assets),
        "audio_bytes": total_bytes,
        "credits_sha256": credits["sha256"],
        "content_sha256": content["sha256"],
        "phonemes_sha256": content["phonemes_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--audio-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.manifest, args.repo_root, args.audio_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, VerificationError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
