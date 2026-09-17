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
`TINY_IPA_COOKIE_SAMESITE=lax`. The controlled P1b trial also fixes
`TINY_IPA_REQUIRE_PACKAGED_AUDIO=true` so normal practice only selects audio
that the manifest binds and the host deploys. Set
`TINY_IPA_KEEP_WAL_ANCHOR=true` for the bounded backup trial so the API keeps
one idle SQLite connection open for the process lifetime. The connection
completes a read during startup and must not retain a transaction; SQLite then
keeps its WAL coordination files available without backup-triggered HTTP
traffic or broader backup-service write access.

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

The canonical marked P0 probe later in this document is the sole executable
route-check source. It invokes `/usr/bin/curl -q`, captures curl
`%{header_json}` only in memory, and passes it to the marked parser without
printing raw headers or stderr. The route sequence must be production demo 200,
test demo 302 with one strictly allowed Location and `no-store`, then four 503
responses with `no-store`. Unsupported write-out syntax stops H0. Never dump raw
headers. Require at least 1 GiB available RAM, 5 GiB disk, free port 18110,
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
The final packet copies the canonical marked P0 probe byte-for-byte into H0,
the post-staging recheck, H1 acceptance, H2 completion, and both withdrawal
paths. Each copy validates the tuple rather than merely printing it.

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
bootstrap_pip_version=26.2.1
git fetch origin "$commit"
test "$(git rev-parse "$commit^{commit}")" = "$commit"
git archive "$commit" | tar -x -C "$build_root"
cd "$build_root/backend"
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock.txt
mkdir -p bootstrap/wheelhouse
curl --proto '=https' --tlsv1.2 --fail --location --output bootstrap/get-pip.py https://bootstrap.pypa.io/get-pip.py
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST python3 -m pip download --no-deps --only-binary=:all: "pip==$bootstrap_pip_version" --dest bootstrap/wheelhouse
bootstrap_wheel=$(printf '%s\n' bootstrap/wheelhouse/pip-*.whl)
test -f "$bootstrap_wheel"
bootstrap_wheel_sha=$(sha256sum "$bootstrap_wheel" | cut -d ' ' -f 1)
printf 'pip==%s --hash=sha256:%s\n' "$bootstrap_pip_version" "$bootstrap_wheel_sha" > bootstrap/requirements.lock.txt
printf 'source=https://bootstrap.pypa.io/get-pip.py\npip_version=%s\nretrieved_at=%s\n' "$bootstrap_pip_version" "$(date -u +%FT%TZ)" > bootstrap/PROVENANCE
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST python3 -m pip download --require-hashes --requirement requirements.lock.txt --dest wheelhouse --only-binary=:all:
env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS -u PIP_TRUSTED_HOST PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONNOUSERSITE=1 python3 -m pip install --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt --target "$check_root"
python3 -m compileall -q "$check_root"
python3 -I -B -c 'import json, platform, sysconfig; print(json.dumps({"implementation":"cpython","python":platform.python_version(),"machine":platform.machine(),"soabi":sysconfig.get_config_var("SOABI"),"platform":sysconfig.get_platform(),"libc":"-".join(platform.libc_ver())}, sort_keys=True))' > TARGET-RUNTIME.json
BUILDER_CHECK_ROOT="$check_root" python3 -I -B -c 'import os, sys; sys.path.insert(0, os.environ["BUILDER_CHECK_ROOT"]); import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("builder imports passed")'
sha256sum TARGET-RUNTIME.json requirements.lock.txt wheelhouse/* bootstrap/PROVENANCE bootstrap/get-pip.py bootstrap/requirements.lock.txt bootstrap/wheelhouse/* > OFFLINE-MANIFEST.sha256
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
the application requirements and wheelhouse, the frozen official
`get-pip.py`, one fixed pip wheel, its hash-locked bootstrap requirement and
provenance, and the combined manifest. H1 runs
`sha256sum -c OFFLINE-MANIFEST.sha256`, confirms wheel compatibility with the
observed CPython/x86_64 target, creates each venv with `--without-pip`, validates
the bootstrap lock against the sole local pip wheel, and uses `--no-index` for
both bootstrap and application installation. `get-pip.py` appends its own
`pip` requirement, so the bootstrap command does not claim pip CLI
`--require-hashes`; the already verified manifest plus the bootstrap lock and
single-wheel allowlist enforce the byte identity instead. A
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
sudo -n python3 -m venv --without-pip .venv
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR=/tmp/tiny-ipa-p1a/tmp /usr/bin/timeout 10s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B - bootstrap/requirements.lock.txt bootstrap/wheelhouse <<'PY'
# P1A_BOOTSTRAP_LOCK_PYTHON_BEGIN
import hashlib
import pathlib
import re
import sys

lock = pathlib.Path(sys.argv[1])
wheelhouse = pathlib.Path(sys.argv[2])
match = re.fullmatch(r"pip==([0-9]+(?:\.[0-9]+)*) --hash=sha256:([0-9a-f]{64})\n", lock.read_text())
if match is None:
    raise SystemExit("invalid bootstrap lock")
wheels = list(wheelhouse.iterdir())
if len(wheels) != 1 or not wheels[0].is_file() or wheels[0].name != f"pip-{match[1]}-py3-none-any.whl":
    raise SystemExit("invalid bootstrap wheel inventory")
if hashlib.sha256(wheels[0].read_bytes()).hexdigest() != match[2]:
    raise SystemExit("bootstrap wheel hash mismatch")
# P1A_BOOTSTRAP_LOCK_PYTHON_END
PY
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR=/tmp/tiny-ipa-p1a/tmp /usr/bin/timeout 45s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B bootstrap/get-pip.py --no-setuptools --no-wheel --no-index --no-cache-dir --only-binary=:all: --find-links bootstrap/wheelhouse pip==26.2.1
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 /usr/bin/timeout 10s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B - "/opt/tiny-ipa/releases/$release_id/backend/.venv" <<'PY'
import pathlib
import pip
import sys

root = pathlib.Path(sys.argv[1]).resolve()
installed = pathlib.Path(pip.__file__).resolve()
if pip.__version__ != "26.2.1" or root not in installed.parents:
    raise SystemExit("unexpected pip version or location")
print(f"pip={pip.__version__} location=release-venv")
PY
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR=/tmp/tiny-ipa-p1a/tmp /usr/bin/timeout 45s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B -m pip install --dry-run --ignore-installed --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR=/tmp/tiny-ipa-p1a/tmp /usr/bin/timeout 45s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B -m pip install --require-hashes --only-binary=:all: --no-index --no-cache-dir --find-links wheelhouse --requirement requirements.lock.txt
sudo -n /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR=/tmp/tiny-ipa-p1a/tmp /usr/bin/timeout 20s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B -c 'import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("activation imports passed")'
sudo -n -u tiny-ipa /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 /usr/bin/timeout 20s "/opt/tiny-ipa/releases/$release_id/backend/.venv/bin/python" -I -B - "/opt/tiny-ipa/releases/$release_id/backend" /var/lib/tiny-ipa /var/lib/tiny-ipa/tiny-ipa.sqlite <<'PY'
# P1A_INIT_DB_PYTHON_BEGIN
import json
import os
import pathlib
import sqlite3
import stat
import sys
import urllib.parse

backend = pathlib.Path(sys.argv[1])
state_root = pathlib.Path(sys.argv[2])
database = pathlib.Path(sys.argv[3])
expected_tables = {
    "attempts", "auth_sessions", "daily_sessions", "phoneme_stats", "phonemes",
    "session_items", "settings", "users", "words",
}

def require_real_directory(path):
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        entry = os.lstat(current)
        if stat.S_ISLNK(entry.st_mode):
            raise RuntimeError("symlink path component")
    if not stat.S_ISDIR(os.lstat(path).st_mode):
        raise RuntimeError("required directory is not a directory")

def require_absent(path):
    try:
        os.lstat(path)
    except FileNotFoundError:
        return
    raise RuntimeError("database namespace collision")

try:
    if not backend.is_absolute() or not state_root.is_absolute() or not database.is_absolute():
        raise RuntimeError("absolute paths required")
    require_real_directory(backend)
    require_real_directory(state_root)
    if database.parent != state_root:
        raise RuntimeError("database must be directly below state root")
    if not (backend / "app/services/db_schema.py").is_file():
        raise RuntimeError("frozen schema module missing")
    for candidate in (database, pathlib.Path(str(database) + "-wal"), pathlib.Path(str(database) + "-shm"), pathlib.Path(str(database) + "-journal")):
        require_absent(candidate)
    os.umask(0o077)
    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(database, flags, 0o600)
    os.close(descriptor)
    sys.path.insert(0, str(backend))
    from app.services.db_schema import init_db
    uri = "file:" + urllib.parse.quote(str(database), safe="/") + "?mode=rw"
    connection = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        init_db(connection)
        connection.commit()
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        sessions = connection.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
    finally:
        connection.close()
    metadata = os.lstat(database)
    if tables != expected_tables or integrity != "ok" or users != 0 or sessions != 0:
        raise RuntimeError("initialized database invariant failed")
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("initialized database is not a regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid() or metadata.st_gid != os.getgid():
        raise RuntimeError("initialized database ownership or mode failed")
except Exception:
    raise SystemExit("database initialization failed") from None
print(json.dumps({"auth_sessions": sessions, "integrity": integrity, "mode": "600", "status": "initialized", "tables": len(tables), "users": users}, sort_keys=True))
# P1A_INIT_DB_PYTHON_END
PY
sudo -n sh -c 'umask 0027; secret=$(openssl rand -hex 32) || exit 30; { printf "%s\n" "TINY_IPA_ENV=production" "TINY_IPA_DB_PATH=/var/lib/tiny-ipa/tiny-ipa.sqlite" "TINY_IPA_SESSION_SECRET=$secret" "TINY_IPA_ALLOWED_ORIGINS=https://ipa.jingyun.bj.cn" "TINY_IPA_COOKIE_SECURE=true" "TINY_IPA_COOKIE_SAMESITE=lax" "TINY_IPA_AUDIO_DIR=/var/lib/tiny-ipa/audio" "TINY_IPA_REQUIRE_PACKAGED_AUDIO=true" "TINY_IPA_RELEASE_ID=<APPROVED_RELEASE_ID>" "TINY_IPA_RELEASE_COMMIT=<APPROVED_GITHUB_SHA>" "TINY_IPA_RELEASE_TAG="; } > /etc/tiny-ipa/tiny-ipa.env; chown root:tiny-ipa /etc/tiny-ipa/tiny-ipa.env; chmod 0640 /etc/tiny-ipa/tiny-ipa.env'
sudo -n chmod -R a-w "/opt/tiny-ipa/releases/$release_id"
sudo -n ln -s "/opt/tiny-ipa/releases/$release_id" /opt/tiny-ipa/current
sudo -n install -o root -g root -m 0644 /opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-api.service.candidate /etc/systemd/system/tiny-ipa-api.service
sudo -n systemd-analyze verify /etc/systemd/system/tiny-ipa-api.service
sudo -n systemctl daemon-reload
timeout 45s sudo -n systemctl start tiny-ipa-api.service
```

The database initialization command runs as `tiny-ipa` with the frozen release
interpreter and current `app.services.db_schema.init_db`. It exclusively creates
one private database, refuses an existing database or sidecar namespace and any
symlinked parent, and verifies exactly the nine current application tables with
zero users and zero auth sessions. It does not invoke app startup, account
bootstrap, content generation, migration of an existing database, or a provider.
Failure preserves the partial new file for diagnosis and stops before env,
pointer, unit, service, or H2 operations; retry or deletion requires a later
decision.

The installed paths are the single release directory, `current` symlink,
`/etc/tiny-ipa/tiny-ipa.env`, the new empty-schema DB/audio/restore roots, backup root, and
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

The single H2 block installs and verifies the versioned operations tool before
using it for direct backup and separate restore verification. Only after that
restore verifies does it materialize and start the bounded unit and timer. The
backup oneshot owns a 30-second start limit and a 10-second stop limit; the
outer 60-second `systemctl start` bound leaves time to capture its terminal
result. Every R2 operation emits one fixed step identifier and numeric return
code. A failed step emits the same filtered seven-field unit summary used by
runtime acceptance before the packet enters withdrawal; it never prints raw
unit output or a journal:

```sh
set -u
release_id=<APPROVED_RELEASE_ID>
tool_revision=<APPROVED_TOOL_REVISION>
tool_sha256=<APPROVED_TOOL_SHA256>
unit_template_sha256=<APPROVED_UNIT_TEMPLATE_SHA256>
snapshot_id=<UNIQUE_UTC_SNAPSHOT_ID>
restore_id=<UNIQUE_RESTORE_ID>
[[ $release_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || exit 148
[[ $tool_revision =~ ^[0-9a-f]{40}$ ]] || exit 148
[[ $tool_sha256 =~ ^[0-9a-f]{64}$ ]] || exit 148
[[ $unit_template_sha256 =~ ^[0-9a-f]{64}$ ]] || exit 148
[[ $snapshot_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || exit 148
[[ $restore_id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || exit 148
r2_summary() {
  local raw rc
  raw=$(/usr/bin/timeout 5s systemctl show tiny-ipa-backup.service --no-pager \
    --property=ActiveState --property=SubState --property=Result \
    --property=ExecMainCode --property=ExecMainStatus --property=NRestarts \
    --property=InvocationID 2>/dev/null); rc=$?
  if test "$rc" -ne 0; then
    printf '%s\n' '{"r2_unit_summary":"unavailable"}' >&2
    return
  fi
  /usr/bin/timeout 5s /usr/bin/python3 -I -B -c '
# P1A_R2_SUMMARY_PYTHON_BEGIN
import json, re, sys
keys = {"ActiveState", "SubState", "Result", "ExecMainCode", "ExecMainStatus", "NRestarts", "InvocationID"}
values = {}
valid = True
for line in sys.stdin.read().splitlines():
    if "=" not in line:
        valid = False
        continue
    key, value = line.split("=", 1)
    if key not in keys or key in values:
        valid = False
        continue
    values[key] = value
valid = valid and set(values) == keys
valid = valid and values.get("ActiveState") in {"active", "inactive", "activating", "deactivating", "failed"}
valid = valid and all(re.fullmatch(r"[a-z][a-z0-9-]{0,63}", values.get(key, "")) for key in ("SubState", "Result"))
valid = valid and all(re.fullmatch(r"-?[0-9]+", values.get(key, "")) for key in ("ExecMainCode", "ExecMainStatus", "NRestarts"))
valid = valid and re.fullmatch(r"(?:|[0-9a-f]{32})", values.get("InvocationID", "")) is not None
print(json.dumps({"r2_unit_summary": values if valid else "invalid"}, sort_keys=True, separators=(",", ":")))
# P1A_R2_SUMMARY_PYTHON_END
' <<<"$raw" >&2
}
r2_finish() {
  local step=$1 rc=$2
  [[ $step =~ ^[a-z0-9-]+$ ]] && [[ $rc =~ ^[0-9]+$ ]] || exit 149
  printf '{"r2_step":"%s","rc":%s}\n' "$step" "$rc"
  if test "$rc" -ne 0; then
    r2_summary
    exit "$rc"
  fi
}
r2_run() {
  local step=$1 rc
  shift
  "$@"; rc=$?
  r2_finish "$step" "$rc"
}
tool_source=/tmp/tiny-ipa-p1a/p1a-backup-$tool_revision.py
unit_template_source=/tmp/tiny-ipa-p1a/tiny-ipa-backup-$tool_revision.service.candidate
tool_dir=/opt/tiny-ipa/ops/$tool_revision
tool_path=$tool_dir/p1a-backup.py
unit_template_path=$tool_dir/tiny-ipa-backup.service.candidate
unit_stage=/tmp/tiny-ipa-p1a/tiny-ipa-backup.service
test -f "$tool_source" && test ! -L "$tool_source"; rc=$?
r2_finish tool-source-type "$rc"
test -f "$unit_template_source" && test ! -L "$unit_template_source"; rc=$?
r2_finish unit-template-source-type "$rc"
observed=$(/usr/bin/sha256sum "$tool_source"); rc=$?
if test "$rc" -eq 0; then read -r digest name extra <<<"$observed"; test "$digest" = "$tool_sha256" && test "$name" = "$tool_source" && test -z "${extra:-}"; rc=$?; fi
r2_finish tool-source-sha "$rc"
observed=$(/usr/bin/sha256sum "$unit_template_source"); rc=$?
if test "$rc" -eq 0; then read -r digest name extra <<<"$observed"; test "$digest" = "$unit_template_sha256" && test "$name" = "$unit_template_source" && test -z "${extra:-}"; rc=$?; fi
r2_finish unit-template-source-sha "$rc"
ops_root=/opt/tiny-ipa/ops
sudo -n test ! -L "$ops_root"; rc=$?
r2_finish ops-root-not-symlink "$rc"
sudo -n test -e "$ops_root"; rc=$?
if test "$rc" -ne 0; then sudo -n install -d -o root -g root -m 0755 "$ops_root"; rc=$?; fi
r2_finish ops-root-present "$rc"
sudo -n /usr/bin/python3 -I -B - "$ops_root" <<'PY'
import os
import stat
import sys

value = os.lstat(sys.argv[1])
if not stat.S_ISDIR(value.st_mode) or stat.S_IMODE(value.st_mode) != 0o755:
    raise SystemExit("ops-root-type-mode")
if (value.st_uid, value.st_gid) != (0, 0):
    raise SystemExit("ops-root-owner")
PY
rc=$?
r2_finish ops-root-metadata "$rc"
sudo -n test ! -e "$tool_dir"; rc=$?
if test "$rc" -eq 0; then sudo -n test ! -L "$tool_dir"; rc=$?; fi
r2_finish tool-dir-absent "$rc"
r2_run install-tool-dir sudo -n install -d -o root -g root -m 0755 "$tool_dir"
r2_run install-tool sudo -n install -o root -g root -m 0555 "$tool_source" "$tool_path"
r2_run install-unit-template sudo -n install -o root -g root -m 0444 "$unit_template_source" "$unit_template_path"
r2_run seal-tool-dir sudo -n chmod 0555 "$tool_dir"
r2_run verify-tool-sha /usr/bin/sha256sum --status -c <(printf '%s  %s\n' "$tool_sha256" "$tool_path")
r2_run verify-unit-template-sha /usr/bin/sha256sum --status -c <(printf '%s  %s\n' "$unit_template_sha256" "$unit_template_path")
sudo -n /usr/bin/python3 -I -B - "$tool_dir" "$tool_path" "$unit_template_path" <<'PY'
import os
import stat
import sys

expected = ((stat.S_IFDIR, 0o555), (stat.S_IFREG, 0o555), (stat.S_IFREG, 0o444))
paths = sys.argv[1:]
if len(paths) != len(expected):
    raise SystemExit("tool-path-count")
for path, (kind, mode) in zip(paths, expected):
    value = os.lstat(path)
    if stat.S_IFMT(value.st_mode) != kind or stat.S_IMODE(value.st_mode) != mode:
        raise SystemExit("tool-path-type-mode")
    if (value.st_uid, value.st_gid) != (0, 0):
        raise SystemExit("tool-path-owner")
PY
rc=$?
r2_finish tool-install-metadata "$rc"
# P1A_TOOL_MATERIALIZATION_END
backup_output=$(sudo -n -u tiny-ipa "$tool_path" backup --source /var/lib/tiny-ipa/tiny-ipa.sqlite --state-root /var/lib/tiny-ipa --destination-root /var/backups/tiny-ipa --snapshot-id "$snapshot_id" --release-id "$release_id" --max-bytes 104857600 --retention-limit 7); rc=$?
r2_finish direct-backup "$rc"
backup_sha=$(printf '%s' "$backup_output" | /usr/bin/python3 -I -B -c 'import json, re, sys; value=json.load(sys.stdin); digest=value.get("sha256", "") if isinstance(value, dict) and value.get("status") == "complete" else ""; sys.exit(1) if not re.fullmatch(r"[0-9a-f]{64}", digest) else print(digest)'); rc=$?
unset backup_output
r2_finish direct-backup-report "$rc"
r2_run direct-restore sudo -n -u tiny-ipa "$tool_path" verify-restore --backup-file "/var/backups/tiny-ipa/$snapshot_id/tiny-ipa.sqlite.backup" --backup-root /var/backups/tiny-ipa --restore-root /var/lib/tiny-ipa/restore-candidates --trial-id "$restore_id" --expected-sha256 "$backup_sha"
test ! -e "$unit_stage" && test ! -L "$unit_stage"
set +e
(umask 077; set -o noclobber; /usr/bin/timeout 5s sed -e "s|<APPROVED_RELEASE_ID>|$release_id|g" -e "s|<APPROVED_TOOL_REVISION>|$tool_revision|g" "$unit_template_path" > "$unit_stage")
rc=$?
r2_finish unit-stage "$rc"
# P1A_UNIT_MATERIALIZATION_END
r2_run install-service /usr/bin/timeout 20s sudo -n install -o root -g root -m 0644 "$unit_stage" /etc/systemd/system/tiny-ipa-backup.service
r2_run install-timer /usr/bin/timeout 20s sudo -n install -o root -g root -m 0644 /opt/tiny-ipa/current/deploy/jingyun/tiny-ipa-backup.timer.candidate /etc/systemd/system/tiny-ipa-backup.timer
r2_run verify-units /usr/bin/timeout 20s sudo -n systemd-analyze verify /etc/systemd/system/tiny-ipa-backup.service /etc/systemd/system/tiny-ipa-backup.timer
r2_run daemon-reload /usr/bin/timeout 20s sudo -n systemctl daemon-reload
r2_run start-backup /usr/bin/timeout 60s sudo -n systemctl start tiny-ipa-backup.service
result=$(/usr/bin/timeout 5s systemctl show tiny-ipa-backup.service -p Result --value); rc=$?
if test "$rc" -eq 0; then test "$result" = success; rc=$?; fi
r2_finish backup-result "$rc"
r2_run start-timer /usr/bin/timeout 20s sudo -n systemctl start tiny-ipa-backup.timer
active=$(/usr/bin/timeout 5s systemctl show tiny-ipa-backup.timer -p ActiveState --value); rc=$?
if test "$rc" -eq 0; then test "$active" = active; rc=$?; fi
r2_finish timer-active "$rc"
unit_file=$(/usr/bin/timeout 5s systemctl show tiny-ipa-backup.timer -p UnitFileState --value); rc=$?
if test "$rc" -eq 0; then test "$unit_file" = disabled; rc=$?; fi
r2_finish timer-disabled "$rc"
r2_run list-timer /usr/bin/timeout 5s systemctl list-timers tiny-ipa-backup.timer --no-pager
```

H2 adds only `/etc/systemd/system/tiny-ipa-backup.service`,
`/etc/systemd/system/tiny-ipa-backup.timer`, complete/incomplete snapshot
directories, and the separate restore-candidate directory. `/tmp` staging is
retained for evidence until a later cleanup authorization.

The Human-reviewed recovery packet must stage and hash the exact
`p1a-backup.py` and `tiny-ipa-backup.service.candidate` bytes from the same
final tool revision before H2. The packet refuses an existing version
directory, installs it and the script as `root:root` mode `0555`, installs the
unit template as `root:root` mode `0444`, and verifies both installed hashes
before materializing or starting a unit. There is no `ops/current` pointer.
This leaves the immutable application release, its manifest, and
`/opt/tiny-ipa/current` unchanged.

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

venv.EnvBuilder(with_pip=False)
print("H0 runtime-profile, namespace, venv, and libc lookups passed")
print(f"venv=without-pip ssl={ssl.OPENSSL_VERSION.split()[0]} sqlite={sqlite3.sqlite_version}")
# P1A_H0_PYTHON_END
PY
python_rc=$?
test "$python_rc" -eq 0 || hold 67 "python-gate rc=$python_rc"

readonly P1A_CURL=/usr/bin/curl
readonly P1A_P0_HOLD_CODE=68
capture curl_version curl-version "$P1A_CURL" -q --version
export P1A_CURL
# P1A_P0_PROBE_BEGIN
readonly P1A_P0_PARSER='
# P1A_P0_PARSER_BEGIN
import json
import sys

SPECS = {
    "/apps/xuetuzhiban/demo/": ("prod-demo", 200),
    "/apps/xuetuzhiban-test/demo/": ("test-demo", 302),
    "/apps/xuetuzhiban/app/": ("prod-app", 503),
    "/apps/xuetuzhiban-test/app/": ("test-app", 503),
    "/api/xuetuzhiban": ("prod-api", 503),
    "/api/xuetuzhiban-test": ("test-api", 503),
}
ALLOWED_LOCATIONS = frozenset((
    "/apps/xuetuzhiban/demo/",
    "http://127.0.0.1/apps/xuetuzhiban/demo/",
    "http://127.0.0.1:80/apps/xuetuzhiban/demo/",
))


def fail(reason):
    print(reason)
    raise SystemExit(1)


def directives(value):
    parts = []
    current = []
    quoted = False
    escaped = False
    for character in value:
        if escaped:
            current.append(character)
            escaped = False
        elif quoted and character == "\\":
            current.append(character)
            escaped = True
        elif character == "\"":
            current.append(character)
            quoted = not quoted
        elif character == "," and not quoted:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if quoted or escaped:
        fail("cache-format")
    parts.append("".join(current).strip())
    return parts


def has_no_store(values):
    for value in values:
        for directive in directives(value):
            name = directive.split("=", 1)[0].strip().lower()
            if name == "no-store":
                return True
    return False


def header_values(headers, name):
    values = headers.get(name, [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        fail("header-format")
    return values


path = sys.argv[1] if len(sys.argv) == 2 else ""
if path not in SPECS:
    fail("path")
path_id, expected_status = SPECS[path]
try:
    payload = json.load(sys.stdin)
except (UnicodeDecodeError, json.JSONDecodeError):
    fail("curl-json")
if not isinstance(payload, dict) or set(payload) != {"status", "headers"}:
    fail("curl-shape")
status = payload["status"]
headers = payload["headers"]
if not isinstance(status, int) or isinstance(status, bool) or not isinstance(headers, dict):
    fail("curl-types")
if any(not isinstance(name, str) or name != name.lower() for name in headers):
    fail("header-name")
locations = header_values(headers, "location")
cache_values = header_values(headers, "cache-control")
no_store = has_no_store(cache_values)
if status != expected_status:
    fail(path_id + "-status")
result = {
    "cache_no_store": no_store,
    "location_count": len(locations),
    "path_id": path_id,
    "status": status,
}
if path_id == "test-demo":
    if len(locations) != 1:
        fail("test-demo-location-count")
    location = locations[0]
    if any(ord(character) < 32 or ord(character) == 127 for character in location):
        fail("test-demo-location-control")
    if location not in ALLOWED_LOCATIONS:
        fail("test-demo-location")
    if not no_store:
        fail("test-demo-cache")
    result["location"] = location
elif path_id != "prod-demo" and not no_store:
    fail(path_id + "-cache")
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
# P1A_P0_PARSER_END
'

p0_probe() {
  local path=$1 raw curl_rc filtered filter_rc
  raw=$("$P1A_CURL" -q --noproxy '*' --proto '=http' --http1.1 --connect-timeout 3 --max-time 8 --max-redirs 0 --silent --show-error --head --output /dev/null --header 'Host: 127.0.0.1' --header 'User-Agent: tiny-ipa-p1a-p0/1' --header 'Accept: */*' --header 'Accept-Encoding: identity' --header 'Connection: close' --write-out '{"status":%{http_code},"headers":%{header_json}}' "http://127.0.0.1$path" 2>/dev/null)
  curl_rc=$?
  if test "$curl_rc" -ne 0; then
    unset raw
    hold "$P1A_P0_HOLD_CODE" "p0-$path-curl-rc=$curl_rc"
  fi
  filtered=$(printf '%s' "$raw" | /usr/bin/python3 -I -B -c "$P1A_P0_PARSER" "$path" 2>/dev/null)
  filter_rc=$?
  unset raw
  test "$filter_rc" -eq 0 || hold "$P1A_P0_HOLD_CODE" "p0-$path-${filtered:-filter}"
  printf '%s\n' "$filtered"
}

for path in /apps/xuetuzhiban/demo/ /apps/xuetuzhiban-test/demo/ /apps/xuetuzhiban/app/ /apps/xuetuzhiban-test/app/ /api/xuetuzhiban /api/xuetuzhiban-test; do
  p0_probe "$path"
done
# P1A_P0_PROBE_END
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
bootstrap = destination / "backend/bootstrap"
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
bootstrap_files = {item.name for item in bootstrap.iterdir()}
if bootstrap_files != {"PROVENANCE", "get-pip.py", "requirements.lock.txt", "wheelhouse"}:
    raise SystemExit("invalid bootstrap inventory")
bootstrap_wheels = list((bootstrap / "wheelhouse").iterdir())
if len(bootstrap_wheels) != 1 or not bootstrap_wheels[0].is_file() or bootstrap_wheels[0].suffix != ".whl":
    raise SystemExit("bootstrap wheelhouse must contain one wheel")
# P1A_STAGE_ARCHIVE_PYTHON_END
PY
timeout 45s python3 -I -B -m venv --without-pip "$stage/venv" || exit 87
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR="$stage/tmp" \
  /usr/bin/timeout 10s "$stage/venv/bin/python" -I -B - \
  "$stage/extracted/backend/bootstrap/requirements.lock.txt" \
  "$stage/extracted/backend/bootstrap/wheelhouse" <<'PY' || exit 88
import hashlib
import pathlib
import re
import sys

lock = pathlib.Path(sys.argv[1])
wheelhouse = pathlib.Path(sys.argv[2])
match = re.fullmatch(r"pip==([0-9]+(?:\.[0-9]+)*) --hash=sha256:([0-9a-f]{64})\n", lock.read_text())
if match is None:
    raise SystemExit("invalid bootstrap lock")
wheels = list(wheelhouse.iterdir())
if len(wheels) != 1 or not wheels[0].is_file() or wheels[0].name != f"pip-{match[1]}-py3-none-any.whl":
    raise SystemExit("invalid bootstrap wheel inventory")
if hashlib.sha256(wheels[0].read_bytes()).hexdigest() != match[2]:
    raise SystemExit("bootstrap wheel hash mismatch")
PY
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR="$stage/tmp" \
  /usr/bin/timeout 45s "$stage/venv/bin/python" -I -B \
  "$stage/extracted/backend/bootstrap/get-pip.py" --no-setuptools --no-wheel \
  --no-index --no-cache-dir --only-binary=:all: \
  --find-links "$stage/extracted/backend/bootstrap/wheelhouse" pip==26.2.1 || exit 89
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/timeout 10s "$stage/venv/bin/python" -I -B - "$stage/venv" <<'PY' || exit 90
import pathlib
import pip
import sys

root = pathlib.Path(sys.argv[1]).resolve()
installed = pathlib.Path(pip.__file__).resolve()
if pip.__version__ != "26.2.1" or root not in installed.parents:
    raise SystemExit("unexpected pip version or location")
print(f"pip={pip.__version__} location=staging-venv")
PY
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR="$stage/tmp" \
  /usr/bin/timeout 45s "$stage/venv/bin/python" -I -B -m pip install --dry-run --ignore-installed \
  --require-hashes --only-binary=:all: --no-index --no-cache-dir \
  --find-links "$stage/extracted/backend/wheelhouse" \
  --requirement "$stage/extracted/backend/requirements.lock.txt" || exit 91
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 TMPDIR="$stage/tmp" \
  /usr/bin/timeout 45s "$stage/venv/bin/python" -I -B -m pip install \
  --require-hashes --only-binary=:all: --no-index --no-cache-dir \
  --find-links "$stage/extracted/backend/wheelhouse" \
  --requirement "$stage/extracted/backend/requirements.lock.txt" || exit 92
/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR="$stage/tmp" \
  /usr/bin/timeout 20s "$stage/venv/bin/python" -I -B -c \
  'import argon2, fastapi, pydantic_core, sqlite3, ssl, uvicorn; print("staging imports passed")' || exit 93
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
the staging venv. Before service start it also exclusively initializes the new
private database with the frozen current schema and verifies nine tables, zero
users, zero auth sessions, integrity, ownership, and mode. The activation
commands earlier in this document apply only after this recheck and must use the
staged, validated artifact.

### Canonical H1 runtime acceptance

The runtime acceptance is `python3 -I -B` with one monotonic 45-second deadline
per before/after-restart phase. Every `systemctl`, `readlink`, and `ss` query is
bounded to the smaller of three seconds or the remaining phase budget. An empty
listener result may retry every 0.5 seconds while the same active unit and
InvocationID remain stable. A nonempty result must contain only exact
`127.0.0.1:18110` listeners before HTTP begins. HTTP uses `http.client`
directly, the smaller of a three-second timeout or remaining budget, a 64 KiB
body cap, no proxy/cookie/auth/redirect, and sanitized output. It asserts health
200/ok; version 200/ok with exact approved release and full commit, empty tag and
`no-store`; auth/me 200 with exactly an anonymous result; and progress 401 with
`AUTH_REQUIRED`. It never prints a failed body or raw header.

Before and after exactly one
`timeout 45s sudo -n systemctl restart tiny-ipa-api.service`, the acceptance
block must compare `ActiveState=active`, `MemoryMax=536870912`, `TasksMax=64`,
and a checked 32-hex `InvocationID` on every listener attempt; parse `REVISION`
as data and compare its release/commit to the approved literals; and execute the
HTTP assertions within the same deadline. InvocationID cannot change during a
phase, and the post-restart value must differ. Any producer error, inactive
unit, wildcard/mixed/malformed listener, wrong identity/status/error, malformed
or oversized JSON, or timeout fails into withdrawal. Before withdrawal, one
five-second failure-only query prints a filtered JSON record containing only
`ActiveState`, `SubState`, `Result`, `ExecMainCode`, `ExecMainStatus`,
`NRestarts`, and `InvocationID`; malformed or failed summary production emits
only a fixed sentinel. No environment, command line, journal, or arbitrary unit
field is read. Finally rerun the canonical P0 tuple checks.

```bash
# P1A_H1_ACCEPTANCE_BEGIN
set -u
P1A_SUMMARY_EMITTED=0
failure_summary() {
  local raw summary_rc
  summary_rc=0
  raw=$(/usr/bin/timeout 5s /usr/bin/systemctl show tiny-ipa-api.service --no-pager \
    --property=ActiveState --property=SubState --property=Result \
    --property=ExecMainCode --property=ExecMainStatus --property=NRestarts \
    --property=InvocationID 2>/dev/null) || summary_rc=$?
  if test "$summary_rc" -ne 0; then
    printf '%s\n' '{"failure_summary":"unavailable"}' >&2
    return
  fi
  /usr/bin/python3 -I -B /dev/fd/3 3<<'PY' <<<"$raw" >&2
# P1A_FAILURE_SUMMARY_PYTHON_BEGIN
import json
import re
import sys

expected = {
    "ActiveState", "SubState", "Result", "ExecMainCode", "ExecMainStatus",
    "NRestarts", "InvocationID",
}
values = {}
valid = True
for line in sys.stdin.read().splitlines():
    if "=" not in line:
        valid = False
        continue
    key, value = line.split("=", 1)
    if key not in expected or key in values:
        valid = False
        continue
    values[key] = value
if set(values) != expected:
    valid = False
if values.get("ActiveState") not in {
    "active", "inactive", "activating", "deactivating", "failed", "reloading",
    "maintenance", "refreshing",
}:
    valid = False
for key in ("SubState", "Result"):
    if re.fullmatch(r"[a-z][a-z0-9-]{0,63}", values.get(key, "")) is None:
        valid = False
for key in ("ExecMainCode", "ExecMainStatus", "NRestarts"):
    if re.fullmatch(r"-?[0-9]+", values.get(key, "")) is None:
        valid = False
if re.fullmatch(r"(?:|[0-9a-f]{32})", values.get("InvocationID", "")) is None:
    valid = False
if valid:
    print(json.dumps({"failure_summary": values}, sort_keys=True, separators=(",", ":")))
else:
    print('{"failure_summary":"invalid"}')
# P1A_FAILURE_SUMMARY_PYTHON_END
PY
}
hold() {
  local code=$1 label=$2
  if test "$P1A_SUMMARY_EMITTED" -eq 0; then
    P1A_SUMMARY_EMITTED=1
    failure_summary
  fi
  printf 'HOLD %s\n' "$label" >&2
  exit "$code"
}
capture() {
  local target=$1 label=$2 output rc
  shift 2
  output=$(/usr/bin/timeout 5s "$@" 2>&1); rc=$?
  test "$rc" -eq 0 || hold 100 "$label rc=$rc"
  printf -v "$target" '%s' "$output"
}
readonly approved_release=<APPROVED_RELEASE_ID>
readonly approved_commit=<APPROVED_GITHUB_SHA>

# P1A_RUNTIME_ACCEPT_SHELL_BEGIN
runtime_accept() {
  local phase=$1 prior_invocation=$2 output probe_rc
  output=$(/usr/bin/timeout 45s /usr/bin/python3 -I -B - \
    "$phase" "$approved_release" "$approved_commit" "$prior_invocation" <<'PY'
# P1A_RUNTIME_PROBE_BEGIN
import http.client
import json
import pathlib
import re
import subprocess
import sys
import time

BODY_LIMIT = 65536
COMMAND_LIMIT = 3.0
PHASE_LIMIT = 45.0
POLL_INTERVAL = 0.5
UNIT_KEYS = {"ActiveState", "MemoryMax", "TasksMax", "InvocationID"}


class ReadinessError(RuntimeError):
    pass


def remaining(deadline, monotonic):
    value = deadline - monotonic()
    if value <= 0:
        raise ReadinessError("readiness-timeout")
    return value


def command(label, argv, deadline, run, monotonic):
    timeout = min(COMMAND_LIMIT, remaining(deadline, monotonic))
    try:
        result = run(
            argv, check=False, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ReadinessError("readiness-timeout") from exc
    if result.returncode != 0:
        raise ReadinessError(label + "-query")
    if len(result.stdout) > BODY_LIMIT:
        raise ReadinessError(label + "-output")
    return result.stdout.strip()


def parse_unit(raw):
    values = {}
    for line in raw.splitlines():
        if "=" not in line:
            raise ReadinessError("unit-shape")
        key, value = line.split("=", 1)
        if key not in UNIT_KEYS or key in values:
            raise ReadinessError("unit-shape")
        values[key] = value
    if set(values) != UNIT_KEYS:
        raise ReadinessError("unit-shape")
    if values["ActiveState"] != "active":
        raise ReadinessError("unit-inactive")
    if values["MemoryMax"] != "536870912" or values["TasksMax"] != "64":
        raise ReadinessError("unit-resources")
    if re.fullmatch(r"[0-9a-f]{32}", values["InvocationID"]) is None:
        raise ReadinessError("unit-invocation")
    return values["InvocationID"]


def request(path, deadline, connection_factory, monotonic):
    timeout = min(3.0, remaining(deadline, monotonic))
    connection = connection_factory("127.0.0.1", 18110, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        body = response.read(BODY_LIMIT + 1)
        if len(body) > BODY_LIMIT:
            raise ReadinessError("http-oversized")
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReadinessError("http-malformed") from exc
        if not isinstance(payload, dict):
            raise ReadinessError("http-shape")
        return response.status, response.getheader("Cache-Control", ""), payload
    finally:
        connection.close()


def readiness(
    phase,
    release,
    commit,
    prior_invocation,
    *,
    run=subprocess.run,
    monotonic=time.monotonic,
    sleep=time.sleep,
    connection_factory=http.client.HTTPConnection,
    revision_path=pathlib.Path("/opt/tiny-ipa/current/REVISION"),
):
    deadline = monotonic() + PHASE_LIMIT
    pointer = command(
        "pointer", ["/usr/bin/readlink", "/opt/tiny-ipa/current"], deadline,
        run, monotonic,
    )
    if pointer != f"/opt/tiny-ipa/releases/{release}":
        raise ReadinessError("pointer")
    revision = {}
    try:
        lines = revision_path.read_text().splitlines()
    except (OSError, UnicodeError) as exc:
        raise ReadinessError("revision-read") from exc
    for line in lines:
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in revision:
            raise ReadinessError("revision-shape")
        revision[key] = value
    if revision.get("release_id") != release or revision.get("commit") != commit:
        raise ReadinessError("revision-identity")

    phase_invocation = ""
    while True:
        unit_raw = command(
            "unit",
            [
                "/usr/bin/systemctl", "show", "tiny-ipa-api.service", "--no-pager",
                "--property=ActiveState", "--property=MemoryMax",
                "--property=TasksMax", "--property=InvocationID",
            ],
            deadline, run, monotonic,
        )
        invocation = parse_unit(unit_raw)
        if not phase_invocation:
            phase_invocation = invocation
            if prior_invocation and invocation == prior_invocation:
                raise ReadinessError("unchanged-invocation")
        elif invocation != phase_invocation:
            raise ReadinessError("invocation-changed")

        listeners = command(
            "listener", ["/usr/bin/ss", "-ltnH", "sport = :18110"], deadline,
            run, monotonic,
        )
        if listeners:
            rows = [row.split() for row in listeners.splitlines()]
            if any(len(row) < 5 for row in rows):
                raise ReadinessError("listener-shape")
            if any(row[3] != "127.0.0.1:18110" for row in rows):
                raise ReadinessError("listener-not-loopback")
            try:
                health = request(
                    "/api/health", deadline, connection_factory, monotonic,
                )
            except (OSError, http.client.HTTPException):
                health = None
            if health is not None:
                if health[0] != 200 or health[2].get("status") != "ok":
                    raise ReadinessError("health-contract")
                version = request(
                    "/api/version", deadline, connection_factory, monotonic,
                )
                anonymous = request(
                    "/api/auth/me", deadline, connection_factory, monotonic,
                )
                protected = request(
                    "/api/progress", deadline, connection_factory, monotonic,
                )
                if not (
                    version[0] == 200
                    and version[2] == {
                        "status": "ok", "release_id": release,
                        "commit": commit, "tag": None,
                    }
                    and "no-store" in version[1].lower()
                ):
                    raise ReadinessError("version-contract")
                if anonymous[0] != 200 or anonymous[2] != {
                    "authenticated": False, "user": None,
                }:
                    raise ReadinessError("anonymous-contract")
                if (
                    protected[0] != 401
                    or protected[2].get("detail", {}).get("error") != "AUTH_REQUIRED"
                ):
                    raise ReadinessError("protected-contract")
                return phase_invocation
        if remaining(deadline, monotonic) <= POLL_INTERVAL:
            raise ReadinessError("readiness-timeout")
        sleep(POLL_INTERVAL)


if __name__ == "__main__":
    phase, release, commit, prior_invocation = sys.argv[1:]
    try:
        print(readiness(phase, release, commit, prior_invocation))
    except ReadinessError as error:
        print(str(error))
        raise SystemExit(1) from None
# P1A_RUNTIME_PROBE_END
PY
  )
  probe_rc=$?
  if test "$probe_rc" -eq 124; then
    hold 109 "$phase-readiness-timeout"
  fi
  test "$probe_rc" -eq 0 || hold 109 "$phase-${output:-readiness-failed}"
  [[ $output =~ ^[0-9a-f]{32}$ ]] || hold 104 "$phase-invocation-output"
  P1A_INVOCATION=$output
}
# P1A_RUNTIME_ACCEPT_SHELL_END

runtime_accept before-restart ''
before_invocation=$P1A_INVOCATION
/usr/bin/timeout 45s sudo -n systemctl restart tiny-ipa-api.service
restart_rc=$?
test "$restart_rc" -eq 0 || hold 110 "restart-rc=$restart_rc"
runtime_accept after-restart "$before_invocation"
test "$P1A_INVOCATION" != "$before_invocation" || hold 111 unchanged-invocation

readonly P1A_CURL=/usr/bin/curl
readonly P1A_P0_HOLD_CODE=112
capture curl_version curl-version "$P1A_CURL" -q --version
export P1A_CURL
<P1A_CANONICAL_P0_PROBE>
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

## P1b controlled public-phone trial

P1a is accepted as a private synthetic trial. P1b may reuse its backend release,
state and versioned backup tool, but it must not infer that public ingress,
licensed audio, a non-empty learner state, natural timer execution or phone use
already works. Issue #304 owns the repository package; issue #282 owns every
real-host decision and receipt.

The checked-in `p1b-content-audio.manifest.json` is a hard gate. It now binds a
Human-approved `ready` package with one source, license, size and SHA-256 entry
for each required trial word; public credits and conversion disclosure live in
`audio/ATTRIBUTION.md`. The operator copies that file to
`/var/lib/tiny-ipa/audio/ATTRIBUTION.md`, and the manifest binds its SHA-256 and
public `/audio/ATTRIBUTION.md` URL. Before host apply, a Reviewer must accept the exact
manifest and asset bytes. `verify-p1b-assets.py` must return
`status=manifest_integrity_verified` against the frozen repo and audio roots.
This proves package paths, containment, non-empty bounded size, checksums and
declared source/use permission; it does not prove codec validity, the spoken
word, browser playback or legal approval. Those user-visible properties remain
part of the HTTPS phone walkthrough. Browser TTS and paid generation cannot
satisfy this gate.

The manifest is also the controlled-trial runtime availability allowlist. Only
its ten word ids may keep a non-null `audio_us` in Core 100; every unbound word
must use `null`. Normal practice scheduling requires a packaged audio URL for
the selected accent, so a Today group cannot advertise an undeployed file or
silently substitute browser TTS for the accepted MP3 evidence.

### Bounded read-only discovery

This block is a candidate, not present authority to SSH. It returns only the
metadata needed to freeze the actual shared-ingress and ACME diff. It does not
read certificate bytes, secret/env contents, Nginx file contents, private rows,
journals or process command lines.

```bash
# P1B_READONLY_DISCOVERY_BEGIN
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no \
  -o ConnectTimeout=10 -o ConnectionAttempts=1 -o ClearAllForwardings=yes \
  -o ForwardAgent=no -o ForwardX11=no -o ControlMaster=no -o ControlPath=none \
  jingyun 'env -i PATH=/usr/bin:/bin /bin/bash --noprofile --norc -s' \
  < deploy/jingyun/p1b-readonly-discovery.sh
# P1B_READONLY_DISCOVERY_END
```

The frozen operator packet binds the SHA-256 of
`deploy/jingyun/p1b-readonly-discovery.sh`. Every producer has a five-second
timeout and any DNS producer, listener, unit, privileged metadata, capacity or
tool-version query failure returns HOLD. DNS no-answer is represented as an
explicit empty JSON list only when the resolver itself returns `gaierror`;
permission or command failures cannot be reported as an absent path.

### Frozen P1b host and package snapshot

The 2026-09-16 bounded host read found Ubuntu Nginx 1.24.0, Snap 2.75.2 and no
installed snaps or ACME client. Nginx 1.24.0 supports
`ssl_reject_handshake`, so the reviewed final candidate adds one IPv4
`listen 443 ssl default_server` rejection server followed by the exact
`ipa.jingyun.bj.cn` TLS server. It adds no IPv6 443 listener and does not alter
the existing IPv4/IPv6 default HTTP server.

The same-day Snap Store snapshot binds these amd64 `latest/stable` artifacts:

- Certbot 5.8.0, revision 5893, snap ID
  `wy7i66qPx4neXr6m9rTh7Y40h8EhtZFh`, 75,173,888 bytes, SHA3-384
  `9f1b58aea2d76a787f636f3d17ecd88e568714cc8ffda659dcc2a71b7791554fd7a7f2e6de1678438d00c3d209f4960b`;
- core24 20260824, revision 2124, snap ID
  `dwTAh7MZZ01zyriOZErqd1JynQLiOGvM`, 70,033,408 bytes, SHA3-384
  `9f84f391c5ace85b755a7530a330f7b52aff891178cdfdf10bc4f673f261ea9454629ddd933991cbedaf7963e689789c`.

Certbot's v5.8.0 build declares classic confinement, `base: core24`, and one
Snap-managed `renew` oneshot with timer `00:00~24:00/2`. The host currently
reports no installed snaps and `snap refresh --time` reports the default
`00:00~24:00/4` timer, an expired 2024 hold value, and no next refresh. The
install gate must therefore stop unless the store metadata still matches both
frozen revisions. It then installs exactly core24 revision 2124 followed by
Certbot revision 5893; no global `snap refresh`, apt operation, OS upgrade or
additional snap is permitted. After installation it must read back the two
versions/revisions, tracking channel, publisher, installed dependency set,
`snap.certbot.renew.timer` and service state, and Snap refresh next-run state.
Unexpected dependencies, a disabled/missing renewal timer, or no scheduled Snap
refresh is HOLD for classification rather than permission to repair global
Snap policy.

The certificate request requires `<HUMAN_APPROVED_ACME_EMAIL>`, acceptance of
the then-current Let's Encrypt Subscriber Agreement (v1.8 was current in the
2026-09-16 repository snapshot), `<HUMAN_APPROVED_EXECUTION_WINDOW>`, and
`<HUMAN_APPROVED_MAINTAINER>`. The command is non-interactive, requests only
`ipa.jingyun.bj.cn`, uses the reviewed webroot, fixes the cert name to that
hostname and passes the reviewed versioned
`p1b-certbot-deploy-hook.sh` with `--deploy-hook`. That hook returns without a
reload for every other lineage. For this lineage it additionally requires the
reviewed active-site symlink and exact final-site SHA-256 before bounded
`nginx -t` and a shared reload. The bootstrap site's different hash means the
initial issuance does not reload Nginx; only the separately authorized final
activation does. No file is added to the global renewal-hook directories and no
second scheduler is created.

The exact installation and issuance command block remains CANDIDATE - DO NOT
APPLY until #282 records the final artifact hashes, private trial owner input,
window/maintainer values and Human approval:

```bash
# P1B_SNAP_INSTALL_GATE_BEGIN
set -euo pipefail
core_info=$(/usr/bin/timeout 20s /usr/bin/snap info core24)
certbot_info=$(/usr/bin/timeout 20s /usr/bin/snap info certbot)
core_revision=$(printf '%s\n' "$core_info" | sed -n 's/^  latest\/stable:.*(\([0-9][0-9]*\)).*$/\1/p')
certbot_revision=$(printf '%s\n' "$certbot_info" | sed -n 's/^  latest\/stable:.*(\([0-9][0-9]*\)).*$/\1/p')
test "$core_revision" = 2124
test "$certbot_revision" = 5893
sudo -n /usr/bin/timeout 120s /usr/bin/snap install core24 --revision=2124
sudo -n /usr/bin/timeout 120s /usr/bin/snap install certbot --classic --revision=5893
snap_inventory=$(/usr/bin/timeout 5s /usr/bin/snap list --all)
installed=$(printf '%s\n' "$snap_inventory" | /usr/bin/awk 'NR > 1 {print $1 ":" $3}' | /usr/bin/sort)
test "$installed" = 'certbot:5893
core24:2124'
timer_load=$(/usr/bin/timeout 5s /usr/bin/systemctl show snap.certbot.renew.timer -p LoadState --value)
timer_active=$(/usr/bin/timeout 5s /usr/bin/systemctl show snap.certbot.renew.timer -p ActiveState --value)
timer_sub=$(/usr/bin/timeout 5s /usr/bin/systemctl show snap.certbot.renew.timer -p SubState --value)
timer_unit_file=$(/usr/bin/timeout 5s /usr/bin/systemctl show snap.certbot.renew.timer -p UnitFileState --value)
service_load=$(/usr/bin/timeout 5s /usr/bin/systemctl show snap.certbot.renew.service -p LoadState --value)
test "$timer_load" = loaded
test "$timer_active" = active
test "$timer_sub" = waiting
test "$timer_unit_file" = enabled
test "$service_load" = loaded
refresh_state=$(/usr/bin/timeout 5s /usr/bin/snap refresh --time)
printf '%s\n' "$refresh_state"
printf '%s\n' "$refresh_state" | /usr/bin/grep -Eq '^next: .+'
if printf '%s\n' "$refresh_state" | /usr/bin/grep -Eq '^next: n/a$'; then
  exit 1
fi

sudo -n /usr/bin/timeout 180s /snap/bin/certbot certonly \
  --non-interactive --agree-tos --no-eff-email \
  --email '<HUMAN_APPROVED_ACME_EMAIL>' \
  --cert-name ipa.jingyun.bj.cn -d ipa.jingyun.bj.cn \
  --webroot -w /var/lib/tiny-ipa/acme-webroot \
  --deploy-hook '/opt/tiny-ipa/ops/<APPROVED_TOOL_REVISION>/p1b-certbot-deploy-hook.sh'
# P1B_SNAP_INSTALL_GATE_END
```

A separate coordinator-side public probe records the authoritative DNS answer,
TCP 80/443 reachability and certificate hostname/issuer/time metadata without
sending credentials, following redirects or recording response bodies. A
missing answer, unexpected address, unknown port owner, competing ACME manager,
existing Tiny IPA site, or changed P1a identity is a stop for classification;
it is not permission to overwrite, select a new domain or switch challenge
methods.

### Frozen repository and asset preconditions

Before requesting apply authorization, the packet binds:

- one reviewed P1b commit and frontend tree built with `VITE_API_BASE=/api`;
- the existing P1a backend release when its app tree is unchanged, or a newly
  reviewed application release when executable backend bytes changed;
- the exact Nginx candidate and the discovery-confirmed single ACME owner;
- a `ready` content/audio manifest and successful verifier output;
- Core 100 import and phoneme checksums, a collision-refusing frontend release,
  the audio asset list, and the existing private DB identity;
- one private-input owner bootstrap command using `--password-stdin`;
- pre-state hashes/links for only the Tiny IPA site, frontend and certificate
  bindings that the withdrawal may restore.

The repository candidate assumes Certbot `certonly --webroot` paths only when
discovery proves no other supported ACME owner. It never stops Nginx for a
standalone challenge, installs a second proxy, changes the default site, edits
global HSTS/cookie policy, or touches XueTuZhiBan routes/upstreams/certificates.
For the no-existing-certificate fallback, the HTTP-only bootstrap candidate is
validated and reloaded first. The final HTTPS candidate is validated and
reloaded only after certificate issuance. These are two separately reviewed,
bounded Nginx reloads. The bootstrap does not alter a shared/default server;
the final candidate adds the reviewed IPv4 443 handshake-rejection default and
the exact-host Tiny IPA server while leaving default HTTP and IPv6 unchanged.

### Conditional apply and acceptance order

One later Human decision may cover this already frozen sequence:

1. Revalidate discovery identities, P1a app/tool/state and the protected route
   matrix. Stage frontend, manifest, verifier, approved audio and
   `audio/ATTRIBUTION.md` under private
   collision-refusing paths.
2. Verify content/audio bytes offline. Import the bound public Core 100 into the
   existing trial DB, then use private stdin to create exactly one trial owner.
   Never print the password, cookie, private rows or password/session hashes.
3. Materialize only the Tiny IPA ACME webroot, frontend release, audio files and
   the manifest-bound credits at `/var/lib/tiny-ipa/audio/ATTRIBUTION.md`.
   When discovery proves no existing certificate or supported ACME owner,
   collision-refuse the Tiny IPA binding, install the HTTP-only bootstrap
   candidate, require candidate-content equality and `nginx -t`, then perform
   bounded reload 1. Prove the challenge path and issue with reviewed Certbot
   `certonly --webroot`; never stop Nginx for a standalone challenge.
4. After certificate paths exist, replace only the active Tiny IPA bootstrap
   binding with the final HTTPS candidate. Require candidate-content equality
   and `nginx -t`, then perform bounded reload 2. Existing supported ACME
   owners use their separately frozen equivalent sequence rather than Certbot.
5. Check HTTPS `/`, `/api/health`, `/api/version` and one known `/audio/` MP3;
   verify exact origin, Secure/HttpOnly/SameSite=Lax/Path cookie behavior and
   anonymous/wrong-password/foreign-Origin/logout rejection without recording
   secret headers.
6. Complete one real-phone login, Settings, non-empty Today practice, approved
   MP3 playback, Progress, refresh/reopen and logout walkthrough. Restart only
   `tiny-ipa-api.service`, log in again and prove saved state persists.
7. Run online backup for the new non-empty state and restore to a separate
   candidate. Verify content, owner, settings, attempts, progress and session
   semantics by counts/owned relationships and representative app reads, never
   by publishing private values or switching the active DB.
8. Observe one natural timer occurrence separately from manual runs. If it has
   not elapsed, record `pending`; if the known missing-SHM condition appears,
   stop and return the minimal backup defect for review.
9. Repeat protected XueTuZhiBan checks. Record timer enabled/persistent state,
   retention capacity, next maintenance check, notification owner and off-host
   decision exactly as observed.

P1b keeps API and timer boot enablement unchanged and `Persistent=false` unless
a separate Human choice authorizes persistence. It keeps the seven-snapshot,
100 MiB and no-prune limits. Same-host trial backup is not disaster recovery.

### Withdrawal

Any failed ingress or phone phase stops further work. The frozen withdrawal
removes only the newly enabled Tiny IPA server binding from the active Nginx
set, restores its recorded prior Tiny IPA pointer/config when applicable, runs
`nginx -t`, performs one bounded authorized withdrawal reload, and proves the protected
route matrix. It stops only Tiny IPA units started by this packet when needed.
It preserves the certificate, frontend/audio releases, trial DB, owner, backup,
restore candidate, logs and failed artifacts for diagnosis. No account, data,
certificate, backup or old P1a evidence is deleted automatically.
