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
Those placeholders apply to production/real-data operation. P1a fixes the
synthetic-only operator to `tiny-ipa`, permits at most seven complete snapshots,
and never deletes; it does not settle the later production retention policy.

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
deployment kind, verified previous-release state, sanitized SQLite `PRAGMA quick_check`
result, checksum, operator, and retention owner. It must not include user rows,
password hashes, session token hashes, secrets, cookies, certificate paths, SSH
keys, or private learner data.

The release ID, checked-in or generated `REVISION` file, and live
`/api/version` response must agree before accepting a current-release backup.
Record source, timestamp, integrity result, checksum, backup owner and retention
policy. The first release may have `previous_release=none` when the first-install
pre-state verified absence as defined in docs/15; unknown or missing history
is not verified absence. A current-release backup does not require an older
release and does not authorize restore.

An upgrade rollback package additionally requires the real previous release,
both backend/frontend pointers, matching non-secret environment identity,
recovery owner and database compatibility evidence from docs/15. A backup of
the current database alone does not prove compatibility with previous code.
Keep new data and recovery evidence; never silently roll back or restore data.

These synthetic current-backup records complement the lifecycle examples in
docs/15. Tests validate both cases; they are not production evidence.

```json
[
  {"kind": "first_install", "previous_release": "none", "pre_state": "verified_absent",
   "current_identity_matches": true, "source": "/var/lib/tiny-ipa/tiny-ipa.sqlite",
   "timestamp": "example-time", "integrity": "ok", "checksum": "example-checksum",
   "backup_owner": "example-owner", "retention": "example-policy"},
  {"kind": "upgrade", "previous_release": "example-v1", "pre_state": "verified_existing",
   "current_identity_matches": true, "source": "/var/lib/tiny-ipa/tiny-ipa.sqlite",
   "timestamp": "example-time", "integrity": "ok", "checksum": "example-checksum",
   "backup_owner": "example-owner", "retention": "example-policy"}
]
```

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
- current release ID, `/api/version`, `REVISION` or verified deployment-kind
  evidence is missing or inconsistent;
- an upgrade rollback package lacks previous release, backend/frontend pointers,
  matching environment identity or database compatibility evidence;
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

## P1a Synthetic Trial Operation

`deploy/jingyun/p1a-backup.py` turns the #280 online SQLite method into a
bounded candidate for new synthetic trial state. Every invocation requires an
explicit source, declared root, destination, release ID, and limits. It rejects
symlink components, paths outside declared roots, unsafe IDs, collisions,
invalid checksums, a backup larger than 100 MiB, and an eighth complete
snapshot. It never deletes an older snapshot.

While a backup is being created it remains under
`.incomplete-<snapshot-id>`. Only a verified SQLite copy with `quick_check=ok`,
schema fingerprint, table counts, byte size, and SHA-256 is renamed to the final
snapshot directory with a `status=complete` manifest. A precheck failure writes
nothing; a failure after creation leaves a bounded `.incomplete-*` directory
with a `FAILED` marker and never becomes a valid snapshot. The manifest and output
exclude rows, cookies, token values, password hashes, secrets, certificates,
raw response headers, and query data.

Restore verification is a separate explicit command. It verifies the supplied
SHA-256, creates a new
`/var/lib/tiny-ipa/restore-candidates/<trial-id>/tiny-ipa.sqlite`, uses SQLite
online backup semantics, and compares integrity, schema fingerprint, and table
counts with the backup. It refuses an existing restore trial and never changes
the active database pointer or starts a service.

The candidate timer runs daily at 03:20 UTC with `Persistent=false`. During
P1a it is started without `enable`, after one observed oneshot succeeds. A
future scheduled run remains `pending` until observed. At the retention or size
cap the service fails and the operator records the failure. Automatic prune,
off-host copy, in-place restore, real user data, and a disaster-recovery/RPO
claim remain outside P1a.

The trial now uses the same readonly H0, authorized H1-staging,
H1-activation, and H2 boundary as docs/15. Backup unit materialization uses a
collision-refusing file inside `/tmp/tiny-ipa-p1a`; it does not create a second
unowned `/tmp` path. Failure during dependency staging cannot reach the backup
root or units. Failure after activation follows the checked preserve-data
withdrawal and retains every backup/restore artifact.
