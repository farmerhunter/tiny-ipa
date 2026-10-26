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

SQLite's online backup reader must lock the WAL shared-memory file. The backup
unit therefore keeps `/var/lib/tiny-ipa` read-only and grants write access only
to the existing regular, non-symlink `tiny-ipa.sqlite-shm` file. It does not
grant write access to the database, WAL, restore directory, or state root. If
the SHM file is absent, is not writable, has an unexpected type, or does not
have the same owner and group as the database when the backup entrypoint opens
it, the unit fails instead of creating it or treating the run as successful.
The controlled Jingyun runtime sets `TINY_IPA_KEEP_WAL_ANCHOR=true`: application
startup opens the existing database in WAL mode, completes one read, and keeps
that otherwise idle connection until process shutdown without holding a
transaction. This lets SQLite own the SHM lifecycle while the backup unit keeps
the source and state root read-only and grants write access only to the exact
existing SHM file. Missing or invalid SHM remains a backup failure; operators
must not create it with `touch`, manufacture it through HTTP traffic, or widen
the state root's write boundary.

The backup script is installed separately from the immutable application
release at `/opt/tiny-ipa/ops/<APPROVED_TOOL_REVISION>/p1a-backup.py`. The
revision is the full commit that supplied the reviewed tool bytes. Its
versioned directory and script are `root:root` mode `0555`, installation
refuses collisions, and no mutable `ops/current` pointer is created. The same
directory contains a frozen `root:root` mode `0444` backup unit template from
that revision; both files are hash-checked before unit materialization.

The trial now uses the same readonly H0, authorized H1-staging,
H1-activation, and H2 boundary as docs/15. Backup unit materialization uses a
collision-refusing file inside `/tmp/tiny-ipa-p1a`; it does not create a second
unowned `/tmp` path. Failure during dependency staging cannot reach the backup
root or units. Failure after activation follows the checked preserve-data
withdrawal and retains every backup/restore artifact.

For the first P1a trial, H1-activation exclusively creates the previously
absent source database and initializes it through the frozen release's current
`app.services.db_schema.init_db`. The accepted synthetic invariant is exactly
nine application tables with zero users and zero auth sessions, private mode,
matching owner, and `PRAGMA integrity_check=ok`. H2 must preserve that schema
and all-zero table counts in the online backup and separate restore. No account,
session, learner content, existing database migration, or provider call is part
of this witness.

## P1b non-empty trial and natural schedule gate

P1b reuses the versioned P1a backup tool and narrow SHM permission. A manual
oneshot against the earlier empty database is not P1b evidence. After the
reviewed Core 100 import, one private-input trial owner and a completed phone
practice flow, the source must contain non-zero, owner-consistent settings,
session, daily session, session item and attempt/progress state.

The P1b backup receipt records only release/tool IDs, snapshot ID, timestamp,
SHA-256, byte size, schema fingerprint, table counts and owner-consistency
booleans. The separate restore candidate must reproduce the content count and
relationships among the one owner, settings, practice group/items, attempts and
progress. It may use an isolated disposable application process for
representative reads, but never changes the active DB pointer or emits row
values, usernames, password hashes, cookies or session tokens.

Natural scheduling is distinct from a manually started service. The acceptance
receipt binds the timer's scheduled time, invocation ID and a newly created
complete snapshot to one naturally elapsed occurrence. If the occurrence has
not elapsed it remains `pending`. If it fails because the SQLite SHM file is
absent after an idle/restarted app, the run is failed evidence and the package
returns for the smallest reviewed fix; it must not widen write access to the
whole state root or silently invoke the API to manufacture success.

For the controlled public trial the API and timer remain disabled at boot and
the timer remains `Persistent=false`. The operator records the next manual
check and a named failure owner. Automatic pruning, missed-run catch-up,
notification credentials and off-host copying remain forbidden until Human
chooses concrete retention, notification and encrypted off-host policies. A
maximum of seven complete snapshots and 100 MiB per set remains fail-closed.

## Post-M14 trial retention — #309 repository candidate

The Human accepted strategy v1 on 2026-10-26 with **two fixed recovery points
plus two rolling backups**. This section supersedes the no-prune policy only
for an explicitly activated `rolling-backup` operation. The original `backup`
command and original service candidate retain their seven-snapshot/no-delete
behavior. This repository change does not authorize host installation or any
snapshot deletion. Review the concrete host execution list before applying it.

The fixed points are `20260916T095935Z` (user/content before attempts) and
`20260917T010641Z` (independently restored H7 witness). Daily operation retains
these two plus the two latest successful managed backups, ordered by their
recorded UTC creation time rather than directory names or modification times.
Normal replacement temporarily holds a fifth complete snapshot. Existing
legacy snapshots cannot silently become automatic cleanup candidates.

`rolling-backup` checks both protected snapshots, all complete manifests and
artifact checksums, and exact snapshot directory contents before creating a
new copy. Legacy snapshots may contain only the two recognized SQLite sidecars:
a regular, non-symlink zero-byte `tiny-ipa.sqlite.backup-wal` and/or a regular,
non-symlink 32768-byte `tiny-ipa.sqlite.backup-shm`. Nonempty WAL, unexpected
sizes/types or other files fail closed. These legacy files are preserved by
the tool; accepting their layout does not authorize their deletion. It publishes the verified new copy before unlinking the oldest
managed rolling copy. A nonblocking directory lock excludes another legacy,
bootstrap or rolling writer using this tool. Snapshot IDs, roots and artifacts
remain subject to the existing path/symlink checks. Keep the backup namespace
private to the service account; the lock is cooperative operator protection,
not protection against an adversarial process with the same Unix identity.

New managed copies are normalized to SQLite DELETE journal mode inside their
private incomplete directory, before checksum/verification and publication.
Only the destination copy changes journal mode; the live source remains WAL.
Managed directories must still contain exactly the DB and manifest, so later
sidecars are never silently adopted as automatic cleanup targets. Bounded
restore reads a verified, closed legacy artifact with `immutable=1` only after
checking its WAL is absent/empty and known sidecars are safe; the live source
never uses immutable reads. This avoids rewriting historical SHM or creating
new sidecars while validating a fixed recovery point.

Creation failure preserves all successful old copies. An interrupted managed
copy or a failed cleanup requires maintenance before another new copy; a
cleanup failure retains the new complete copy and returns nonzero. Unknown
objects, invalid checksums, missing protected points, unexpected files and
unmanaged legacy copies fail closed. No unknown, incomplete or restore
artifact is automatically removed.

The shared budget for backup root and restore-candidates is 1 GiB, including
incomplete files. Each new snapshot remains capped at 100 MiB; prechecks
reserve the full 100 MiB copy cap (including metadata) and leave at least 512 MiB free on
the target filesystem after copying. Bootstrap reserves space for both its
backup and separate restore. Post-copy budget checks precede automatic
cleanup. The bounded restore flag applies the same worst-case reservation, copy cap and
budget/free-space checks, and shares the backup-root writer lock.
These are limits, not preallocation. A growing source that exceeds the cap
fails; the operator must review the limit rather than bypass it.

### First migration: review before host effects

The steady-state limit is four, while the host currently has seven legacy
snapshots. A separate `bootstrap-backup` command accepts exactly seven
verified legacy snapshots, creates one managed eighth snapshot and **never
deletes anything**. It refuses a second bootstrap or a later rolling backup
until the old legacy excess has been resolved. The original protected copies
and every legacy copy remain in place throughout this first creation.

After a reviewed version has been installed and the timer stopped with no
backup service running, the candidate invocation is:

```bash
sudo -u tiny-ipa /opt/tiny-ipa/ops/<APPROVED_TOOL_REVISION>/p1a-backup.py \
  bootstrap-backup \
  --source /var/lib/tiny-ipa/tiny-ipa.sqlite \
  --state-root /var/lib/tiny-ipa \
  --destination-root /var/backups/tiny-ipa \
  --restore-root /var/lib/tiny-ipa/restore-candidates \
  --snapshot-id utc-now --release-id <APPROVED_RELEASE_ID> \
  --protect 20260916T095935Z --protect 20260917T010641Z \
  --writable-wal-shm /var/lib/tiny-ipa/tiny-ipa.sqlite-shm
```

Run it through the reviewed oneshot sandbox (temporarily materialize the
rolling candidate with `bootstrap-backup` replacing `rolling-backup`), not an
unrestricted shell invocation: the command above identifies its arguments,
not permission to widen the existing DB/WAL/state-root access boundary. The
API remains running; its current release and environment do not change.

Record that invocation's new snapshot ID and checksum. Independently restore
that exact artifact into a new, separate restore-candidates directory with
`verify-restore ... --bounded-storage`. Check SQLite integrity, foreign keys,
owner/settings and practice/attempt relationships against the fresh execution
baseline. Existing M14 phone/TLS acceptance is reused; no active DB pointer is
changed. Verification failure leaves every old copy intact and stops cleanup.

Before deletion, present the exact five legacy empty-copy IDs below, their
fresh checksums and retained receipt/manifest metadata for Human review:

- `20260915T101140Z`
- `shm-recovery-20260915t1118z`
- `20260916T025408Z`
- `20260916T032001Z`
- `p1b-prestate-20260916T084751Z`

On 2026-10-26 all five actual database files matched their manifests and shared
SHA-256 `8706e0c798be00c44238bc4ab10dcf13e0b3c2f5984277a62562b6a03852ff97`.
This identifies byte-identical cleanup candidates, not deletion authorization.
Host preflight later found the recognized zero-byte WAL and 32768-byte SHM in
every legacy snapshot directory. PR #311 was merged but not installed: its
strict two-file check stopped the migration before a new backup or deletion.
The follow-up layout fix requires a separately reviewed candidate and an
updated first-cleanup authorization listing these two additional files in
each of the same five named legacy directories. Never apply the original
two-file-only cleanup to this four-file layout. Preserve the two fixed
snapshots' sidecars and existing restore witnesses.
Preserve the original receipt and manifest metadata. Revalidate the exact IDs
and bytes immediately before an approved cleanup; never infer eligibility
from empty row counts, a glob or mtime. Do not delete the two fixed copies,
new bootstrap copy, old failure directory or restore witnesses. After all
five approved removals, there are two fixed copies plus one managed copy; the
next daily success fills the second rolling slot, and later successes replace
the oldest managed slot.

Install `tiny-ipa-backup-rolling.service.candidate` as the existing backup
service only through the reviewed root-owned, versioned tool/unit procedure.
Retain the old tool/unit for rollback, keep the original timer's daily
03:20 UTC / `Persistent=false` / boot-disabled settings, and read back its
actual next occurrence and installed command. Never activate the permanent
rolling service before migration cleanup is complete.

Rollback stops the timer, preserves every DB/backup/restore artifact, and
restores the old reviewed unit/tool binding and previous timer activity.
Read back service/tool and timer state. The old service may again fail at its
seven-snapshot cap; report that limitation instead of deleting more data.
Deletion is irreversible and rollback does not promise to recreate removed
snapshots. Do not restart the API or touch other applications for this change.

### Operating responsibility and accepted trial limits

The maintainer checks last successful time and service failure before each
trial and at least weekly; this is a manual responsibility, not an installed
notification or Codex schedule. Reboots still require the maintainer to start
the trial API/timer. The two latest successful backups do not imply two
calendar days or a strict recovery objective. Failures remain visible in
systemd and its journal; subsequent scheduled attempts do not bypass quantity,
space or integrity checks. Budget exhaustion and failed cleanup require an
explicit maintenance decision.

Same-VPS backups do not cover disk/host loss. Off-host storage, automatic
alerts, full user administration and production recovery commitments remain
deferred. Revisit these decisions before keeping irreplaceable learner data,
opening the application to real users or relying on unattended operation.
