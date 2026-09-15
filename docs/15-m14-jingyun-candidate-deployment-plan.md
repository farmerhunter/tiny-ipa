# M14 Jingyun Candidate Deployment Plan

CANDIDATE - DO NOT APPLY.

This is a repository-only staging plan for the Tiny IPA namespace accepted for
candidate generation: `ipa.jingyun.bj.cn`, `/opt/tiny-ipa`,
`/var/www/tiny-ipa`, `/var/lib/tiny-ipa`, `/var/backups/tiny-ipa`,
`tiny-ipa-api.service`, and backend bind `127.0.0.1:18110`.

This plan does not authorize SSH, VPS reads, package installation, host writes,
operating-system user or directory creation, secret generation, database
creation or mutation, systemd/Nginx/firewall/DNS/TLS changes, service
start/restart/reload, backup, restore, rollback, or deployment.

## Candidate Artifact Set

- `deploy/jingyun/tiny-ipa-api.service.candidate`: review-only systemd unit.
- `deploy/jingyun/ipa.jingyun.bj.cn.nginx.candidate`: review-only Nginx server block.
- `deploy/jingyun/tiny-ipa.production.env.example`: non-secret environment example.
- `deploy/jingyun/REVISION.candidate`: active-release readback convention.
- `docs/16-m14-jingyun-production-backup-restore-plan.md`: production backup/restore plan.

Every artifact must keep `CANDIDATE - DO NOT APPLY` visible until a later
Human-owned host action explicitly replaces it with an approved operational
file.

## Required Pre-State Evidence

Before any future host mutation, a Human-authorized operator must collect
sanitized evidence for the current host, current date, running services,
listener list, available capacity, and the absence or known ownership of every
Tiny IPA namespace path. The Xue Tu Zhi Ban baseline must be recorded through an
owner-approved application health check, not inferred from Tiny IPA health or a
systemd active state alone.

Stop before mutation when any of these are missing or ambiguous:

- approved service user: `<HUMAN_APPROVED_TINY_IPA_SERVICE_USER>`;
- approved service group: `<HUMAN_APPROVED_TINY_IPA_SERVICE_GROUP>`;
- Human-owned environment file: `<HUMAN_OWNED_TINY_IPA_ENV_FILE>`;
- TLS certificate ownership for `ipa.jingyun.bj.cn`;
- secret provisioning channel for `TINY_IPA_SESSION_SECRET`;
- backup owner and retention policy;
- rollback owner and acceptable data-loss boundary;
- Xue Tu Zhi Ban baseline health evidence.

## Staged Release Shape

Use immutable release directories and active-release pointers only after later
authorization:

```text
/opt/tiny-ipa/releases/<release-id>
/opt/tiny-ipa/current -> /opt/tiny-ipa/releases/<release-id>
/opt/tiny-ipa/current/REVISION
/var/www/tiny-ipa/releases/<release-id>
/var/www/tiny-ipa/current -> /var/www/tiny-ipa/releases/<release-id>
/var/lib/tiny-ipa/tiny-ipa.sqlite
/var/lib/tiny-ipa/audio
/var/backups/tiny-ipa
```

The frontend build must use `VITE_API_BASE=/api`. The backend must read
`TINY_IPA_DB_PATH=/var/lib/tiny-ipa/tiny-ipa.sqlite` and
`TINY_IPA_AUDIO_DIR=/var/lib/tiny-ipa/audio`. The deployed origin must be
exactly `https://ipa.jingyun.bj.cn`, with `TINY_IPA_COOKIE_SECURE=true` and
`TINY_IPA_COOKIE_SAMESITE=lax`.

## Release Identity and Version Readback

GitHub is the source of truth for every deployable release. A later
Human-authorized operator must select one explicit immutable identity before any
host mutation:

```text
release_id=<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>
commit=<INTENDED_GITHUB_COMMIT_SHA>
tag=<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>
deployment_kind=first_install|upgrade
```

Do not deploy from uncommitted local files, direct VPS edits, local-only patches,
or an unpushed branch. The intended release must be visible on GitHub before it
is copied or built for the VPS.

Each backend release directory must contain a generated `REVISION` file with
the same release ID, commit, optional tag, and timestamp shape as
`deploy/jingyun/REVISION.candidate`. The backend environment must set:

```dotenv
TINY_IPA_RELEASE_ID=<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>
TINY_IPA_RELEASE_COMMIT=<INTENDED_GITHUB_COMMIT_SHA>
TINY_IPA_RELEASE_TAG=<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>
```

The live backend exposes only these explicit non-secret environment fields at
`/api/version`, with `Cache-Control: no-store`. It does not read or return the
contents of `REVISION` or any operator-selected file path. After any later
authorized activation, the operator must compare the disk and API evidence as
separate sources:

```text
local git rev-parse HEAD
intended GitHub commit/tag
/opt/tiny-ipa/current/REVISION
GET https://ipa.jingyun.bj.cn/api/version
```

Before public activation, after separately authorized backend start, compare
GitHub, disk REVISION, non-secret environment identity and loopback
`http://127.0.0.1:18110/api/version`; verify both current pointers and the
frontend build's source commit match the intended release. Stop on mismatch or
unreachable loopback API. The public HTTPS endpoint is checked only after
separately authorized public activation. Loopback evidence is not public/TLS
evidence; the HTTPS comparison above and full smoke must then pass.

## First Installation and Upgrade Recovery

Choose `first_install` only after authorized observations verify that there is
no Tiny IPA active release, neither backend nor frontend current pointer, no
Tiny IPA service or public route, and no existing Tiny IPA data or partial
installation. Record service, route, both pointer and DB/audio/path ownership
pre-state. Unknown ownership, an old database or partial deployment means HOLD,
not first installation. `previous_release=none` records verified absence; an
empty field, unknown state or fabricated pointer is never equivalent.

For `upgrade`, record `previous_release=<PREVIOUS_ACTIVE_RELEASE_ID_RECORDED_BEFORE_CHANGE>`,
backend pointer `<PREVIOUS_ACTIVE_RELEASE_PATH_RECORDED_BEFORE_CHANGE>`, frontend
pointer, and the matching previous non-secret release environment identity.
Rollback restores frontend, backend and environment identity together. Require
a named recovery owner and verified database compatibility/data-loss boundary;
unknown compatibility means HOLD. Code rollback is not database restore.

First-install withdrawal returns Tiny IPA to the recorded disabled/unpublished
state. Only withdraw this trial's Tiny IPA activation and stop the Tiny IPA
service started by this trial. Preserve new DB, audio, backups, release files
and evidence. Service/proxy/pointer withdrawal commands require explicit later
phase authorization. Failure never authorizes shared Nginx reload, deletion,
in-place restore, or any change to Xue Tu Zhi Ban. Record the recovery owner,
phase-specific withdrawal plan and independently recheck Xue Tu Zhi Ban health.

The following two **synthetic review examples** define the minimum lifecycle
record checked by repository tests. They are not current host observations or
deployment authorization. Actual records must link concrete pre-state evidence,
owners and separately approved command lists before host use.

```json
[
  {
    "kind": "first_install",
    "pre_state": "verified_absent",
    "previous_release": "none",
    "backend_pointer": null,
    "frontend_pointer": null,
    "previous_env_identity": null,
    "recovery_owner": "example-owner",
    "recovery_plan": "withdraw_this_trial_activation",
    "recovery_scope": "tiny_ipa_only",
    "preserve_data": true,
    "delete": false,
    "in_place_restore": false,
    "phase_authorization_required": true,
    "version_stages": ["loopback_after_backend_start", "https_after_public_activation"]
  },
  {
    "kind": "upgrade",
    "pre_state": "verified_existing",
    "previous_release": "example-v1",
    "backend_pointer": "/opt/tiny-ipa/releases/example-v1",
    "frontend_pointer": "/var/www/tiny-ipa/releases/example-v1",
    "previous_env_identity": "example-v1",
    "db_compatibility": "verified",
    "recovery_owner": "example-owner",
    "recovery_plan": "restore_backend_frontend_env_identity",
    "recovery_scope": "tiny_ipa_only",
    "preserve_data": true,
    "delete": false,
    "in_place_restore": false,
    "phase_authorization_required": true,
    "version_stages": ["loopback_after_backend_start", "https_after_public_activation"]
  }
]
```

## Validation Before Activation

Each later phase must validate before moving to the next phase:

1. Record pre-state evidence and Xue Tu Zhi Ban baseline health.
2. Verify the candidate service user is not root and owns only the approved Tiny IPA paths.
3. Verify port `18110` is still free before any backend start.
4. Record the intended GitHub commit/tag and verified first-install or upgrade recovery record.
5. Generate `REVISION` in the candidate release directory before any `current` pointer change.
6. Validate the systemd unit syntax without enabling or starting it.
7. Build the frontend with `VITE_API_BASE=/api` before any web-root pointer change.
8. Validate the Nginx candidate without reload and confirm it owns only `ipa.jingyun.bj.cn`.
9. After authorized backend start, compare loopback version identity and frontend build source;
   re-check Xue Tu Zhi Ban health before requesting any proxy reload or public activation.
10. Run Tiny IPA health, `/api/version`, login, Settings save, Today resume,
    and `/audio/` checks only after the relevant host action is authorized.
11. Compare local/GitHub/REVISION/live `/api/version` release identity before
    considering the phase valid.
12. Re-check Xue Tu Zhi Ban health after each authorized phase.

## Stop Conditions

Stop and route to Architect/Human owner before mutation if any proposed command,
diff, or path would touch `/opt/hermes`, `/var/www/hermes-web`,
`/home/ubuntu/.hermes`, Redis, `xuetuzhiban-api.service`, `jingyun.bj.cn` root
routes, existing Nginx defaults, occupied backend ports 3000, 5173, 8000, 8001,
8002, 8010, or 6379, private application data, real secrets, or real
certificate files.

Stop after validation, before activation, if Tiny IPA health succeeds but Xue
Tu Zhi Ban health is missing or regressed. Tiny IPA success never substitutes
for the higher-priority application baseline.

Stop before pointer changes, proxy activation, or smoke completion if the
deployment kind, verified pre-state, recovery owner or phase recovery plan is
missing. An upgrade additionally requires real previous backend/frontend
pointers and matching environment identity. A first installation instead
requires verified absence and an authorized withdrawal plan preserving data.

## Later Authorization Boundary

A future host-action request must name the exact phase, release ID, files to
transfer, command list, expected output, rollback owner
`<HUMAN_APPROVED_ROLLBACK_OWNER>`, and backup owner
`<HUMAN_APPROVED_BACKUP_OWNER>`. Approval for this candidate plan alone does
not authorize applying any artifact.

## P1a Private Loopback Trial Packet

P1a is narrower than the full first-install lifecycle record above. It creates
only a private backend and synthetic state, so public Tiny IPA route absence is
not inferred or required. The full `first_install` record remains `incomplete`
until P1b verifies Nginx, DNS, TLS, and public-route boundaries. P1a neither
serves the frontend nor weakens `TINY_IPA_COOKIE_SECURE=true` or origin policy.

Before a Human decision, replace `<APPROVED_RELEASE_ID>`,
`<APPROVED_GITHUB_SHA>`, and `<APPROVED_ARTIFACT_SHA256>` with the exact
Reviewer- and Architect-accepted Epic-integrated commit and artifact digest.
The same frozen values must be recorded in #282. Placeholders are not authority
to execute this packet.

### H0: readonly preflight

Use this wrapper for each quoted block:

```text
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ConnectTimeout=10 -o ConnectionAttempts=1 -o ClearAllForwardings=yes -o ForwardAgent=no -o ForwardX11=no -o ControlMaster=no -o ControlPath=none jingyun '<reviewed command block>'
```

Run the blocks independently. Expected identity is `ubuntu` and
`VM-0-7-ubuntu`; architecture is `x86_64`. Each curl failure is fatal.

```sh
date -u +%FT%TZ
whoami
hostname
uname -m
python3 --version
df -Pk / /var/lib /var/backups
free -m
ss -ltn
systemctl show nginx.service xuetuzhiban-api.service tiny-ipa-api.service tiny-ipa-backup.service tiny-ipa-backup.timer --no-pager -p Id -p LoadState -p ActiveState -p SubState -p UnitFileState
getent passwd tiny-ipa
getent group tiny-ipa
for p in /opt/tiny-ipa /opt/tiny-ipa/current /var/www/tiny-ipa /var/www/tiny-ipa/current /etc/tiny-ipa /var/lib/tiny-ipa /var/lib/tiny-ipa/tiny-ipa.sqlite /var/lib/tiny-ipa/audio /var/backups/tiny-ipa; do stat --printf='%n|%F|%U|%G|%a\n' -- "$p"; done
```

```sh
curl --version | sed -n '1p'
for p in /apps/xuetuzhiban/demo/ /apps/xuetuzhiban-test/demo/ /apps/xuetuzhiban/app/ /apps/xuetuzhiban-test/app/ /api/xuetuzhiban /api/xuetuzhiban-test; do
  result=$(curl --noproxy '*' --connect-timeout 3 --max-time 8 --max-redirs 0 -sS -I -o /dev/null -w '%{http_code}|%header{cache-control}|%header{location}' "http://127.0.0.1$p") || exit $?
  printf '%s\n' "$result"
done
```

The route sequence must be `200`, `302` to `/apps/xuetuzhiban/demo/`, then
four `503` responses with `no-store`. The write-out emits only status,
Cache-Control, and Location. Unsupported `%header{}` syntax stops H0; never dump
raw headers. Require at least 1 GiB available RAM, 5 GiB disk, free port 18110,
and absent or exactly explained Tiny IPA account, units, and paths. Unknown
state, another host writer, incompatible Python/wheels, or P0 route drift means
HOLD before writes.

### Locked offline release assembly

From the `backend` directory on an isolated Linux x86_64 build environment
matching the H0 Python minor, derive dependencies from `backend/uv.lock`
without an unlocked solve:

```sh
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock.txt
python3 -m pip download --requirement requirements.lock.txt --dest wheelhouse --only-binary=:all:
python3 -m pip install --no-index --find-links wheelhouse --requirement requirements.lock.txt --target dependency-check
python3 -m compileall -q dependency-check
sha256sum requirements.lock.txt wheelhouse/* > OFFLINE-MANIFEST.sha256
```

The release artifact contains the repository tree at `<APPROVED_GITHUB_SHA>`,
the requirements file, wheelhouse, and manifest. H0 runs
`sha256sum -c OFFLINE-MANIFEST.sha256`, confirms wheel compatibility with the
observed CPython/x86_64 target, and uses `--no-index` for the release venv. A
source distribution, missing wheel, network fallback, apt, global Python
update, Docker, or mutable host checkout stops the trial.

### H1: conditional private backend activation

Only after H0 passes under one Human approval, the sole host writer may create
non-login `tiny-ipa:tiny-ipa`, immutable root-owned release
`/opt/tiny-ipa/releases/<APPROVED_RELEASE_ID>`, root-owned 0640
`/etc/tiny-ipa/tiny-ipa.env`, and new Tiny IPA-only state/backup roots. Generate
the session secret directly into the env file and never print it. Populate the
venv offline, verify the manifest, make the release service-readable and
non-writable, then select it through `current`.

Install only the reviewed `tiny-ipa-api.service`, run `systemd-analyze verify`,
`sudo -n systemctl daemon-reload`, and
`sudo -n systemctl start tiny-ipa-api.service`; do not enable it. Verify
`MemoryMax=512M`, `TasksMax=64`, listener `127.0.0.1:18110`, and matching
GitHub, `REVISION`, env, and loopback `/api/version` identity. Check loopback
health and unauthenticated fail-closed APIs. Do not create accounts, import
data, invoke TTS/models/providers, or read private rows. Repeat the P0 route
checks after activation.

### H2: backup, separate restore, and timer

```sh
sudo -n -u tiny-ipa /opt/tiny-ipa/current/deploy/jingyun/p1a-backup.py backup --source /var/lib/tiny-ipa/tiny-ipa.sqlite --state-root /var/lib/tiny-ipa --destination-root /var/backups/tiny-ipa --snapshot-id <UNIQUE_UTC_SNAPSHOT_ID> --release-id <APPROVED_RELEASE_ID> --max-bytes 104857600 --retention-limit 7
sudo -n -u tiny-ipa /opt/tiny-ipa/current/deploy/jingyun/p1a-backup.py verify-restore --backup-file /var/backups/tiny-ipa/<UNIQUE_UTC_SNAPSHOT_ID>/tiny-ipa.sqlite.backup --backup-root /var/backups/tiny-ipa --restore-root /var/lib/tiny-ipa/restore-candidates --trial-id <UNIQUE_RESTORE_ID> --expected-sha256 <OBSERVED_BACKUP_SHA256>
```

Accept `status=complete` followed by `status=verified` with matching checksum,
schema fingerprint, and table counts. The restore remains separate and never
replaces the active DB. Install and verify the reviewed backup service/timer,
run one `sudo -n systemctl start tiny-ipa-backup.service`, then
`sudo -n systemctl start tiny-ipa-backup.timer`, and inspect its oneshot result
and `systemctl list-timers tiny-ipa-backup.timer`. Do not enable it. The timer
runs at 03:20 UTC with `Persistent=false`; a future occurrence is `pending`
until observed. Seven complete snapshots or 100 MiB causes failure and a
recorded notification; nothing is pruned.

### Withdrawal and evidence

On post-write failure, stop only `tiny-ipa-backup.timer`, a running
`tiny-ipa-backup.service`, and `tiny-ipa-api.service`; verify port 18110 closed
and repeat the P0 route checks. Preserve the account, env, release, pointer,
state, backups, restore candidate, and unit files as evidence. Do not change
shared services, delete files, return to another app configuration, or restore
in place. Record only release ID, times, unit states, size, checksums,
integrity/schema/table-count summary, timer result, and route tuples. Exclude
rows, cookies, raw headers, secrets, tokens, certificate paths, and query data.

P1a proves only private coexistence and the bounded backup operation. P1b owns
public frontend, shared ingress, DNS, HTTPS, supported ACME renewal, and full
phone smoke. Disaster recovery and RPO remain unclaimed until off-host storage,
permanent retention/deletion, and failure notification have separate owners.
