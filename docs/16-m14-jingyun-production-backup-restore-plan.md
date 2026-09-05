# M14 Jingyun Production Backup and Restore Candidate Plan

CANDIDATE - DO NOT APPLY.

This plan describes a future Human-gated Tiny IPA production backup and restore
shape for `/var/backups/tiny-ipa`. It is not a backup command, restore command,
VPS access authorization, production database read authorization, in-place
restore authorization, cron job, systemd timer, off-host copy policy, or
retention decision.

## Scope Boundary

The production database candidate path is
`/var/lib/tiny-ipa/tiny-ipa.sqlite`. The production backup namespace candidate
is `/var/backups/tiny-ipa`. Backup owner
`<HUMAN_APPROVED_BACKUP_OWNER>` and retention policy
`<HUMAN_APPROVED_BACKUP_RETENTION_POLICY>` remain unresolved Human decisions.

#280 proved only a temporary fixture backup/restore method. It does not
authorize production data access, production backup creation, private database
copying, in-place restore, or retention cleanup.

## Candidate Backup Artifacts

When a later Human owner authorizes production backup creation, write separate
timestamped artifacts under the approved backup root:

```text
/var/backups/tiny-ipa/<timestamp>/tiny-ipa.sqlite.backup
/var/backups/tiny-ipa/<timestamp>/tiny-ipa.sqlite.quick_check.txt
/var/backups/tiny-ipa/<timestamp>/tiny-ipa.sqlite.sha256
/var/backups/tiny-ipa/<timestamp>/manifest.txt
```

The manifest should include release ID, database source path, backup artifact
path, `/opt/tiny-ipa/current/REVISION` identity, live `/api/version` identity,
previous release ID, rollback pointer, sanitized SQLite `PRAGMA quick_check`
result, checksum, operator, and retention owner. It must not include user rows,
password hashes, session token hashes, secrets, cookies, certificate paths, SSH
keys, or private learner data.

The release ID, checked-in or generated `REVISION` file, and live
`/api/version` response must agree before the backup can be treated as a
release rollback artifact. Stop when a backup manifest cannot name both the
current release and the previous active release path.

## Restore Candidate

Restore is a separate later authorization owned by
`<HUMAN_APPROVED_ROLLBACK_OWNER>`. A restore must first target a separate path,
never the only known-good production database:

```text
/var/lib/tiny-ipa/restore-candidates/<timestamp>/tiny-ipa.sqlite
```

After copying into the separate restore candidate path, run integrity checks,
schema/table-count comparison, application health against an explicitly
approved disposable or maintenance-mode target, and Xue Tu Zhi Ban baseline
health. Only a later Human decision may authorize changing an active database
pointer or restarting `tiny-ipa-api.service`.

## Stop Conditions

Stop before backup or restore if any of these are true:

- the database source is not exactly `/var/lib/tiny-ipa/tiny-ipa.sqlite`;
- the backup destination is outside `/var/backups/tiny-ipa`;
- the restore target is the active production database path;
- backup owner, retention policy, or rollback owner is missing;
- release ID, `/api/version`, `REVISION`, previous release, or rollback pointer
  evidence is missing or inconsistent;
- Xue Tu Zhi Ban baseline health evidence is absent;
- the action would read, copy, delete, overwrite, or restore another
  application's data;
- the evidence would expose secrets, cookies, session tokens, SSH keys,
  certificate files, password hashes, or private learner rows.

## Retention and Cleanup

Retention cleanup is not part of this candidate. A later Human decision must
define `<HUMAN_APPROVED_BACKUP_RETENTION_POLICY>`, off-host copy policy, and the
accountable owner before any deletion command is reviewed. A successful #280
temporary dry run is method evidence only; it is not a production retention or
restore gate.
