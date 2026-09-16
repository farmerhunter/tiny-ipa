#!/bin/bash
# CANDIDATE - DO NOT APPLY. Human authorization is required before SSH execution.
set -u -o pipefail

hold() { printf 'HOLD %s\n' "$2" >&2; exit "$1"; }
capture() {
  local target=$1 label=$2 output rc
  shift 2
  output=$(/usr/bin/timeout 5s "$@" 2>&1); rc=$?
  test "$rc" -eq 0 || hold 160 "$label-rc=$rc"
  printf -v "$target" '%s' "$output"
}

capture identity identity /usr/bin/whoami
capture host host /usr/bin/hostname
capture machine machine /usr/bin/uname -m
test "$identity" = ubuntu || hold 161 identity
test "$host" = VM-0-7-ubuntu || hold 162 host
test "$machine" = x86_64 || hold 163 machine
printf 'identity=%s host=%s machine=%s\n' "$identity" "$host" "$machine"

dns_output=$(/usr/bin/timeout 5s /usr/bin/python3 -I -B - <<'PY'
import json
import socket
try:
    rows = socket.getaddrinfo("ipa.jingyun.bj.cn", None, family=socket.AF_INET)
except socket.gaierror:
    print(json.dumps({"dns_ipv4": []}, separators=(",", ":")))
else:
    values = sorted({row[4][0] for row in rows})
    print(json.dumps({"dns_ipv4": values}, separators=(",", ":")))
PY
); rc=$?
test "$rc" -eq 0 || hold 164 "dns-query-rc=$rc"
printf '%s\n' "$dns_output"

capture listeners listeners /usr/bin/sudo -n /usr/bin/ss -ltnpH '( sport = :80 or sport = :443 or sport = :18110 )'
printf '%s\n' "$listeners"

for unit in nginx.service certbot.timer snap.certbot.renew.timer tiny-ipa-api.service tiny-ipa-backup.service tiny-ipa-backup.timer; do
  capture unit_state "unit-$unit" /usr/bin/systemctl show "$unit" --no-pager --property=LoadState --property=ActiveState --property=SubState --property=UnitFileState
  printf 'UNIT %s\n%s\n' "$unit" "$unit_state"
done

if certbot_path=$(command -v certbot); then
  case "$certbot_path" in /usr/bin/certbot|/snap/bin/certbot) : ;; *) hold 165 certbot-path ;; esac
  capture certbot_version certbot-version "$certbot_path" --version
  printf 'certbot=present version=%s\n' "$certbot_version"
else
  printf 'certbot=absent\n'
fi

metadata_output=$(/usr/bin/timeout 5s /usr/bin/sudo -n /usr/bin/python3 -I -B - <<'PY'
import json
import os
import stat
paths = (
    "/etc/nginx/sites-enabled/ipa.jingyun.bj.cn",
    "/etc/letsencrypt/live/ipa.jingyun.bj.cn",
    "/var/lib/tiny-ipa/acme-webroot",
    "/var/www/tiny-ipa/current",
    "/var/lib/tiny-ipa/audio",
)
rows = []
for path in paths:
    try:
        value = os.lstat(path)
    except FileNotFoundError:
        rows.append({"path": path, "state": "absent"})
        continue
    kind = "directory" if stat.S_ISDIR(value.st_mode) else "symlink" if stat.S_ISLNK(value.st_mode) else "file" if stat.S_ISREG(value.st_mode) else "other"
    rows.append({
        "gid": value.st_gid,
        "kind": kind,
        "mode": format(stat.S_IMODE(value.st_mode), "04o"),
        "path": path,
        "state": "present",
        "uid": value.st_uid,
    })
print(json.dumps({"path_metadata": rows}, sort_keys=True, separators=(",", ":")))
PY
); rc=$?
test "$rc" -eq 0 || hold 166 "path-metadata-rc=$rc"
printf '%s\n' "$metadata_output"

capture capacity capacity /usr/bin/df -Pk / /var/lib /var/backups
printf '%s\n' "$capacity"
printf 'p1b-readonly-discovery-passed\n'
