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

`p1b-readonly-discovery.sh` is the fail-closed discovery artifact. The
no-existing-certificate fallback first activates only
`ipa.jingyun.bj.cn.acme-bootstrap.nginx.candidate`, validates it with
`nginx -t`, and performs bounded reload 1 so HTTP-01 can succeed. After Certbot
`certonly --webroot` creates the bound certificate paths, the operator replaces
only that Tiny IPA binding with `ipa.jingyun.bj.cn.nginx.candidate`, validates
again, and performs bounded reload 2. Both reloads remain Human-gated in #282.

The final candidate owns the first IPv4 443 default only to reject the TLS
handshake with `ssl_reject_handshake on`; it does not serve Tiny IPA for an
unknown or absent SNI name and does not add an IPv6 listener. The observed host
Nginx 1.24.0 supports that directive. The named Tiny IPA server remains a
separate exact-host binding.

`p1b-certbot-deploy-hook.sh` is the only proposed issuance/renewal deploy hook.
Certbot invokes it after a successful first issuance and successful renewals;
it returns without reloading for any lineage other than
`/etc/letsencrypt/live/ipa.jingyun.bj.cn`. For the Tiny
IPA lineage it additionally requires the reviewed active-site symlink, then
requires the exact final-site SHA-256 and runs bounded `nginx -t` before the
shared reload. The hash check makes the first issuance a no-reload event while
the HTTP bootstrap is active. It is passed to the single certificate issuance
with `--deploy-hook`; no global renewal hook, cron entry, or second timer is
proposed.

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
inputs and now has status `ready`. The ten approved trial MP3s are checked in
under `audio/us/`; `audio/ATTRIBUTION.md` records their public author, source,
license and conversion disclosure. The operator copies that file beside `us/`
to `/var/lib/tiny-ipa/audio/ATTRIBUTION.md`, where Nginx exposes the public
credits at `/audio/ATTRIBUTION.md`. The manifest binds the credits checksum and
each deployed audio byte size and SHA-256. `verify-p1b-assets.py` proves package integrity,
not pronunciation or playback. Those remain part of the HTTPS phone
walkthrough. Browser TTS and paid generation are not accepted substitutes.

The manifest is also the runtime availability allowlist for the controlled
trial. Only those ten Core 100 rows keep a non-null `audio_us`; every other Core
100 row uses `null`. Normal practice scheduling requires packaged audio for the
selected accent, so the P1b trial cannot emit a URL outside the deployed
manifest.

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


The separate `tiny-ipa-backup-rolling.service.candidate` opts into #309's
Human-selected two-fixed/two-rolling policy. The original candidate above is
unchanged. See docs/16's Post-M14 retention section for the explicit
bootstrap (seven legacy copies to an eighth without deletion), independent
restore, exact cleanup review and only then regular activation. Neither
candidate authorizes a host change. Normal replacement holds at most five
complete snapshots; shared backup/restore storage is bounded at 1 GiB.

## Post-M14 offline release rehearsal (#332)

This is local preparation, not online execution authority. With backend dev and
frontend dependencies already cached, run from `backend`:

```bash
UV_OFFLINE=true uv run --frozen --extra dev python scripts/offline_release_rehearsal.py \
  --source-revision <EXACT_40_CHARACTER_CANDIDATE_COMMIT>
```

The command allocates a new marked directory under the system temporary root;
`--output-root` may select a new path there. Existing paths, symlinks, traversal
and external roots are refused. It accepts no input database. Success and
failure roots remain for review. It performs no SSH, public probe, download,
service/timer operation, real retention prune or cleanup.

The source archive binds backend/frontend source, lockfiles and the optional
`content/sound_compare_pairs_candidate.json` evidence. Cached `pnpm install
--offline --frozen-lockfile` and frontend build run in the unpacked source.
The runtime archive contains built frontend assets, backend source, lockfiles,
content inputs and hash-checked recordings/credits. A second unpack loads the
app from that package in a separate Python process, using the installed local
Python environment. This is **not** a self-contained Linux dependency bundle
or systemd/VPS readiness proof. The receipt separates source/runtime archives,
build workspace/cache, fixture sizes and unknown host space. Native build
dependencies can differ across platforms.

The synthetic DB has one learner, one answer and pending items. Two synthetic
protected snapshots use the approved fixed IDs, plus one rolling backup with
`fixed2-rolling2-v1` and no deletion. Checksum/integrity/FK and learner state are
verified in a separately restored before-state. The existing 13-row tag plan
is applied, its stale reuse rejected, and a separate patched restore verified.
A different temp DB opts into the reviewed pair fields and explicitly binds
`TINY_IPA_SOUND_COMPARE_EVIDENCE_PATH` to check feedback and pair-data restore.
Ordinary code/tag fixtures do not activate pairs; default evidence stays unset.
Listening current reports `enabled:false`; starting a lesson stays 404. The
synthetic snapshots do not prove the identity or state of real recovery points.

A later online packet still needs review with final PR/release identity and
fresh current-release/data/free-space/backup-tool/policy/fixed-point readback:

1. Stage reviewed code/assets and prove cached Linux dependencies/load; retain
   the old release. Review exact pointer/service effects before switching.
   No schema migration or blanket content import is proposed.
2. Review a fresh tag-only plan if still needed; skip already-corrected state.
   Code switching does not grant data-patch authority.
3. Hold pair activation and evidence-env activation for a separate decision;
   keep listening and Human trials held.
4. Verify version/health, settings/history, normal practice and disabled lessons;
   create and independently restore a new backup only under the reviewed list.
   This rehearsal proposes no deletion.

Code-pointer rollback requires the old binary's verified identity and local
compatibility with candidate data. It cannot undo data writes. A real DB restore
needs a separate explicit decision because newer learner writes may be lost.
Failures retain old/new artifacts and stop the affected phase. The local receipt
does not claim that the unknown deployed old binary works.


## Additional Sound Compare pairs (#334, development only)

The opt-in `sound_compare_pairs_candidate.json` now contains four groups/eight
existing words. In addition to back/bag and came/game, cat/hat contrasts initial
/k/ and /h/; map/match contrasts final /p/ and /tʃ/. The latter is an existing
single phoneme token, not /t/ plus /ʃ/. These are distinct sound contrasts, not
both voicing-only distinctions. No canonical IPA/tags or recording bytes change.

The shared generator/runtime validator accepts two different existing inventory
phones at one first/final index, with complete ordered IPA reconstruction.
Source hashes, beginner level, current member/group facts, monosyllabic generation
and original Core100 media/hash/licence bindings still constrain the candidate;
no automatic pair discovery or general phonology rules are introduced. Existing
negative checks reject unsupported, split/merged, internal/multiple/unequal
contrasts and stale evidence. The ordinary default still has no active pair
metadata or evidence-file binding. Listening and live activation remain held.

The existing `pnpm test:e2e:sound-compare-candidate` route now covers all eight
words with actual recordings, both directions of the new pairs, post-answer
feedback, manual Continue, first-answer replay, resume and return to the chosen
normal mode. Licensed media is reused from the original99 fixture; no new
recording download, provider or binary fixture is needed. Evidence remains
source/integrity/native-playback only, not Human phonetic or teaching acceptance.

## Core300 audio candidate (#334, local only)

`core300-content-audio.manifest.json` is an explicit opt-in overlay for the
frozen 300-row source. It reuses all 99 Core100 recordings and their asset
bindings unchanged, adding 12 licensed Commons recordings: book, boy, brother,
country, double, down, father, mother, never, oil, weather and young. Coverage is
111 of 299 enabled words. The other 188 enabled words and disabled `feb` retain
`audio_us:null`; an original source URL alone never counts as packaged audio.
The source/IPA and canonical tags are not rewritten. Existing reviewed Core300
tag corrections are applied through their separate hash-bound provenance before
the audio-only overlay is derived.

With the exact audio files already in the local hash cache, run from `backend`:

```bash
UV_OFFLINE=true uv run --frozen python scripts/prepare_core100_audio.py --pack 300 --check-media
```

The default remains Core100. Core300 requires `--pack 300`; it has a separate
manifest, generated `content/generated/core_300_audio_candidate.json`, audio
candidate directory and content-hashed credits file. Downloading missing assets
requires the existing explicit `--allow-download`; there is no new provider,
credential or source-host allowance. Source/asset mismatch, unsafe path or
collision fails without overwriting existing bytes. Caches/generated audio are
not source files to commit or install automatically.

The bounded source selection and source/licence links are recorded on #334.
`core300-audio-attribution.md` preserves the reused credits and appends each new
file's source, author and CC BY-SA 3.0 licence. Wikimedia-provided MP3 transcodes
are copied unchanged. Weather's description names Dvortygirl as recorder while
the machine Artist field marks attribution assumed; the credits retain that
qualification. Integrity, automated decode and native playback do not certify
speaker identity, precise audible IPA agreement or learning effectiveness.

`pnpm test:e2e:core300-audio-candidate` from `frontend` uses the existing real
SQLite/API/browser harness and a small 12-recording fixture. It seeds two
synthetic learners and real normal-practice history, imports only the explicit
candidate into that disposable DB, checks prior learner rows unchanged, then
plays a newly covered word, records its answer and resumes the same group.
The Core100 fixture and default routes remain available for regression; this
candidate is included in CI. It does not activate live audio, pairs, evidence
configuration, listening or Human trials. Any later online asset/field delta
still needs its own concrete reviewed list; no production importer is added.
