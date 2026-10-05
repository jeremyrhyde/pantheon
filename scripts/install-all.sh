#!/usr/bin/env bash
# Install the full Pantheon system on the main Pi: every enabled module's own
# service, Pantheon's app, the Caddy gateway, and pantheon.target tying them
# together. Module list: the enabled entries in modules.yaml.
#
# Usage (or the matching `make service-*-all` targets):
#   ./scripts/install-all.sh              # install + start everything
#   ./scripts/install-all.sh --uninstall  # stop + remove everything
#   ./scripts/install-all.sh --status     # one line per unit + its /health
#
# Linux only. Idempotent — running it twice is safe. After enabling or
# disabling a module in modules.yaml, run it again.

set -euo pipefail

ACTION="install"
case "${1:-}" in
  "")          ;;
  --uninstall) ACTION="uninstall" ;;
  --status)    ACTION="status" ;;
  -h|--help)   sed -n '2,14p' "$0" | sed 's/^# \?//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

source "$(dirname "$0")/_common.sh"
require_uv

if [[ "$OS" != "Linux" ]]; then
  echo "install-all is Linux/Raspberry Pi only (systemd user units)." >&2
  exit 1
fi

cd "$PANTHEON_HOME"
[[ -f modules.yaml ]] || cp modules.yaml.example modules.yaml

render() { "$UV_BIN" run --quiet python -m services.render "$1"; }

TARGET="$SYSTEMD_USER_DIR/pantheon.target"
GATEWAY_UNIT="$SYSTEMD_USER_DIR/$GATEWAY_SERVICE_NAME"
MODULES="$(render modules)"   # "<name> <port>" per enabled module

status() {
  echo "Pantheon units:"
  while read -r unit port; do
    if [[ -z "$unit" ]]; then continue; fi
    local state health
    state="$(systemctl --user is-active "$unit" 2>/dev/null || true)"
    if curl -fsS -m 2 "http://localhost:$port/health" >/dev/null 2>&1; then
      health="healthy"
    else
      health="no /health on :$port"
    fi
    printf "  %-28s %-10s %s\n" "$unit" "$state" "$health"
  done <<< "$(render units)"
}

install() {
  echo "[1/5] module services..."
  while read -r name port; do
    if [[ -z "$name" ]]; then continue; fi
    echo "  -> $name (:$port)"
    make -C "modules/$name" service-install
  done <<< "$MODULES"

  echo "[2/5] Pantheon app..."
  ./scripts/install-server.sh

  echo "[3/5] Caddy gateway..."
  command -v caddy >/dev/null 2>&1 || ensure_apt_packages caddy
  # apt's caddy enables a system-wide caddy.service on :80; Pantheon runs its
  # own Caddy as a user unit instead.
  sudo systemctl disable --now caddy.service 2>/dev/null || true
  CADDY_BIN="$(command -v caddy)"
  mkdir -p build
  render caddyfile > build/Caddyfile
  "$CADDY_BIN" validate --config build/Caddyfile --adapter caddyfile
  render_unit deploy/pantheon-gateway.service "$GATEWAY_UNIT"

  echo "[4/5] pantheon.target + drop-ins..."
  rm -f "$SYSTEMD_USER_DIR"/*.service.d/pantheon.conf   # drop stale ones (disabled modules)
  render target > "$TARGET"
  while read -r name port; do
    if [[ -z "$name" ]]; then continue; fi
    mkdir -p "$SYSTEMD_USER_DIR/$name.service.d"
    render dropin > "$SYSTEMD_USER_DIR/$name.service.d/pantheon.conf"
  done <<< "$MODULES"

  echo "[5/5] starting pantheon.target..."
  systemctl --user daemon-reload
  systemctl --user enable "$GATEWAY_SERVICE_NAME" pantheon.target
  systemctl --user restart pantheon.target
  sleep 2
  status
  echo
  echo "Gateway: http://$(hostname -I 2>/dev/null | awk '{print $1}'):$(grep -oP '^:\K[0-9]+' build/Caddyfile)/"
}

uninstall() {
  systemctl --user disable --now pantheon.target "$GATEWAY_SERVICE_NAME" 2>/dev/null || true
  rm -f "$TARGET" "$GATEWAY_UNIT" "$SYSTEMD_USER_DIR"/*.service.d/pantheon.conf
  rmdir "$SYSTEMD_USER_DIR"/*.service.d 2>/dev/null || true
  ./scripts/install-server.sh --uninstall
  while read -r name port; do
    if [[ -z "$name" ]]; then continue; fi
    make -C "modules/$name" service-uninstall || true
  done <<< "$MODULES"
  systemctl --user daemon-reload || true
  echo "Removed. Caddy (apt package) and linger left in place."
}

case "$ACTION" in
  install)   install ;;
  uninstall) uninstall ;;
  status)    status ;;
esac
