#!/usr/bin/env bash
# Shared setup for the install scripts. Sourced, not executed:
#   source "$(dirname "$0")/_common.sh"
#
# Resolves paths, locates `uv` (systemd and launchd run with a minimal PATH,
# so the absolute path is baked into the unit), and defines render_unit /
# ensure_apt_packages / detect_mode. Adapted from hestia/scripts/_pi-common.sh.

PANTHEON_HOME="$(cd "$(dirname "${BASH_SOURCE[1]}")/.." && pwd)"
USER_NAME="$(id -un)"
USER_HOME="$HOME"
OS="$(uname -s)"                       # Linux | Darwin
SYSTEMD_USER_DIR="$USER_HOME/.config/systemd/user"
LAUNCHD_DIR="$USER_HOME/Library/LaunchAgents"
LOG_DIR="$USER_HOME/Library/Logs/pantheon"

SERVICE_NAME="pantheon.service"
KIOSK_SERVICE_NAME="pantheon-kiosk.service"
LAUNCHD_LABEL="com.pantheon.server"

GATEWAY_SERVICE_NAME="pantheon-gateway.service"

UV_BIN=""
require_uv() {
  # require_uv — locate uv or exit. Only scripts that run uv call this, so the
  # kiosk installer works on an edge Pi that has no uv.
  UV_BIN="$(command -v uv || true)"
  if [[ -z "$UV_BIN" ]]; then
    for cand in "$USER_HOME/.local/bin/uv" "$USER_HOME/.cargo/bin/uv"; do
      [[ -x "$cand" ]] && UV_BIN="$cand" && break
    done
  fi
  if [[ -z "$UV_BIN" ]]; then
    echo "ERROR: 'uv' not found. Run 'make setup' first." >&2
    exit 1
  fi
}

render_unit() {
  # render_unit <src> <dest> — copy with @PANTHEON_HOME@/@UV_BIN@/@CADDY_BIN@/@LOG_DIR@ filled in.
  sed \
    -e "s|@PANTHEON_HOME@|$PANTHEON_HOME|g" \
    -e "s|@UV_BIN@|${UV_BIN:-}|g" \
    -e "s|@CADDY_BIN@|${CADDY_BIN:-}|g" \
    -e "s|@LOG_DIR@|$LOG_DIR|g" \
    "$1" > "$2"
}

ensure_apt_packages() {
  # ensure_apt_packages [--no-recommends] <pkg>... — install only what's missing.
  local apt_opts=()
  if [[ "${1:-}" == "--no-recommends" ]]; then
    apt_opts+=(--no-install-recommends); shift
  fi
  local missing=()
  for p in "$@"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "  installing apt packages: ${missing[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${apt_opts[@]}" "${missing[@]}"
  fi
}

detect_mode() {
  # Echoes "desktop" or "headless", honoring a caller-set $MODE other than "auto".
  if [[ "${MODE:-auto}" != "auto" ]]; then echo "$MODE"; return; fi
  if systemctl get-default 2>/dev/null | grep -q graphical || [[ -n "${DISPLAY:-}" ]]; then
    echo "desktop"
  else
    echo "headless"
  fi
}
