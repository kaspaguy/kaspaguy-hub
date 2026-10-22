#!/bin/bash
# Kaspaguy uptime check, run every 5 min from cron on thanaaya-mail. Alerts on Telegram after 2 consecutive failures, and once on recovery.
set -a; . /etc/dmarc-check.env; set +a
STATE=/var/lib/kaspaguy-uptime; mkdir -p "$STATE"
BASE=https://kaspaguy.com
fail=""
code=$(curl -s -m 15 -o "$STATE/home.html" -w '%{http_code}' "$BASE/")
[ "$code" = 200 ] || fail="$fail home=$code"
grep -qi 'kaspaguy' "$STATE/home.html" 2>/dev/null || fail="$fail home-content"
for p in /sitemap.xml /robots.txt; do
  c=$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$BASE$p"); [ "$c" = 200 ] || fail="$fail $p=$c"
done
c=$(curl -s -m 15 -o /dev/null -w '%{http_code}' "$BASE/no-such-page-uptime"); [ "$c" = 404 ] || fail="$fail 404page=$c"
end=$(echo | openssl s_client -connect kaspaguy.com:443 -servername kaspaguy.com 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$end" ]; then d=$(( ($(date -d "$end" +%s) - $(date +%s)) / 86400 )); [ "$d" -ge 7 ] || fail="$fail cert-expires-in-${d}d"; else fail="$fail cert-unreadable"; fi
send() { curl -s -m 20 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$1"; }
n=$(cat "$STATE/fails" 2>/dev/null || echo 0)
if [ -n "$fail" ]; then
  n=$((n+1)); echo $n > "$STATE/fails"
  [ "$n" = 2 ] && { send "kaspaguy.com DOWN:$fail"; touch "$STATE/alerted"; }
else
  [ -e "$STATE/alerted" ] && { send "kaspaguy.com recovered"; rm -f "$STATE/alerted"; }
  echo 0 > "$STATE/fails"
fi
