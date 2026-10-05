#!/usr/bin/env bash
# Run the whole system in this terminal: every enabled module (modules.yaml),
# Pantheon's app and the Caddy gateway, each log line tagged with its source.
# Ctrl-C stops everything. For local testing — on the Pi, use
# `make service-install-all` (systemd) instead.
#
# Usage (or `make run-all` / `make run-dev-all`):
#   ./scripts/run-all.sh          # each app's `make run`
#   ./scripts/run-all.sh --dev    # each app's `make run-dev` (auto-reload)
#
# Needs `caddy` on PATH and the gateway port (8000) free.

set -euo pipefail

VERB="run"
case "${1:-}" in
  "")        ;;
  --dev)     VERB="run-dev" ;;
  -h|--help) sed -n '2,11p' "$0" | sed 's/^# \?//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

source "$(dirname "$0")/_common.sh"
require_uv
cd "$PANTHEON_HOME"

CADDY_BIN="$(command -v caddy || true)"
if [[ -z "$CADDY_BIN" ]]; then
  echo "caddy not found on PATH — run 'make caddy' (apt on Linux)," >&2
  echo "or put a binary from https://caddyserver.com/download in ~/.local/bin." >&2
  exit 1
fi
if systemctl --user is-active --quiet "$GATEWAY_SERVICE_NAME" 2>/dev/null; then
  echo "$GATEWAY_SERVICE_NAME is running — stop the installed system first:" >&2
  echo "  systemctl --user stop pantheon.target" >&2
  exit 1
fi

[[ -f modules.yaml ]] || cp modules.yaml.example modules.yaml
make --no-print-directory gateway-config >/dev/null
MODULES="$("$UV_BIN" run --quiet python -m services.render modules)"
mapfile -t MODULE_ROWS <<< "$MODULES"
GATEWAY_PORT="$(grep -oP '^:\K[0-9]+' build/Caddyfile)"

# tag <name> <command...> — run in the background, prefixing every output line.
tag() {
  local name="$1"; shift
  "$@" </dev/null 2>&1 | sed -u "s/^/[$(printf '%-8s' "$name")] /" &
}

# One Ctrl-C (or any exit) stops the whole process group.
trap 'trap - INT TERM EXIT; kill 0 2>/dev/null' INT TERM EXIT

for row in "${MODULE_ROWS[@]}"; do
  [[ -n "$row" ]] || continue
  read -r name port <<< "$row"
  echo "starting $name (:$port)"
  tag "$name" make --no-print-directory -C "modules/$name" "$VERB"
done
echo "starting pantheon (:$(sed -n 's/^PORT ?= //p' Makefile))"
tag pantheon make --no-print-directory "$VERB"
echo "starting gateway (:$GATEWAY_PORT)"
tag gateway "$CADDY_BIN" run --config build/Caddyfile --adapter caddyfile

echo
echo "Open http://localhost:$GATEWAY_PORT/ — Ctrl-C stops everything."
echo
wait
