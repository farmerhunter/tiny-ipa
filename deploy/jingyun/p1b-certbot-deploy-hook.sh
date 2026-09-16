#!/bin/sh
# CANDIDATE - DO NOT APPLY.
# Reload shared Nginx only after this exact Tiny IPA lineage renews successfully.

set -eu

expected_lineage=/etc/letsencrypt/live/ipa.jingyun.bj.cn
active_site=/etc/nginx/sites-enabled/ipa.jingyun.bj.cn
expected_site=/etc/nginx/sites-available/ipa.jingyun.bj.cn
expected_site_sha256=043c4ffa10370bb01e5e4eb1981e32c6fbc0e86488e78dd64532d56fe5dec44e
bootstrap_site_sha256=ca2022f714b841a91fabcc2b9af2fef905894cde548e69f62524372e8a38e36f

if test "${RENEWED_LINEAGE:-}" != "$expected_lineage"; then
    exit 0
fi

test -L "$active_site"
test "$(/usr/bin/readlink -f -- "$active_site")" = "$expected_site"
actual_site_sha256=$(/usr/bin/sha256sum -- "$expected_site" | /usr/bin/cut -d ' ' -f 1)
if test "$actual_site_sha256" = "$bootstrap_site_sha256"; then
    exit 0
fi
test "$actual_site_sha256" = "$expected_site_sha256"
/usr/bin/timeout 15s /usr/sbin/nginx -t
/usr/bin/timeout 20s /usr/bin/systemctl reload nginx.service
