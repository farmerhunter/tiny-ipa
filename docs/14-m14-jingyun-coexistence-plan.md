# M14 Jingyun Coexistence Deployment Plan

This document defines the proposed Tiny IPA deployment boundary for
`jingyun.bj.cn`. The same VPS currently runs the higher-priority
Xue Tu Zhi Ban application. Tiny IPA may proceed only when every step can be
isolated from that application and its related services, routes, ports, files,
configuration, data, and operational schedule.

This is a design and review artifact. It does not authorize package
installation, file or configuration writes, service changes or restarts,
DNS/TLS changes, secret generation, database mutation, backup restore, or a
deployment.

## Status and evidence boundary

Evidence collected under the Human-authorized read-only preflight for #282:

| Area | Sanitized observation | Decision impact |
| --- | --- | --- |
| Host | SSH alias `jingyun`; user `ubuntu`; host `VM-0-7-ubuntu`; Ubuntu 24.04.4 LTS; Linux `6.8.0-134-generic` | A later trial may target this host only after a new authorization. |
| Capacity | Root disk about 59 GiB with 41 GiB available; memory about 3.6 GiB with 2.4 GiB available at observation time | Capacity was not an immediate blocker, but must be re-read before mutation. |
| Public entry | `jingyun.bj.cn` resolved to `49.233.203.222`; TCP 80 accepted a connection but HTTP HEAD timed out; TCP 443 refused | Do not assume a working HTTP/TLS route or take ownership of the root hostname. |
| Active services | `nginx.service`, `xuetuzhiban-api.service`, `redis-server.service`, `chatbox.service`, and SSH were active | Tiny IPA must not edit, restart, stop, reuse, or depend on these services. |
| Listeners | 80, 3000, 8010, 5173, 8000, 8001, 8002, and 6379 were occupied | Tiny IPA must use a separately reserved loopback port. |
| Existing paths | `/opt/hermes`, `/opt/hermes/2026agentapp-prod`, `/var/www/hermes-web`, and `/home/ubuntu/.hermes` existed | These namespaces and their descendants are forbidden Tiny IPA targets. |

The preflight did not inspect private file contents, secrets, learner data, or
database rows. It did not establish current DNS/TLS ownership or explain the
public port-80 timeout. These observations are a dated planning snapshot, not
permission to operate the host.

## Minimum Responsible Architecture

### Frozen Invariants

1. Xue Tu Zhi Ban availability and integrity outrank Tiny IPA delivery. A Tiny
   IPA step stops before mutation if it could affect that application's
   services, listeners, routes, files, data, Redis instance, or review window.
2. Tiny IPA owns a distinct namespace for code, web assets, environment,
   service identity, database, audio, logs, and backups. No Tiny IPA path may
   be nested under a Hermes or Xue Tu Zhi Ban path.
3. Tiny IPA binds only to an explicitly revalidated free loopback port. It must
   not bind observed occupied ports, especially 80, 3000, 5173, 8000, 8001,
   8002, 8010, or 6379.
4. Nginx, systemd, firewall, DNS, TLS, secrets, private databases, backups, and
   service state remain Human-controlled boundaries. Each real-host mutation
   needs a separately reviewed target and explicit authorization.
5. Every staged action is fail-closed and reversible: record pre-state, exact
   target, owner, verification, and rollback boundary; stop on ambiguity,
   collision, failed health evidence, or an unexpected write target.

### Accepted residuals

- The port-80 timeout is unexplained. Tiny IPA planning does not debug it by
  changing Nginx or the existing application.
- Public 443 was unavailable during the preflight. Certificate source, renewal
  owner, and redirect policy remain undecided.
- `ipa.jingyun.bj.cn` is a proposed hostname. Its DNS and certificate owner
  still require Human confirmation.
- The preflight snapshot can drift. Port, capacity, service health, and path
  non-existence must be checked again immediately before any authorized write.
- Production content volume and backup retention size are not yet measured on
  this host. A later operator decision must set retention without consuming
  space needed by Xue Tu Zhi Ban.

### Deferred capabilities

- Real deployment, package installation, and host configuration writes.
- DNS and TLS issuance or renewal changes.
- Production secret generation and storage.
- Private database migration, default-owner claim apply, or data import.
- In-place restore, automated rollback, or unattended deployment.
- Shared Redis, shared process managers, shared databases, or shared web roots.
- Monitoring or alerting that changes the existing host stack.

## Proposed isolated namespace

These values are candidates for review. They are not approved host resources
until the Human owner authorizes a staged trial.

| Responsibility | Proposed value | Isolation rule |
| --- | --- | --- |
| Deployment root | `/opt/tiny-ipa` | Never reuse `/opt/hermes` or an existing checkout. |
| Release checkout | `/opt/tiny-ipa/releases/<commit-or-timestamp>` | One immutable backend release directory per rollout. |
| Active backend release | `/opt/tiny-ipa/current` | Symlink to one reviewed release; change only in an authorized rollout or rollback. |
| Environment file | `/etc/tiny-ipa/tiny-ipa.env` | Human-owned, outside Git, restricted read access. |
| SQLite database | `/var/lib/tiny-ipa/tiny-ipa.sqlite` | Separate file and directory; never use another app's database. |
| Audio directory | `/var/lib/tiny-ipa/audio` | Canonical `TINY_IPA_AUDIO_DIR` target. |
| Log policy | journald for `tiny-ipa-api.service` | Do not add a shared log service during M14. |
| Backup directory | `/var/backups/tiny-ipa` | Separate retention and ownership; no in-place restore. |
| Frontend web root | `/var/www/tiny-ipa/releases/<commit-or-timestamp>` | Never write under `/var/www/hermes-web`; use the same release ID as the backend. |
| Active frontend release | `/var/www/tiny-ipa/current` | Symlink to one reviewed frontend build. |
| systemd unit | `tiny-ipa-api.service` | Do not modify or depend on `xuetuzhiban-api.service`. |
| Backend bind | `127.0.0.1:18110` | Candidate only; prove free again before use. |
| Public hostname | `ipa.jingyun.bj.cn` | Preferred over taking over root `jingyun.bj.cn`. |

The service, SQLite file, release directories, and active-release pointers are
the only new durable resources proposed for the M14 main path. Removing one
removes a contracted capability: supervised API runtime, persistent learner
state, or a reviewable release/rollback boundary. Redis, containers, a process
manager, and a deployment registry are not required.

Substitution test: a later operator may replace Nginx with another reverse
proxy, or `/opt/tiny-ipa` with another approved isolated root. The architecture
still requires the same hostname isolation, loopback API boundary, separate
state paths, Human-owned secrets, fail-closed checks, and non-interference
invariants.

## Public entry and routing plan

The preferred entry is the dedicated subdomain `ipa.jingyun.bj.cn`. The root
hostname `jingyun.bj.cn` remains outside Tiny IPA scope unless the Xue Tu Zhi
Ban owner explicitly approves a route-ownership change.

The proposed Tiny IPA-only routing shape is:

```text
https://ipa.jingyun.bj.cn/
  /          -> /var/www/tiny-ipa/current with SPA fallback
  /api/      -> http://127.0.0.1:18110/api/
  /api/health -> http://127.0.0.1:18110/api/health
  /audio/    -> /var/lib/tiny-ipa/audio/
```

A future candidate Nginx diff must:

- add only a Tiny IPA-specific `server_name` and locations;
- leave existing server blocks, default routes, upstreams, certificates, and
  redirects unchanged;
- keep the deployed frontend build on `VITE_API_BASE=/api`;
- map `/audio/` to the same directory named by `TINY_IPA_AUDIO_DIR`;
- be reviewed before transfer to the host;
- pass `nginx -t` before any separately authorized reload;
- stop without reload if the diff or validation mentions an existing
  Xue Tu Zhi Ban/Hermes route unexpectedly.

Because public 443 was unavailable, the TLS mechanism is deliberately not
selected here. Certbot, an existing certificate manager, or a pre-provisioned
certificate are implementation options only after ownership is known. No
option may alter Xue Tu Zhi Ban certificates or redirects.

## Runtime and data contract

The proposed environment shape extends the accepted M14 contracts:

```dotenv
TINY_IPA_ENV=production
TINY_IPA_DB_PATH=/var/lib/tiny-ipa/tiny-ipa.sqlite
TINY_IPA_SESSION_SECRET=<Human-provisioned secret>
TINY_IPA_ALLOWED_ORIGINS=https://ipa.jingyun.bj.cn
TINY_IPA_COOKIE_SECURE=true
TINY_IPA_COOKIE_SAMESITE=lax
TINY_IPA_AUDIO_DIR=/var/lib/tiny-ipa/audio
```

`TINY_IPA_LOG_DIR` is intentionally omitted because this plan selects journald
for M14. Adding a file log directory would be a separate design and retention
decision.

The real secret must never enter GitHub, terminal evidence, logs, screenshots,
or a checked-in file. Secret generation and writing the environment file are
future Human-gated actions.

The first authorized trial must initialize either a new Tiny IPA database or
an explicitly named disposable trial database. It must not inspect or mutate a
private Xue Tu Zhi Ban database. Production backup creation, retention, an
off-host copy, and any restore remain separate Human decisions. A restore must
target a separate path first; in-place restore is outside M14 authorization.

## Pre-mutation checkpoint

Immediately before any future authorized write, capture sanitized evidence for:

```bash
whoami
hostname
date -Iseconds
ss -ltnp
systemctl is-active nginx.service xuetuzhiban-api.service
systemctl show xuetuzhiban-api.service \
  -p ActiveState -p SubState -p FragmentPath -p WorkingDirectory
test -e /opt/tiny-ipa
test -e /var/www/tiny-ipa
test -e /var/lib/tiny-ipa
test -e /var/backups/tiny-ipa
```

These commands are listed as evidence requirements; this document does not
authorize running them. The authorized operator must also compare the current
listener list with the preflight snapshot and confirm that port `18110` is free.

Stop before mutation when:

- `xuetuzhiban-api.service` is not active/running before the Tiny IPA trial;
- port `18110` is occupied or listener ownership is unclear;
- any proposed path already exists with unknown ownership;
- a planned path overlaps `/opt/hermes`, `/var/www/hermes-web`,
  `/home/ubuntu/.hermes`, or another application's state;
- the candidate proxy diff changes an existing route, upstream, certificate,
  redirect, or default site;
- backup ownership, rollback owner, or separate restore target is unclear;
- the Xue Tu Zhi Ban owner reports an active review, deployment, incident, or
  maintenance window that conflicts with the trial.

## Future staged deployment trial

After the namespace, domain, owners, and exact candidate diffs are approved, a
later authorization may release these phases one at a time:

1. Re-run the pre-mutation checkpoint and record the Xue Tu Zhi Ban health
   baseline using only an owner-approved health path; active systemd state alone
   is not sufficient application-health evidence.
2. Create only the approved Tiny IPA directories and ownership.
3. Install or verify dependencies only when package actions are explicitly in
   scope and cannot affect the existing app runtime.
4. Place an exact Tiny IPA release checkout and build the frontend with
   `VITE_API_BASE=/api`.
5. Write the Tiny IPA-only environment file and initialize the approved new or
   disposable SQLite database.
6. Add `tiny-ipa-api.service` on `127.0.0.1:18110`; validate it before start.
7. Prepare and validate the Tiny IPA-only proxy/TLS candidate without reload.
8. Re-check Xue Tu Zhi Ban health, then request separate authorization for any
   proxy reload or public DNS/TLS activation.
9. Run the #281 live smoke rows: HTTPS/domain, frontend, `/api/health`, login,
   Settings save, Today start/resume, `/audio/`, and restart persistence.
10. Create and verify the separately authorized Tiny IPA backup, record
    rollback evidence, and re-check Xue Tu Zhi Ban health.

Each phase has its own stop point. Authorization for one phase does not imply
authorization for the next, and a failed check does not authorize repair by
changing the other application.

## Next Human Decision Contract

Before candidate config generation or any staged host action, the Human owner
must confirm the namespace and responsibility owners. A suitable planning-only
authorization phrase is:

```text
Tiny IPA may use ipa.jingyun.bj.cn, /opt/tiny-ipa, /var/www/tiny-ipa,
/var/lib/tiny-ipa, /var/backups/tiny-ipa, service tiny-ipa-api.service, and
backend port 18110 as the planned isolated deployment namespace, with all
changes still requiring a separate staged deployment authorization.
```

This phrase authorizes planning and candidate configuration generation only.
It does not authorize applying anything to `jingyun.bj.cn`.
