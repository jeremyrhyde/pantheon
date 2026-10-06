#!/usr/bin/env bash
# Pantheon heartbeat — run every minute on an edge display by
# pantheon-heartbeat.timer. Tells the main Pi this device is alive, how it's
# doing, and whether its kiosk is running. Bash + curl only (no uv). A failed
# send is logged to the journal and otherwise ignored.
#
#   heartbeat.sh           # send to http://$SERVER_IP_ADDRESS:$GATEWAY_PORT
#   heartbeat.sh --print   # print the JSON body instead (tests)
#
# HEARTBEAT_ROOT (tests only) prefixes every /proc and /sys path;
# HEARTBEAT_CPU_SAMPLE_S (default 1) is the gap between the two CPU reads.
#
# Every value is made to satisfy schemas/devices.py Heartbeat before sending:
# the server rejects the whole body on one bad field.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
for f in "$REPO_DIR/.env" "$REPO_DIR/kiosk.env"; do
  if [[ -f "$f" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
done
ROOT="${HEARTBEAT_ROOT:-}"

# num <value> [nonneg]: a JSON number, or null if it isn't one (or, with
# "nonneg", is negative).
num() {
  if [[ "${1:-}" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] && { [[ "${2:-}" != nonneg ]] || [[ "$1" != -* ]]; }; then
    printf '%s' "$1"
  else
    printf 'null'
  fi
}
# clean: drop control bytes JSON can't carry raw (keeping \t \n \r to escape).
clean() { printf '%s' "${1:-}" | tr -d '\000-\010\013\014\016-\037'; }
# str <value>: a JSON string for any input, or null if empty.
str() {
  local s
  s="$(clean "${1:-}")"
  if [[ -z "$s" ]]; then printf 'null'; return; fi
  s="${s//\\/\\\\}"; s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"; s="${s//$'\r'/\\r}"; s="${s//$'\t'/\\t}"
  printf '"%s"' "$s"
}

cpu_times() { awk '/^cpu /{ idle=$5+$6; total=0; for (i=2; i<=NF; i++) total+=$i; print total, idle }' "$ROOT/proc/stat" 2>/dev/null; }
cpu_percent() {  # clamped to 0..100
  local t1 i1 t2 i2
  read -r t1 i1 < <(cpu_times) || return 0
  sleep "${HEARTBEAT_CPU_SAMPLE_S:-1}"
  read -r t2 i2 < <(cpu_times) || return 0
  (( t2 > t1 )) || return 0
  awk -v dt="$((t2 - t1))" -v di="$((i2 - i1))" \
    'BEGIN { p = 100 * (dt - di) / dt; if (p < 0) p = 0; if (p > 100) p = 100; printf "%.1f", p }'
}
mem_mb() {  # prints "used total" in MB
  awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2} END { if (t) printf "%.1f %.1f", (t-a)/1024, t/1024 }' "$ROOT/proc/meminfo" 2>/dev/null
}
temp_c() {  # only within the schema's -40..150
  awk '{ t = $1 / 1000; if (t >= -40 && t <= 150) printf "%.1f", t }' "$ROOT/sys/class/thermal/thermal_zone0/temp" 2>/dev/null
}
uptime_s() { awk '{ print $1 }' "$ROOT/proc/uptime" 2>/dev/null; }
throttled() {  # only a well-formed hex value, else nothing (→ null)
  command -v vcgencmd >/dev/null 2>&1 || return 0
  local v
  v="$(vcgencmd get_throttled 2>/dev/null | sed -n 's/^throttled=//p')"
  if [[ "$v" =~ ^0x[0-9a-fA-F]+$ && ${#v} -le 18 ]]; then printf '%s' "$v"; fi
}
chromium_running() {  # the snap's process is "chrome"; names cap at 15 chars
  if pgrep -x 'chromium|chromium-browse|chrome' >/dev/null 2>&1; then echo true; else echo false; fi
}

read -r mem_used mem_total <<< "$(mem_mb)"
host="$(clean "$(hostname 2>/dev/null)")"
[[ -n "$host" ]] || host="$(clean "$(cat "$ROOT/proc/sys/kernel/hostname" 2>/dev/null)")"
[[ -n "$host" ]] || host="unknown"
kiosk_url="$(bash "$REPO_DIR/web/kiosk/start-kiosk.sh" --print-url 2>/dev/null)"
body=$(printf '{"hostname":%s,"kiosk_url":%s,"chromium_running":%s,"uptime_s":%s,"cpu_percent":%s,"mem_used_mb":%s,"mem_total_mb":%s,"temp_c":%s,"throttled":%s,"agent_version":1}' \
  "$(str "${host:0:64}")" \
  "$(str "${kiosk_url:0:512}")" \
  "$(chromium_running)" \
  "$(num "$(uptime_s)" nonneg)" \
  "$(num "$(cpu_percent)")" \
  "$(num "${mem_used:-}" nonneg)" \
  "$(num "${mem_total:-}" nonneg)" \
  "$(num "$(temp_c)")" \
  "$(str "$(throttled)")")

if [[ "${1:-}" == "--print" ]]; then
  echo "$body"
  exit 0
fi

url="http://${SERVER_IP_ADDRESS:-localhost}:${GATEWAY_PORT:-8000}/api/devices/heartbeat"
if ! curl -fsS -m 5 -H 'Content-Type: application/json' -d "$body" "$url" >/dev/null; then
  echo "heartbeat: could not reach $url" >&2
fi
exit 0
