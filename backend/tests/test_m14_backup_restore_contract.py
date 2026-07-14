from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "development.md"


def _runbook_text() -> str:
    document = DOC.read_text(encoding="utf-8")
    start = document.index("## M14 SQLite backup and restore dry-run")
    return " ".join(document[start:].split())


def test_m14_backup_restore_runbook_fails_closed_on_data_boundaries() -> None:
    runbook = _runbook_text()

    for phrase in (
        "not a production backup command",
        "operating system temporary directory",
        "rejects repository and production paths",
        "separate new restore target",
        "PRAGMA quick_check",
        "It never prints user rows, password hashes, session token hashes, or secrets.",
        "Do not add overwrite, owner-claim apply, cron, systemd, or remote-copy behavior",
        "#281 owns the all-system smoke/rollback checklist",
    ):
        assert phrase in runbook
