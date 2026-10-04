#!/usr/bin/env bash
# Pantheon kiosk launcher — Chromium fullscreen pointed at the local UI.
#
# Run via the systemd user service in this directory, or invoke directly
# from an X session for testing.
set -euo pipefail

# Load .env from the repo root (two levels up: web/kiosk/ -> repo) if present,
# so SERVER_IP_ADDRESS / PANTHEON_UI_URL can be set there. We do this in-script
# (rather than relying on systemd's EnvironmentFile) so it works across every
# launch path: the systemd kiosk unit, the headless xinitrc, and running this
# script by hand for testing.
ENV_FILE="$(cd "$(dirname "$0")/../.." && pwd)/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a            # export everything we source
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

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

# Resolve the URL Chromium opens, in priority order:
#   1. PANTHEON_UI_URL — explicit full override (wins if set).
#   2. SERVER_IP_ADDRESS — point the kiosk at a server on the network
#      (e.g. a central Pi running the FastAPI app); we build the standard
#      http://<ip>:${PORT}/ui/ URL around it.
#   3. localhost — this Pi runs its own server (the default).
if [[ -n "${PANTHEON_UI_URL:-}" ]]; then
  UI_URL="${PANTHEON_UI_URL}"
elif [[ -n "${SERVER_IP_ADDRESS:-}" ]]; then
  UI_URL="http://${SERVER_IP_ADDRESS}:${PORT:-8000}/ui/"
else
  UI_URL="http://localhost:${PORT:-8000}/ui/"
fi
echo "start-kiosk: opening ${UI_URL}" >&2

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
exec "${CHROMIUM_BIN}" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-restore-session-state \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --disable-features=TranslateUI \
  --disable-component-update \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --disk-cache-size=52428800 \
  "${UI_URL}"
