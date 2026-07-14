from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROADMAP = ROOT / "docs" / "06-epic-roadmap.md"
RUNBOOK = ROOT / "docs" / "development.md"
AUDIO_DOC = ROOT / "docs" / "04-tts-audio.md"
BACKEND_MAIN = ROOT / "backend" / "app" / "main.py"
FRONTEND_API = ROOT / "frontend" / "src" / "api.ts"


def _normalised(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _m14_runbook() -> str:
    document = RUNBOOK.read_text(encoding="utf-8")
    start = document.index("## M14 frontend build and reverse-proxy routing contract")
    return " ".join(document[start:].split())


def test_m14_audio_variable_is_canonical_across_runtime_and_docs() -> None:
    assert '"TINY_IPA_AUDIO_DIR"' in BACKEND_MAIN.read_text(encoding="utf-8")

    for document in (ROADMAP, RUNBOOK, AUDIO_DOC):
        text = _normalised(document)
        assert "TINY_IPA_AUDIO_DIR" in text

    assert "TINY_IPA_AUDIO_ROOT" not in _normalised(ROADMAP)
    assert "TINY_IPA_AUDIO_ROOT` is not a supported alias" in _normalised(RUNBOOK)
    assert "TINY_IPA_AUDIO_ROOT` 没有兼容 alias" in _normalised(AUDIO_DOC)

    assert "TINY_IPA_AUDIO_DIR=<audio-dir>" in _normalised(RUNBOOK)
    assert "alias <audio-dir>/;" in _m14_runbook()


def test_m14_frontend_build_and_nginx_contract_matches_current_client() -> None:
    frontend_api = FRONTEND_API.read_text(encoding="utf-8")
    runbook = _m14_runbook()

    assert "VITE_API_BASE" in frontend_api
    assert "VITE_API_BASE_URL" not in frontend_api
    assert "VITE_API_BASE=/api pnpm run build" in runbook
    assert "VITE_API_BASE_URL` is not supported" in runbook

    for expected in (
        "location = /api/health",
        "location /api/",
        "location ^~ /audio/",
        "proxy_pass http://127.0.0.1:<backend-port>;",
        "root <frontend-dist-dir>;",
        "try_files $uri $uri/ /index.html;",
        "alias <audio-dir>/;",
    ):
        assert expected in runbook


def test_m14_reverse_proxy_contract_preserves_human_gates() -> None:
    runbook = _m14_runbook()

    for boundary in (
        "does not authorize an Nginx install",
        "Do not run Nginx writes/reloads",
        "#280 owns backup/restore",
        "#281 owns the final deployment smoke/rollback checklist",
    ):
        assert boundary in runbook
