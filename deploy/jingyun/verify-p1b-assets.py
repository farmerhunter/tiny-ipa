#!/usr/bin/env python3
"""CANDIDATE - DO NOT APPLY. Verify frozen P1b content and audio assets."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    root_metadata = root.lstat()
    if stat.S_ISLNK(root_metadata.st_mode):
        raise VerificationError("asset root is a symlink")
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise VerificationError("asset root is not a directory")
    root = root.resolve(strict=True)
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


def _mpeg_layer_iii_frame_length(header: bytes) -> int | None:
    if len(header) != 4:
        return None
    value = int.from_bytes(header, "big")
    if value >> 21 != 0x7FF:
        return None
    version = (value >> 19) & 0x3
    layer = (value >> 17) & 0x3
    bitrate_index = (value >> 12) & 0xF
    sample_rate_index = (value >> 10) & 0x3
    padding = (value >> 9) & 0x1
    if version == 1 or layer != 1 or bitrate_index in (0, 15) or sample_rate_index == 3:
        return None
    bitrates = (
        (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320),
        (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160),
    )
    sample_rates = {
        3: (44100, 48000, 32000),
        2: (22050, 24000, 16000),
        0: (11025, 12000, 8000),
    }
    bitrate = bitrates[0 if version == 3 else 1][bitrate_index]
    sample_rate = sample_rates[version][sample_rate_index]
    coefficient = 144000 if version == 3 else 72000
    return coefficient * bitrate // sample_rate + padding


def _verify_mp3(path: Path) -> None:
    maximum = 10 * 1024 * 1024
    size = path.stat().st_size
    if size > maximum:
        raise VerificationError("audio exceeds size limit")
    payload = path.read_bytes()
    offset = 0
    if payload.startswith(b"ID3"):
        if len(payload) < 10 or payload[3] == 0xFF or any(byte & 0x80 for byte in payload[6:10]):
            raise VerificationError("invalid ID3 header")
        tag_size = sum(byte << shift for byte, shift in zip(payload[6:10], (21, 14, 7, 0)))
        offset = 10 + tag_size + (10 if payload[5] & 0x10 else 0)
    first_length = _mpeg_layer_iii_frame_length(payload[offset:offset + 4])
    if first_length is None or offset + first_length > len(payload):
        raise VerificationError("audio lacks a complete MPEG Layer III frame")
    second_offset = offset + first_length
    second_length = _mpeg_layer_iii_frame_length(payload[second_offset:second_offset + 4])
    if second_length is None or second_offset + second_length > len(payload):
        raise VerificationError("audio lacks two consecutive MPEG Layer III frames")


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
        if size <= 0 or size != asset["bytes"]:
            raise VerificationError("audio size mismatch")
        _verify_mp3(path)
        if _sha256(path) != asset["sha256"]:
            raise VerificationError("audio checksum mismatch")
        seen.add(word_id)
        total_bytes += size
    if seen != set(required):
        raise VerificationError("audio coverage incomplete")

    return {
        "status": "verified",
        "word_count": len(words),
        "audio_count": len(assets),
        "audio_bytes": total_bytes,
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
