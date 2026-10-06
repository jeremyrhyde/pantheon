#!/usr/bin/env bash
# Pantheon kiosk launcher — Chromium fullscreen on the gateway (or one module).
#
# Run via the systemd user service in this directory, or invoke directly
# from an X session for testing.
set -euo pipefail

# Load .env, then kiosk.env (written by scripts/install-kiosk.sh: which
# module this display shows and which server it points at). Sourced in-script
# rather than via systemd's EnvironmentFile so it works on every launch path:
# the systemd kiosk unit, the headless xinitrc, and running this by hand.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
for f in "$REPO_DIR/.env" "$REPO_DIR/kiosk.env"; do
  if [[ -f "$f" ]]; then
    set -a            # export everything we source
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
done

# Resolve the URL Chromium opens:
#   1. PANTHEON_UI_URL — explicit full override (wins if set).
#   2. http://<SERVER_IP_ADDRESS or localhost>:<GATEWAY_PORT>/<KIOSK_MODULE>/
#      — the gateway, optionally a single module (edge displays).
if [[ -n "${PANTHEON_UI_URL:-}" ]]; then
  UI_URL="${PANTHEON_UI_URL}"
else
  UI_URL="http://${SERVER_IP_ADDRESS:-localhost}:${GATEWAY_PORT:-8000}/${KIOSK_MODULE:+${KIOSK_MODULE}/}"
fi

# Flag notes (RAM-constrained Pi 4 kiosk):
#  - We intentionally do NOT pass --disable-gpu: on the Pi it forces slow
#    software rendering, hurting the "snappier UI" goal. Let Chromium use
#    the VideoCore GPU.
#  - --disk-cache-size bounds Chromium's on-disk cache (bytes); it does not
#    cap RAM directly but stops unbounded cache growth on a long-lived kiosk.
#  - --disable-features=TranslateUI and --disable-session-crashed-bubble
#    suppress popups that would otherwise overlay the kiosk UI after a
#    crash/restart. These are the flags the documented Pi-kiosk reference
#    implementations (FullPageOS, reelyactive) converge on.
CHROMIUM_FLAGS=(
  --kiosk
  --noerrdialogs
  --disable-infobars
  --disable-restore-session-state
  --disable-session-crashed-bubble
  --disable-pinch
  --disable-features=TranslateUI
  --disable-component-update
  --overscroll-history-navigation=0
  --check-for-update-interval=31536000
  --autoplay-policy=no-user-gesture-required
  --disk-cache-size=52428800
)

# Theme: Pantheon and its modules are dark-first, but a bare kiosk has no
# desktop to say "prefer dark", so Chromium reports light and modules that
# follow prefers-color-scheme (Apollo; Hestia on Auto) come up light. Default
# to dark; KIOSK_THEME=light in kiosk.env or .env opts out.
case "${KIOSK_THEME:-dark}" in
  dark)  CHROMIUM_FLAGS+=(--force-dark-mode --blink-settings=preferredColorScheme=0) ;;
  light) ;;
  *)     echo "start-kiosk: unknown KIOSK_THEME '${KIOSK_THEME}', using dark" >&2
         CHROMIUM_FLAGS+=(--force-dark-mode --blink-settings=preferredColorScheme=0) ;;
esac

case "${1:-}" in
  --print-url)   echo "${UI_URL}"; exit 0 ;;
  --print-flags) printf '%s\n' "${CHROMIUM_FLAGS[@]}"; exit 0 ;;
esac

# Disable screen blanking / DPMS so the touchscreen stays on indefinitely.
xset s off
xset -dpms
xset s noblank

# Hide the cursor after 0.5s of idle.
unclutter -idle 0.5 -root &

# Pick whichever Chromium binary is installed (Pi OS ships chromium-browser;
# Ubuntu provides chromium).
CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || true)"
if [[ -z "${CHROMIUM_BIN}" ]]; then
  echo "start-kiosk: no chromium binary found (apt install chromium-browser)" >&2
  exit 1
fi

echo "start-kiosk: opening ${UI_URL}" >&2

exec "${CHROMIUM_BIN}" "${CHROMIUM_FLAGS[@]}" "${UI_URL}"
