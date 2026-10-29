#!/usr/bin/env python3
"""Prepare an explicit Core100/Core300 audio candidate locally; never install it on a host."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "core100_asset_verifier", REPO / "deploy/jingyun/verify-p1b-assets.py"
)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _directory(path: Path, allowed: Path) -> Path:
    absolute = path.absolute()
    for parent in (absolute, *absolute.parents):
        if parent.is_symlink():
            raise ValueError("candidate paths must not contain symlinks")
    resolved = absolute.resolve()
    if allowed.resolve() not in resolved.parents:
        raise ValueError("output must be a local candidate or temporary directory")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _write(path: Path, data: bytes, expected: str) -> None:
    if digest(data) != expected:
        raise ValueError(f"checksum mismatch: {path.name}")
    if path.is_symlink():
        raise ValueError("candidate file must not be a symlink")
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite different existing bytes: {path.name}")
        return
    with path.open("xb") as stream:
        stream.write(data)


def download(url: str) -> bytes:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
    ):
        raise ValueError("invalid audio source URL")
    if not (
        parsed.hostname == "upload.wikimedia.org"
        and parsed.path.startswith("/wikipedia/commons/")
        or parsed.hostname == "ipa.jingyun.bj.cn"
        and parsed.path.startswith("/audio/us/")
    ):
        raise ValueError("audio source host/path is not allowed")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TinyIPA-audio-package/1.0 (https://github.com/farmerhunter/tiny-ipa)"
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname != parsed.hostname:
            raise ValueError("cross-host audio redirect refused")
        data = response.read(10 * 1024 * 1024 + 1)
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError("audio source exceeds the package size limit")
    return data


def check_media(path: Path) -> dict:
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_name,codec_type,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    value = json.loads(probe.stdout)
    streams = value.get("streams", [])
    duration = float(value["format"]["duration"])
    if not (0.15 <= duration <= 5 and value["format"]["format_name"] == "mp3"):
        raise ValueError(f"invalid pronunciation media duration/format: {path.name}")
    if len(streams) != 1 or streams[0].get("codec_name") != "mp3":
        raise ValueError(f"expected one MP3 stream: {path.name}")
    if int(streams[0]["sample_rate"]) < 16000:
        raise ValueError(f"unexpected pronunciation sample rate: {path.name}")
    decoded = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "info",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    peak = re.search(r"max_volume: ([-\w.]+) dB", decoded.stderr)
    if not peak or not math.isfinite(float(peak[1])) or float(peak[1]) < -50:
        raise ValueError(f"silent or excessively quiet pronunciation: {path.name}")
    return {"duration_seconds": duration, "peak_db": float(peak[1]), "decoded": True}


def prepare(
    manifest_path: Path,
    repo_root: Path,
    audio_root: Path,
    cache_root: Path,
    *,
    pack_size: int = 100,
    allow_download: bool = False,
    validate_media: bool = False,
    fetcher=download,
) -> dict:
    if pack_size not in (100, 300):
        raise ValueError("audio preparation supports only explicit Core100/Core300 candidates")
    manifest = json.loads(manifest_path.read_text())
    build = manifest["build"]
    source_name = f"content/core_{pack_size}_words.json"
    candidate_name = f"content/generated/core_{pack_size}_audio_candidate.json"
    if build["source_content"] != source_name:
        raise ValueError("unexpected source content binding")
    if manifest["content"]["path"] != candidate_name:
        raise ValueError("unexpected generated content binding")
    source_path = VERIFIER._regular_under(repo_root, build["source_content"])
    source_bytes = source_path.read_bytes()
    if digest(source_bytes) != build["source_content_sha256"]:
        raise ValueError("source content checksum mismatch")
    content = json.loads(source_bytes)
    if pack_size == 300:
        from correct_core100_tags import derive
        from correct_expanded_tags import load_pack

        correction_path = "content/core_300_phoneme_corrections.json"
        if build.get("tag_corrections") != {
            "path": correction_path,
            "sha256": digest(VERIFIER._regular_under(repo_root, correction_path).read_bytes()),
        }:
            raise ValueError("Core300 corrected-tag provenance differs")
        original, patch = load_pack(300, repo_root)
        content = derive(original, patch)
        old_path = "deploy/jingyun/core100-content-audio.manifest.json"
        old_bytes = VERIFIER._regular_under(repo_root, old_path).read_bytes()
        if build.get("reuse_manifest") != {"path": old_path, "sha256": digest(old_bytes)}:
            raise ValueError("Core100 reuse manifest binding differs")
        reused = json.loads(old_bytes)["audio"]["assets"]
        current = {a["word_id"]: a for a in manifest["audio"]["assets"]}
        if len(reused) != 99 or any(current.get(a["word_id"]) != a for a in reused):
            raise ValueError("Core300 must preserve all 99 Core100 asset bindings")
        additions = set(current) - {a["word_id"] for a in reused}
        if len(additions) > 12 or set(build.get("new_word_ids", [])) != additions:
            raise ValueError("Core300 addition list exceeds or differs from the bounded selection")
    required = manifest["audio"]["required_word_ids"]
    assets = manifest["audio"]["assets"]
    word_ids = {word["word_id"] for word in content["words"]}
    disabled = {w["word_id"] for w in content["words"] if w.get("content_status") == "disabled"}
    if pack_size == 300 and set(build.get("disabled_word_ids", [])) != disabled:
        raise ValueError("disabled-word report disagrees with source")
    if set(required) & disabled:
        raise ValueError("disabled words must not have active packaged audio")
    if len(required) != len(set(required)) or not set(required) <= word_ids:
        raise ValueError("invalid audio word coverage")
    if set(build["missing_word_ids"]) != word_ids - set(required):
        raise ValueError("missing-word report disagrees with coverage")
    if set(build["sources"]) != set(required) or len(assets) != len(required):
        raise ValueError("source mapping disagrees with coverage")
    if {asset["word_id"] for asset in assets} != set(required):
        raise ValueError("asset identities disagree with coverage")
    for asset in assets:
        wid = asset["word_id"]
        if not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]):
            raise ValueError("invalid audio checksum")
        if not 0 < asset["bytes"] <= 10 * 1024 * 1024:
            raise ValueError("invalid audio byte size")
        if not re.fullmatch(r"[a-z]+", wid) or asset["path"] != f"us/{wid}.mp3":
            raise ValueError("unsafe audio asset path")
        if build["sources"][wid]["sha256"] != asset["sha256"]:
            raise ValueError("source/output checksum binding mismatch")
    for word in content["words"]:
        word["audio_us"] = (
            f"/audio/us/{word['word_id']}.mp3" if word["word_id"] in required else None
        )
    derived = (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode()
    generated = _directory(repo_root / "content/generated", repo_root / "content")
    _write(generated / Path(candidate_name).name, derived, manifest["content"]["sha256"])
    temp_root = Path(tempfile.gettempdir()).resolve()
    allowed = (
        repo_root / "audio" if repo_root.resolve() in audio_root.resolve().parents else temp_root
    )
    audio_root = _directory(audio_root, allowed)
    allowed_cache = (
        repo_root / "content/sources"
        if repo_root.resolve() in cache_root.resolve().parents
        else temp_root
    )
    cache_root = _directory(cache_root, allowed_cache)
    us = _directory(audio_root / "us", audio_root)
    credits = VERIFIER._regular_under(
        repo_root, f"deploy/jingyun/core{pack_size}-audio-attribution.md"
    )
    _write(
        audio_root / VERIFIER._credits_relative(manifest["audio"]["credits"]),
        credits.read_bytes(),
        manifest["audio"]["credits"]["sha256"],
    )
    media = {}
    for asset in assets:
        wid = asset["word_id"]
        destination = us / f"{wid}.mp3"
        cached = cache_root / f"{asset['sha256']}.mp3"
        legacy = repo_root / "audio/us" / f"{wid}.mp3"
        if destination.is_symlink() or cached.is_symlink() or legacy.is_symlink():
            raise ValueError("audio inputs must not be symlinks")
        if destination.exists():
            data = destination.read_bytes()
        elif cached.exists():
            data = cached.read_bytes()
        elif legacy.exists() and digest(legacy.read_bytes()) == asset["sha256"]:
            data = legacy.read_bytes()
        elif allow_download:
            data = fetcher(build["sources"][wid]["url"])
            if fetcher is download:
                time.sleep(5)
            _write(cached, data, asset["sha256"])
        else:
            raise ValueError(f"missing cached audio; explicit --allow-download required: {wid}")
        _write(destination, data, asset["sha256"])
        if validate_media:
            media[wid] = check_media(destination)
    result = VERIFIER.verify(manifest_path, repo_root, audio_root)
    return {
        **result,
        "missing_word_ids": build["missing_word_ids"],
        "pack_size": pack_size,
        "media_checked": len(media),
        "media": media,
        "evidence_scope": "integrity/decoding/playback only; human phonetic acceptance deferred",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=int, choices=(100, 300), default=100)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--audio-root", type=Path)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--check-media", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.check_media and not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe")):
        parser.error("--check-media requires ffmpeg and ffprobe")
    result = prepare(
        args.manifest or REPO / f"deploy/jingyun/core{args.pack}-content-audio.manifest.json",
        REPO,
        args.audio_root or REPO / f"audio/core{args.pack}-candidate",
        args.cache_root or REPO / f"content/sources/core{args.pack}-audio",
        pack_size=args.pack,
        allow_download=args.allow_download,
        validate_media=args.check_media,
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "media"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
