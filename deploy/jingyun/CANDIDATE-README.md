# Jingyun Tiny IPA Candidate Artifacts

CANDIDATE - DO NOT APPLY.

These files are repository-only review artifacts for the Human-approved Tiny
IPA planning namespace:

- Hostname: `ipa.jingyun.bj.cn`
- Deployment root: `/opt/tiny-ipa`
- Frontend root: `/var/www/tiny-ipa`
- State root: `/var/lib/tiny-ipa`
- Backup root: `/var/backups/tiny-ipa`
- Service: `tiny-ipa-api.service`
- Backup units: `tiny-ipa-backup.service` and `tiny-ipa-backup.timer`
- Backend bind: `127.0.0.1:18110`
- Version readback: `/opt/tiny-ipa/current/REVISION` and `/api/version`

They do not authorize SSH, package installation, host reads or writes, user or
directory creation, environment-file writes, secret generation, database
creation or mutation, systemd/Nginx/firewall/DNS/TLS changes, service reloads,
backup, restore, rollback, or deployment.

P1b uses the repository candidate certificate paths under
`/etc/letsencrypt/live/ipa.jingyun.bj.cn/`. Host discovery must still confirm
the existing ACME owner and scheduler before those paths are treated as real.
The candidate prefers the existing supported manager; Certbot webroot is only
the reviewed fallback when no manager exists.

Other full-public bindings that remain unresolved after P1a:

- `<HUMAN_PROVISIONED_TINY_IPA_SESSION_SECRET>`
- `<HUMAN_APPROVED_BACKUP_OWNER>`
- `<HUMAN_APPROVED_BACKUP_RETENTION_POLICY>`
- `<HUMAN_APPROVED_ROLLBACK_OWNER>`
- `<INTENDED_GIT_COMMIT_OR_TAG_RELEASE_ID>`
- `<INTENDED_GITHUB_COMMIT_SHA>`
- `<OPTIONAL_SIGNED_OR_ANNOTATED_GIT_TAG>`
- `<UTC_RELEASE_ARTIFACT_TIMESTAMP>`

`p1b-content-audio.manifest.json` binds the accepted Core 100 and phoneme
inputs. It deliberately has status `blocked_missing_approved_audio`: this
repository contains no MP3 payload, source or license. A Reviewer must replace
that state with a non-empty checksum list for the ten required trial words
before any P1b apply packet can pass. Browser TTS and paid generation are not
accepted substitutes.

P1a instead fixes `tiny-ipa:tiny-ipa` and `/etc/tiny-ipa/tiny-ipa.env`; its
exact accepted release ID, commit, artifact digest, trial operator, and bounded
withdrawal are materialized in #282 before the host-action decision.

Review these files with `backend/tests/test_m14_jingyun_candidate_artifacts.py`
before any future Human-authorized transfer to a VPS.

The P1a private-loopback packet installs `p1a-backup.py` under the versioned
`/opt/tiny-ipa/ops/<APPROVED_TOOL_REVISION>/` root with the matching frozen
backup unit template, then materializes the backup service and timer candidates.
It fixes the trial service identity to non-login
`tiny-ipa:tiny-ipa`, uses `/etc/tiny-ipa/tiny-ipa.env`, limits the API to
`MemoryMax=512M` and `TasksMax=64`, caps each backup at 100 MiB, refuses an
eighth successful snapshot, and schedules 03:20 UTC with `Persistent=false`.
It never prunes or restores automatically. The only supported restore action
is the separate `verify-restore` command documented in docs/16.

P1a includes no Nginx, DNS, TLS, firewall, frontend, public-route, or other-app
change. Its candidate files remain review artifacts until #282 records the
exact integrated release commit and a Human approves the frozen H0 through H2
packet and its bounded withdrawal.

The accepted phase boundary is readonly H0, then the first authorized writes in
a fresh mode-0700 `/tmp/tiny-ipa-p1a` H1-staging root, then H1-activation and
H2. Staging proves the exact target venv can install and import the frozen
offline wheel set before any account, final app root, unit, database, pointer,
or service mutation. A staging failure retains that root and stops.
