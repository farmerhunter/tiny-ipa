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

For the later full public deployment, stop before mutation when any of these
are missing or ambiguous:

- approved service user: `<HUMAN_APPROVED_TINY_IPA_SERVICE_USER>`;
- approved service group: `<HUMAN_APPROVED_TINY_IPA_SERVICE_GROUP>`;
- Human-owned environment file: `<HUMAN_OWNED_TINY_IPA_ENV_FILE>`;
- TLS certificate ownership for `ipa.jingyun.bj.cn`;
- secret provisioning channel for `TINY_IPA_SESSION_SECRET`;
- backup owner and retention policy;
- rollback owner and acceptable data-loss boundary;
- Xue Tu Zhi Ban baseline health evidence.

P1a uses the fixed service identity, env path, backup bounds, and preserve-data
withdrawal below. It does not wait for or change TLS, but it still requires the
exact Human approval and fresh H0 evidence defined in its packet.

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
and complete absence of the Tiny IPA account, units, and every listed path.
Any leftover is a HOLD even when its owner appears known; it requires a new
recovery decision and is never reused, overwritten, or deleted here. NSS
absence, path `ENOENT`, and permission failure are distinct results. Unknown
state, another host writer, incompatible Python/wheels, or P0 route drift also
means HOLD before writes.

The final H0 blocks enforce those predicates without writing:

```sh
set -eu
test "$(whoami)" = ubuntu
test "$(hostname)" = VM-0-7-ubuntu
test "$(uname -m)" = x86_64
test "$(free -m | awk '/^Mem:/ {print $7}')" -ge 1024
test "$(df -Pk / | awk 'NR==2 {print $4}')" -ge 5242880
test -z "$(ss -ltnH 'sport = :18110')"
if getent passwd tiny-ipa >/dev/null; then exit 20; fi
if getent group tiny-ipa >/dev/null; then exit 21; fi
for unit in tiny-ipa-api.service tiny-ipa-backup.service tiny-ipa-backup.timer; do
  test "$(systemctl show "$unit" --no-pager -p LoadState --value)" = not-found
done
LC_ALL=C
export LC_ALL
for p in /opt/tiny-ipa /opt/tiny-ipa/current /var/www/tiny-ipa /var/www/tiny-ipa/current /etc/tiny-ipa /var/lib/tiny-ipa /var/lib/tiny-ipa/tiny-ipa.sqlite /var/lib/tiny-ipa/audio /var/backups/tiny-ipa; do
  if result=$(stat --printf='%n|%F|%U|%G|%a' -- "$p" 2>&1); then
    printf '%s\n' "$result"
    exit 22
  else
    case "$result" in *'No such file or directory'*) : ;; *) printf '%s\n' "$result" >&2; exit 23 ;; esac
  fi
done
```

```sh
set -eu
python3 -m venv --help >/dev/null
systemd-analyze --version | sed -n '1p'
openssl version
tar --version | sed -n '1p'
sha256sum --version | sed -n '1p'
python3 -c 'import platform, sys, sysconfig; print(sys.version.split()[0]); print(platform.machine()); print(sysconfig.get_config_var("SOABI")); print(sysconfig.get_platform())'
```

The builder must match those Python/platform values. Missing `venv`, an
unexpected SOABI/platform, or a binary wheel is fatal. H1 creates the isolated
venv and lets its own pip perform an offline `--dry-run` before installation.
Validate the P0 tuple rather than merely printing it:

```sh
set -eu
for p in /apps/xuetuzhiban/demo/ /apps/xuetuzhiban-test/demo/ /apps/xuetuzhiban/app/ /apps/xuetuzhiban-test/app/ /api/xuetuzhiban /api/xuetuzhiban-test; do
  result=$(curl --noproxy '*' --connect-timeout 3 --max-time 8 --max-redirs 0 -sS -I -o /dev/null -w '%{http_code}|%header{cache-control}|%header{location}' "http://127.0.0.1$p") || exit $?
  IFS='|' read -r status cache location <<EOF
$result
EOF
  case "$p" in
    /apps/xuetuzhiban/demo/) test "$status" = 200 ;;
    /apps/xuetuzhiban-test/demo/) test "$status" = 302; test "$location" = /apps/xuetuzhiban/demo/ ;;
    *) test "$status" = 503; case "$cache" in *no-store*) : ;; *) exit 24 ;; esac ;;
  esac
  printf '%s\n' "$result"
done
```

### Locked offline release assembly

From the `backend` directory on an isolated Linux x86_64 build environment
matching the H0 Python minor, derive dependencies from `backend/uv.lock`
without an unlocked solve:

The isolated Linux builder packages that exact commit. Transfer happens only
through canonical H1-staging after the Human gate opens:

```sh
set -eu
release_id=<APPROVED_RELEASE_ID>
commit=<APPROVED_GITHUB_SHA>
build_root=$(mktemp -d)
check_root=$(mktemp -d)
git fetch origin "$commit"
test "$(git rev-parse "$commit^{commit}")" = "$commit"
git archive "$commit" | tar -x -C "$build_root"
cd "$build_root/backend"
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock.txt
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST python3 -m pip download --require-hashes --requirement requirements.lock.txt --dest wheelhouse --only-binary=:all:
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 python3 -m pip install --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt --target "$check_root"
python3 -m compileall -q "$check_root"
python3 -I -B -c 'import json, platform, sysconfig; print(json.dumps({"implementation":"cpython","python":platform.python_version(),"machine":platform.machine(),"soabi":sysconfig.get_config_var("SOABI"),"platform":sysconfig.get_platform(),"libc":"-".join(platform.libc_ver())}, sort_keys=True))' > TARGET-RUNTIME.json
BUILDER_CHECK_ROOT="$check_root" python3 -I -B -c 'import os, sys; sys.path.insert(0, os.environ["BUILDER_CHECK_ROOT"]); import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("builder imports passed")'
sha256sum TARGET-RUNTIME.json requirements.lock.txt wheelhouse/* > OFFLINE-MANIFEST.sha256
cd "$build_root"
printf 'release_id=%s\ncommit=%s\ntag=\ncreated_at=%s\n' "$release_id" "$commit" "$(date -u +%FT%TZ)" > REVISION
tar --create --gzip --file "../tiny-ipa-$release_id.tar.gz" .
sha256sum "../tiny-ipa-$release_id.tar.gz"
du -sk "$build_root"
stat -c '%s' "../tiny-ipa-$release_id.tar.gz"
```

The locally observed archive digest is materialized as
`<APPROVED_ARTIFACT_SHA256>` before the remote H1 block continues.

The release artifact contains the repository tree at `<APPROVED_GITHUB_SHA>`,
the requirements file, wheelhouse, and manifest. H1 runs
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

The reviewed H1 command sequence is:

```sh
set -eu
release_id=<APPROVED_RELEASE_ID>
artifact=/tmp/tiny-ipa-p1a/tiny-ipa-<APPROVED_RELEASE_ID>.tar.gz
[[ $release_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
archive_line=$(sha256sum "$artifact")
read -r archive_digest archive_name extra <<<"$archive_line"
test "$archive_digest" = <APPROVED_ARTIFACT_SHA256>
test -z "${extra:-}"
sudo -n useradd --system --user-group --home-dir /var/lib/tiny-ipa --no-create-home --shell /usr/sbin/nologin tiny-ipa
sudo -n install -d -o root -g root -m 0755 /opt/tiny-ipa/releases
sudo -n install -d -o root -g root -m 0755 "/opt/tiny-ipa/releases/$release_id"
sudo -n install -d -o root -g tiny-ipa -m 0750 /etc/tiny-ipa
sudo -n install -d -o tiny-ipa -g tiny-ipa -m 0750 /var/lib/tiny-ipa /var/lib/tiny-ipa/audio
sudo -n install -d -o tiny-ipa -g tiny-ipa -m 0700 /var/lib/tiny-ipa/restore-candidates /var/backups/tiny-ipa
sudo -n tar --extract --gzip --file "$artifact" --directory "/opt/tiny-ipa/releases/$release_id" --no-same-owner
cd "/opt/tiny-ipa/releases/$release_id/backend"
sha256sum -c OFFLINE-MANIFEST.sha256
sudo -n python3 -m venv .venv
sudo -n env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 TMPDIR=/tmp/tiny-ipa-p1a/tmp timeout 45s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -m pip install --dry-run --ignore-installed --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt
sudo -n env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 TMPDIR=/tmp/tiny-ipa-p1a/tmp timeout 45s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -m pip install --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt
sudo -n timeout 20s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B -c 'import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("activation imports passed")'
sudo -n sh -c 'umask 0027; secret=$(openssl rand -hex 32) || exit 30; { printf "%s\n" "TINY_IPA_ENV=production" "TINY_IPA_DB_PATH=/var/lib/tiny-ipa/tiny-ipa.sqlite" "TINY_IPA_SESSION_SECRET=$secret" "TINY_IPA_ALLOWED_ORIGINS=https://ipa.jingyun.bj.cn" "TINY_IPA_COOKIE_SECURE=true" "TINY_IPA_COOKIE_SAMESITE=lax" "TINY_IPA_AUDIO_DIR=/var/lib/tiny-ipa/audio" "TINY_IPA_RELEASE_ID=<APPROVED_RELEASE_ID>" "TINY_IPA_RELEASE_COMMIT=<APPROVED_GITHUB_SHA>" "TINY_IPA_RELEASE_TAG="; } > /etc/tiny-ipa/tiny-ipa.env; chown root:tiny-ipa /etc/tiny-ipa/tiny-ipa.env; chmod 0640 /etc/tiny-ipa/tiny-ipa.env'
sudo -n chmod -R a-w "/opt/tiny-ipa/releases/$release_id"
sudo -n ln -s "/opt/tiny-ipa/releases/$release_id" /opt/tiny-ipa/current
sudo -n install -o root -g root -m 0644 /opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-api.service.candidate /etc/systemd/system/tiny-ipa-api.service
sudo -n systemd-analyze verify /etc/systemd/system/tiny-ipa-api.service
sudo -n systemctl daemon-reload
timeout 45s sudo -n systemctl start tiny-ipa-api.service
```

The installed paths are the single release directory, `current` symlink,
`/etc/tiny-ipa/tiny-ipa.env`, the new DB/audio/restore roots, backup root, and
`/etc/systemd/system/tiny-ipa-api.service`. No command uses overwrite or force
against a namespace that H0 requires to be absent.

Install only the reviewed `tiny-ipa-api.service`, run `systemd-analyze verify`,
`sudo -n systemctl daemon-reload`, and
`sudo -n systemctl start tiny-ipa-api.service`; do not enable it. Verify
`MemoryMax=512M`, `TasksMax=64`, listener `127.0.0.1:18110`, and matching
GitHub, `REVISION`, env, and loopback `/api/version` identity. Check loopback
health and unauthenticated fail-closed APIs. Do not create accounts, import
data, invoke TTS/models/providers, or read private rows. Repeat the P0 route
checks after activation.

The canonical runtime acceptance block below supersedes the earlier draft
readback checks.

### H2: backup, separate restore, and timer

```sh
sudo -n -u tiny-ipa /opt/tiny-ipa/current/deploy/jingyun/p1a-backup.py backup --source /var/lib/tiny-ipa/tiny-ipa.sqlite --state-root /var/lib/tiny-ipa --destination-root /var/backups/tiny-ipa --snapshot-id <UNIQUE_UTC_SNAPSHOT_ID> --release-id <APPROVED_RELEASE_ID> --max-bytes 104857600 --retention-limit 7
sudo -n -u tiny-ipa /opt/tiny-ipa/current/deploy/jingyun/p1a-backup.py verify-restore --backup-file /var/backups/tiny-ipa/<UNIQUE_UTC_SNAPSHOT_ID>/tiny-ipa.sqlite.backup --backup-root /var/backups/tiny-ipa --restore-root /var/lib/tiny-ipa/restore-candidates --trial-id <UNIQUE_RESTORE_ID> --expected-sha256 <OBSERVED_BACKUP_SHA256>
```

After that restore verifies, materialize and start the bounded timer without
enabling it:

```sh
set -eu
release_id=<APPROVED_RELEASE_ID>
[[ $release_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
unit_stage=/tmp/tiny-ipa-p1a/tiny-ipa-backup.service
test ! -e "$unit_stage" && test ! -L "$unit_stage"
(umask 077; set -o noclobber; sed "s|<APPROVED_RELEASE_ID>|$release_id|g" /opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-backup.service.candidate > "$unit_stage")
sudo -n install -o root -g root -m 0644 "$unit_stage" /etc/systemd/system/tiny-ipa-backup.service
sudo -n install -o root -g root -m 0644 /opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-backup.timer.candidate /etc/systemd/system/tiny-ipa-backup.timer
sudo -n systemd-analyze verify /etc/systemd/system/tiny-ipa-backup.service /etc/systemd/system/tiny-ipa-backup.timer
sudo -n systemctl daemon-reload
sudo -n systemctl start tiny-ipa-backup.service
test "$(systemctl show tiny-ipa-backup.service -p Result --value)" = success
sudo -n systemctl start tiny-ipa-backup.timer
test "$(systemctl show tiny-ipa-backup.timer -p ActiveState --value)" = active
test "$(systemctl show tiny-ipa-backup.timer -p UnitFileState --value)" = disabled
systemctl list-timers tiny-ipa-backup.timer --no-pager
```

H2 adds only `/etc/systemd/system/tiny-ipa-backup.service`,
`/etc/systemd/system/tiny-ipa-backup.timer`, complete/incomplete snapshot
directories, and the separate restore-candidate directory. `/tmp` staging is
retained for evidence until a later cleanup authorization.

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

The canonical preserve-data withdrawal block below supersedes the earlier
draft stop/readback commands. No `rm`, `unlink`, `disable`, shared-service
action, pointer rewrite, or restore command belongs to withdrawal.

## Architect Re-baselined Canonical Gates

The earlier command blocks are component inventory retained for review context;
they are not independent pass gates. The blocks in this section are the sole
executable P1a gates and supersede conflicting earlier wording. The earlier H1
file-creation sequence is permitted only after canonical staging and the
pre-activation H0 recheck, and its result must pass canonical acceptance.
H0 is readonly. H1-staging is the first authorized write phase. H1-activation
cannot begin until staging succeeds.

### Canonical H0 and pre-activation recheck

Run this exact block with Bash. For the pre-activation recheck set
`P1A_ALLOW_STAGING=1`; initial H0 uses `0`. The five approved profile literals
come from the frozen Linux builder receipt.

```bash
# P1A_H0_GATE_BEGIN
set -u
hold() { printf 'HOLD %s\n' "$2" >&2; exit "$1"; }
capture() {
  local target=$1 label=$2 output rc
  shift 2
  output=$("$@" 2>&1); rc=$?
  test "$rc" -eq 0 || hold 40 "$label rc=$rc"
  printf -v "$target" '%s' "$output"
}

readonly P1A_EXPECTED_PYTHON=<APPROVED_PYTHON_VERSION>
readonly P1A_EXPECTED_IMPLEMENTATION=cpython
readonly P1A_EXPECTED_MACHINE=x86_64
readonly P1A_EXPECTED_SOABI=<APPROVED_SOABI>
readonly P1A_EXPECTED_PLATFORM=<APPROVED_SYSCONFIG_PLATFORM>
readonly P1A_EXPECTED_LIBC=<APPROVED_LIBC_PROFILE>
readonly P1A_ALLOW_STAGING=${P1A_ALLOW_STAGING:-0}
export P1A_EXPECTED_PYTHON P1A_EXPECTED_IMPLEMENTATION P1A_EXPECTED_MACHINE P1A_EXPECTED_SOABI
export P1A_EXPECTED_PLATFORM P1A_EXPECTED_LIBC P1A_ALLOW_STAGING

capture identity identity whoami
test "$identity" = ubuntu || hold 41 identity
capture host host hostname
test "$host" = VM-0-7-ubuntu || hold 42 host
capture machine machine uname -m
test "$machine" = x86_64 || hold 43 machine

capture memory memory free -m
available=''
while read -r kind total used free_mb shared buff_cache available_mb rest; do
  if test "$kind" = 'Mem:'; then available=$available_mb; fi
done <<<"$memory"
[[ $available =~ ^[0-9]+$ ]] || hold 44 memory-format
test "$available" -ge 1024 || hold 45 memory-capacity

for filesystem in / /var/lib /var/backups; do
  capture disk "disk-$filesystem" df -Pk "$filesystem"
  disk_line=''
  while IFS= read -r line; do disk_line=$line; done <<<"$disk"
  read -r fs blocks used available_kb capacity mounted extra <<<"$disk_line"
  [[ $available_kb =~ ^[0-9]+$ ]] || hold 46 "disk-format-$filesystem"
  test "$available_kb" -ge 5242880 || hold 47 "disk-capacity-$filesystem"
done

if port_rows=$(ss -ltnH 'sport = :18110' 2>&1); then
  test -z "$port_rows" || hold 48 port-occupied
else
  query_rc=$?
  hold 49 "ss rc=$query_rc"
fi

for database in passwd group; do
  account_row=$(getent "$database" tiny-ipa 2>&1); query_rc=$?
  if test "$query_rc" -eq 0; then hold 50 "$database-occupied"; fi
  test "$query_rc" -eq 2 || hold 51 "$database rc=$query_rc"
  test -z "$account_row" || hold 52 "$database-contradictory-output"
done

for unit in tiny-ipa-api.service tiny-ipa-backup.service tiny-ipa-backup.timer; do
  capture load_state "systemctl-$unit" systemctl show "$unit" --no-pager -p LoadState --value
  test "$load_state" = not-found || hold 53 "$unit-leftover"
done

capture systemd_version systemd-version systemd-analyze --version
capture openssl_version openssl-version openssl version
capture tar_version tar-version tar --version
capture sha_version sha256sum-version sha256sum --version
capture timeout_version timeout-version timeout --version

timeout 10s python3 -I -B <<'PY'
# P1A_H0_PYTHON_BEGIN
import ctypes
import errno
import os
import platform
import ssl
import sqlite3
import stat
import sys
import sysconfig
import ensurepip
import venv

def fail(code, label):
    print(f"HOLD {label}", file=sys.stderr)
    raise SystemExit(code)

profile = {
    "implementation": sys.implementation.name,
    "python": platform.python_version(),
    "machine": platform.machine(),
    "soabi": sysconfig.get_config_var("SOABI"),
    "platform": sysconfig.get_platform(),
    "libc": "-".join(platform.libc_ver()),
}
expected = {
    "implementation": os.environ["P1A_EXPECTED_IMPLEMENTATION"],
    "python": os.environ["P1A_EXPECTED_PYTHON"],
    "machine": os.environ["P1A_EXPECTED_MACHINE"],
    "soabi": os.environ["P1A_EXPECTED_SOABI"],
    "platform": os.environ["P1A_EXPECTED_PLATFORM"],
    "libc": os.environ["P1A_EXPECTED_LIBC"],
}
if profile != expected:
    fail(60, "runtime-profile")

paths = (
    "/opt/tiny-ipa", "/opt/tiny-ipa/current", "/var/www/tiny-ipa",
    "/var/www/tiny-ipa/current", "/etc/tiny-ipa", "/var/lib/tiny-ipa",
    "/var/lib/tiny-ipa/tiny-ipa.sqlite", "/var/lib/tiny-ipa/audio",
    "/var/backups/tiny-ipa", "/tmp/tiny-ipa-p1a",
)
allow_staging = os.environ["P1A_ALLOW_STAGING"] == "1"

# P1A_LSTAT_DECISION_BEGIN
def require_path_absent(path, allow_staging, lstat=os.lstat):
    try:
        stat_result = lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        fail(61, f"lstat-{path}-errno-{exc.errno}")
    if path == "/tmp/tiny-ipa-p1a" and allow_staging:
        if not platform.system() == "Linux":
            fail(62, "staging-platform")
        if (
            not stat.S_ISDIR(stat_result.st_mode)
            or stat_result.st_uid != os.getuid()
            or stat_result.st_mode & 0o777 != 0o700
        ):
            fail(63, "staging-owner-mode")
        return
    fail(64, f"leftover-{path}")
# P1A_LSTAT_DECISION_END

for path in paths:
    require_path_absent(path, allow_staging)

class Passwd(ctypes.Structure):
    _fields_ = [
        ("pw_name", ctypes.c_char_p), ("pw_passwd", ctypes.c_char_p),
        ("pw_uid", ctypes.c_uint), ("pw_gid", ctypes.c_uint),
        ("pw_gecos", ctypes.c_char_p), ("pw_dir", ctypes.c_char_p),
        ("pw_shell", ctypes.c_char_p),
    ]

class Group(ctypes.Structure):
    _fields_ = [
        ("gr_name", ctypes.c_char_p), ("gr_passwd", ctypes.c_char_p),
        ("gr_gid", ctypes.c_uint), ("gr_mem", ctypes.POINTER(ctypes.c_char_p)),
    ]

libc = ctypes.CDLL(None, use_errno=True)
checks = ((libc.getpwnam_r, Passwd), (libc.getgrnam_r, Group))

# P1A_NSS_DECISION_BEGIN
def require_absent(rc, observed_errno, present):
    if rc == errno.ERANGE:
        fail(65, "nss-erange")
    if rc != 0 or observed_errno != 0 or present:
        fail(66, "nss-lookup")
# P1A_NSS_DECISION_END

for function, record_type in checks:
    function.argtypes = [ctypes.c_char_p, ctypes.POINTER(record_type), ctypes.c_char_p,
                         ctypes.c_size_t, ctypes.POINTER(ctypes.POINTER(record_type))]
    function.restype = ctypes.c_int
    record = record_type()
    result = ctypes.POINTER(record_type)()
    buffer = ctypes.create_string_buffer(16384)
    ctypes.set_errno(0)
    rc = function(b"tiny-ipa", ctypes.byref(record), buffer, len(buffer), ctypes.byref(result))
    observed_errno = ctypes.get_errno()
    require_absent(rc, observed_errno, bool(result))

print("H0 runtime-profile, namespace, and libc lookups passed")
print(f"ensurepip={ensurepip.version()} ssl={ssl.OPENSSL_VERSION.split()[0]} sqlite={sqlite3.sqlite_version}")
# P1A_H0_PYTHON_END
PY
python_rc=$?
test "$python_rc" -eq 0 || hold 67 "python-gate rc=$python_rc"

capture curl_version curl-version curl --version
for path in /apps/xuetuzhiban/demo/ /apps/xuetuzhiban-test/demo/ /apps/xuetuzhiban/app/ /apps/xuetuzhiban-test/app/ /api/xuetuzhiban /api/xuetuzhiban-test; do
  result=$(curl --noproxy '*' --connect-timeout 3 --max-time 8 --max-redirs 0 -sS -I -o /dev/null -w '%{http_code}|%header{cache-control}|%header{location}' "http://127.0.0.1$path" 2>&1)
  curl_rc=$?
  test "$curl_rc" -eq 0 || hold 68 "curl-$path rc=$curl_rc"
  IFS='|' read -r status cache location extra <<<"$result"
  test -z "${extra:-}" || hold 69 "curl-$path-format"
  case "$path" in
    /apps/xuetuzhiban/demo/) test "$status" = 200 || hold 70 p0-prod-demo ;;
    /apps/xuetuzhiban-test/demo/)
      test "$status" = 302 || hold 71 p0-test-demo-status
      test "$location" = /apps/xuetuzhiban/demo/ || hold 72 p0-test-demo-location ;;
    *)
      test "$status" = 503 || hold 73 "p0-$path-status"
      case "$cache" in *no-store*) : ;; *) hold 74 "p0-$path-cache" ;; esac ;;
  esac
  printf '%s\n' "$result"
done
# P1A_H0_GATE_END
```

`getent` rc 2 plus empty output is only one candidate missing result. The
typed libc checks also require `getpwnam_r` and `getgrnam_r` rc 0, errno 0, and
NULL result with a bounded 16 KiB buffer. `ERANGE`, lookup errors, a present
record, `lstat` errors, and dangling symlinks all HOLD. This narrows evidence to
the exact lookup and does not certify an external directory service.

### Canonical H1-staging

The approved packet freezes archive size, unpacked size, runtime profile,
requirements hashes, wheel inventory, and the archive SHA-256. Initial H0 must
show `/tmp/tiny-ipa-p1a` absent. The first write is collision-refusing
`mkdir -m 0700 /tmp/tiny-ipa-p1a`, followed by the reviewed `scp`. No sudo or
final namespace is allowed in staging. The Coordinator runs these two
controller-side commands first:

```bash
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ConnectTimeout=10 -o ConnectionAttempts=1 -o ClearAllForwardings=yes -o ForwardAgent=no -o ForwardX11=no -o ControlMaster=no -o ControlPath=none jingyun 'mkdir -m 0700 /tmp/tiny-ipa-p1a'
scp -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o ConnectTimeout=10 -o ConnectionAttempts=1 -o ClearAllForwardings=yes -o ForwardAgent=no -o ForwardX11=no -o ControlMaster=no -o ControlPath=none "tiny-ipa-<APPROVED_RELEASE_ID>.tar.gz" jingyun:/tmp/tiny-ipa-p1a/
```

Any nonzero result stops staging. Then the SSH wrapper runs the following
remote block:

```bash
# P1A_H1_STAGING_BEGIN
set -u
stage=/tmp/tiny-ipa-p1a
archive="$stage/tiny-ipa-<APPROVED_RELEASE_ID>.tar.gz"
stage_meta=$(stat -c '%U|%a' "$stage" 2>&1); stage_rc=$?
test "$stage_rc" -eq 0 || exit 81
test "$stage_meta" = "ubuntu|700" || exit 81
test -f "$archive" || exit 80
archive_line=$(sha256sum "$archive" 2>&1); archive_rc=$?
test "$archive_rc" -eq 0 || exit 82
read -r archive_digest archive_name extra <<<"$archive_line"
test "$archive_digest" = <APPROVED_ARTIFACT_SHA256> || exit 82
test -z "${extra:-}" || exit 82
disk=$(df -Pk "$stage" 2>&1); disk_rc=$?
test "$disk_rc" -eq 0 || exit 83
disk_line=''
while IFS= read -r line; do disk_line=$line; done <<<"$disk"
read -r fs blocks used available_kb capacity mounted extra <<<"$disk_line"
[[ $available_kb =~ ^[0-9]+$ ]] || exit 83
test "$available_kb" -ge <APPROVED_STAGING_REQUIRED_KB> || exit 84
mkdir -m 0700 "$stage/extracted" "$stage/tmp" || exit 85
timeout 30s python3 -I -B - "$archive" "$stage/extracted" <APPROVED_UNPACKED_MAX_BYTES> <<'PY' || exit 86
# P1A_STAGE_ARCHIVE_PYTHON_BEGIN
import pathlib
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
maximum = int(sys.argv[3])
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    if len(members) > 10000:
        raise SystemExit("too many archive members")
    total = 0
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit("unsafe archive path")
        if not (member.isdir() or member.isreg()):
            raise SystemExit("links and special files are forbidden")
        total += member.size
        if total > maximum:
            raise SystemExit("archive exceeds unpacked bound")
    bundle.extractall(destination, members=members, filter="data")

requirements = destination / "backend/requirements.lock.txt"
wheelhouse = destination / "backend/wheelhouse"
text = requirements.read_text(encoding="utf-8")
for line in text.splitlines():
    stripped = line.strip().lower()
    if (
        stripped.startswith(("-e ", "--index", "--extra-index", "--find-links", "file:"))
        or "git+" in stripped
        or "://" in stripped
        or " @ " in stripped
    ):
        raise SystemExit("URL, VCS, and editable requirements are forbidden")
files = list(wheelhouse.iterdir())
if not files or any(not item.is_file() or item.suffix != ".whl" for item in files):
    raise SystemExit("wheelhouse must contain wheels only")
# P1A_STAGE_ARCHIVE_PYTHON_END
PY
timeout 45s python3 -I -B -m venv "$stage/venv" || exit 87
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 TMPDIR="$stage/tmp" \
  timeout 45s "$stage/venv/bin/python" -m pip install --dry-run --ignore-installed \
  --require-hashes --only-binary=:all: --no-index --no-cache-dir \
  --find-links "$stage/extracted/backend/wheelhouse" \
  --requirement "$stage/extracted/backend/requirements.lock.txt" || exit 88
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 TMPDIR="$stage/tmp" \
  timeout 45s "$stage/venv/bin/python" -m pip install \
  --require-hashes --only-binary=:all: --no-index --no-cache-dir \
  --find-links "$stage/extracted/backend/wheelhouse" \
  --requirement "$stage/extracted/backend/requirements.lock.txt" || exit 89
timeout 20s "$stage/venv/bin/python" -I -B -c \
  'import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("staging imports passed")' || exit 90
# P1A_H1_STAGING_END
```

The inline stdlib body rejects absolute/parent-traversing archive members,
links, devices, FIFOs, sockets, URL/VCS/editable requirements and non-wheel
payloads before bounded extraction into the new staging root. Any staging
failure retains only this root and stops before account,
final roots, units, database, pointer, or service operations.

H1-activation starts by rerunning the canonical H0 block with the one staging
exception. It then creates a fresh final venv and repeats the same manifest,
`--require-hashes`, `--only-binary=:all:`, `--no-index`, `--no-cache-dir`,
offline dry-run, install, and representative imports. It never moves or copies
the staging venv. The activation commands earlier in this document apply only
after this recheck and must use the staged, validated artifact.

### Canonical H1 runtime acceptance

The runtime probe is `python3 -I -B` using `http.client` directly, with a
3-second request timeout, 64 KiB body cap, no proxy/cookie/auth/redirect, and
sanitized output. It asserts health 200/ok; version 200/ok with exact approved
release and full commit, empty tag and `no-store`; auth/me 200 with exactly an
anonymous result; and progress 401 with `AUTH_REQUIRED`. It never prints a
failed body or raw header.

Before and after exactly one
`timeout 45s sudo -n systemctl restart tiny-ipa-api.service`, the acceptance
block must also compare a successfully read nonempty `InvocationID`,
`ActiveState=active`, `MemoryMax=536870912`, and `TasksMax=64`; parse every
successful `ss -ltnH 'sport = :18110'` row and require at least one row with all
local endpoints exactly `127.0.0.1:18110`; parse `REVISION` as data and compare
its release/commit to the approved literals; run only the health readiness loop
for at most 30 seconds; and execute the HTTP assertions. The post-restart
InvocationID must differ. Any producer error, wildcard listener, unchanged ID,
wrong identity/status/error, malformed or oversized JSON, or timeout fails into
withdrawal. Finally rerun the canonical P0 tuple checks.

```bash
# P1A_H1_ACCEPTANCE_BEGIN
set -u
hold() { printf 'HOLD %s\n' "$2" >&2; exit "$1"; }
capture() {
  local target=$1 label=$2 output rc
  shift 2
  output=$("$@" 2>&1); rc=$?
  test "$rc" -eq 0 || hold 100 "$label rc=$rc"
  printf -v "$target" '%s' "$output"
}
readonly approved_release=<APPROVED_RELEASE_ID>
readonly approved_commit=<APPROVED_GITHUB_SHA>

runtime_probe() {
  timeout 30s python3 -I -B - "$approved_release" "$approved_commit" <<'PY'
# P1A_RUNTIME_PROBE_BEGIN
import http.client
import json
import pathlib
import sys
import time

release, commit = sys.argv[1:]
limit = 65536

def request(path):
    connection = http.client.HTTPConnection("127.0.0.1", 18110, timeout=3)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        body = response.read(limit + 1)
        if len(body) > limit:
            raise RuntimeError(f"{path} oversized")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{path} malformed JSON") from exc
        return response.status, response.getheader("Cache-Control", ""), payload
    finally:
        connection.close()

deadline = time.monotonic() + 27
while True:
    try:
        health = request("/api/health")
        if health[0] == 200 and health[2].get("status") == "ok":
            break
    except (OSError, RuntimeError, http.client.HTTPException):
        pass
    if time.monotonic() >= deadline:
        raise SystemExit("health readiness deadline")
    time.sleep(0.5)

version = request("/api/version")
anonymous = request("/api/auth/me")
protected = request("/api/progress")
if not (
    version[0] == 200
    and version[2] == {
        "status": "ok", "release_id": release, "commit": commit, "tag": None,
    }
    and "no-store" in version[1].lower()
):
    raise SystemExit("version identity mismatch")
if anonymous[0] != 200 or anonymous[2] != {"authenticated": False, "user": None}:
    raise SystemExit("anonymous auth contract mismatch")
if protected[0] != 401 or protected[2].get("detail", {}).get("error") != "AUTH_REQUIRED":
    raise SystemExit("protected API did not fail closed")

revision = {}
for line in pathlib.Path("/opt/tiny-ipa/current/REVISION").read_text().splitlines():
    if not line or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key in revision:
        raise SystemExit("duplicate REVISION key")
    revision[key] = value
if revision.get("release_id") != release or revision.get("commit") != commit:
    raise SystemExit("disk identity mismatch")
print(json.dumps({"checks": "passed", "release_id": release, "commit": commit}))
# P1A_RUNTIME_PROBE_END
PY
}

runtime_accept() {
  local phase=$1 active pointer memory tasks listeners listener_rc row_count local_endpoint
  capture pointer "$phase-pointer" readlink /opt/tiny-ipa/current
  test "$pointer" = "/opt/tiny-ipa/releases/$approved_release" || hold 99 "$phase-pointer"
  capture active "$phase-active" systemctl show tiny-ipa-api.service -p ActiveState --value
  test "$active" = active || hold 101 "$phase-active"
  capture memory "$phase-memory" systemctl show tiny-ipa-api.service -p MemoryMax --value
  test "$memory" = 536870912 || hold 102 "$phase-memory"
  capture tasks "$phase-tasks" systemctl show tiny-ipa-api.service -p TasksMax --value
  test "$tasks" = 64 || hold 103 "$phase-tasks"
  capture P1A_INVOCATION "$phase-invocation" systemctl show tiny-ipa-api.service -p InvocationID --value
  test -n "$P1A_INVOCATION" || hold 104 "$phase-empty-invocation"
  listeners=$(ss -ltnH 'sport = :18110' 2>&1); listener_rc=$?
  test "$listener_rc" -eq 0 || hold 105 "$phase-ss-rc=$listener_rc"
  test -n "$listeners" || hold 106 "$phase-no-listener"
  row_count=0
  while read -r state recvq sendq local_endpoint peer extra; do
    test "$local_endpoint" = 127.0.0.1:18110 || hold 107 "$phase-wildcard-listener"
    row_count=$((row_count + 1))
  done <<<"$listeners"
  test "$row_count" -gt 0 || hold 108 "$phase-no-parsed-listener"
  runtime_probe; probe_rc=$?
  test "$probe_rc" -eq 0 || hold 109 "$phase-probe-rc=$probe_rc"
}

runtime_accept before-restart
before_invocation=$P1A_INVOCATION
timeout 45s sudo -n systemctl restart tiny-ipa-api.service
restart_rc=$?
test "$restart_rc" -eq 0 || hold 110 "restart-rc=$restart_rc"
runtime_accept after-restart
test "$P1A_INVOCATION" != "$before_invocation" || hold 111 unchanged-invocation

for path in /apps/xuetuzhiban/demo/ /apps/xuetuzhiban-test/demo/ /apps/xuetuzhiban/app/ /apps/xuetuzhiban-test/app/ /api/xuetuzhiban /api/xuetuzhiban-test; do
  result=$(curl --noproxy '*' --connect-timeout 3 --max-time 8 --max-redirs 0 -sS -I -o /dev/null -w '%{http_code}|%header{cache-control}|%header{location}' "http://127.0.0.1$path" 2>&1)
  curl_rc=$?
  test "$curl_rc" -eq 0 || hold 112 "p0-$path-rc=$curl_rc"
  IFS='|' read -r status cache location extra <<<"$result"
  test -z "${extra:-}" || hold 113 "p0-$path-format"
  case "$path" in
    /apps/xuetuzhiban/demo/) test "$status" = 200 || hold 114 p0-prod-demo ;;
    /apps/xuetuzhiban-test/demo/)
      test "$status" = 302 || hold 115 p0-test-demo-status
      test "$location" = /apps/xuetuzhiban/demo/ || hold 116 p0-test-demo-location ;;
    *)
      test "$status" = 503 || hold 117 "p0-$path-status"
      case "$cache" in *no-store*) : ;; *) hold 118 "p0-$path-cache" ;; esac ;;
  esac
done
# P1A_H1_ACCEPTANCE_END
```

Canonical withdrawal uses the same checked `ss` predicate as H0. Every unit
query and attempted stop records its own status. An unknown query or stop
failure means incomplete withdrawal; it can never be reported as success.
Staging failure performs no service stop because it never reaches activation.

```bash
# P1A_WITHDRAWAL_BEGIN
set -u
withdraw_hold() { printf 'WITHDRAWAL_INCOMPLETE %s\n' "$2" >&2; exit "$1"; }
for unit in tiny-ipa-backup.timer tiny-ipa-backup.service tiny-ipa-api.service; do
  load_state=$(systemctl show "$unit" --no-pager -p LoadState --value 2>&1)
  query_rc=$?
  test "$query_rc" -eq 0 || withdraw_hold 120 "$unit-query-rc=$query_rc"
  if test "$load_state" = not-found; then
    printf '%s|not-found|not-stopped\n' "$unit"
    continue
  fi
  timeout 45s sudo -n systemctl stop "$unit"
  stop_rc=$?
  test "$stop_rc" -eq 0 || withdraw_hold 121 "$unit-stop-rc=$stop_rc"
  active_state=$(systemctl show "$unit" --no-pager -p ActiveState --value 2>&1)
  query_rc=$?
  test "$query_rc" -eq 0 || withdraw_hold 122 "$unit-active-query-rc=$query_rc"
  case "$active_state" in inactive|failed) : ;; *) withdraw_hold 123 "$unit-active=$active_state" ;; esac
  printf '%s|%s|stopped\n' "$unit" "$active_state"
done
port_rows=$(ss -ltnH 'sport = :18110' 2>&1)
query_rc=$?
test "$query_rc" -eq 0 || withdraw_hold 124 "ss-rc=$query_rc"
test -z "$port_rows" || withdraw_hold 125 port-still-open
printf 'withdrawal-port-closed\n'
# P1A_WITHDRAWAL_END
```

After successful withdrawal, rerun the canonical P0 tuple validation. Preserve
the staging root, accounts, final paths, env, state, release, pointers, units,
backups, and restore candidates; no cleanup or retry is implied.
