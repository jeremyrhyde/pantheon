#!/usr/bin/env bash
# Install the Pantheon *kiosk* (fullscreen Chromium display) on a Raspberry Pi.
#
# Installs Chromium + unclutter, the pantheon-kiosk.service user unit, and —
# on a headless base (Pi OS Lite / Ubuntu Server) — a minimal X stack plus
# tty1 auto-login so the kiosk launches at boot. On the main Pi, run
# install-all.sh (or install-server.sh) first; the kiosk then points Chromium
# at the local gateway. Edge displays use --server <main-pi> and need nothing
# else installed.
#
# RECOMMENDED BASE OS: Raspberry Pi OS Lite (headless, no desktop). It ships
# no display system, so --headless mode adds only a bare X stack + Chromium
# — far lighter on a 2-4GB Pi 4 than a full desktop. Ubuntu Server also
# works via the same --headless path.
#
# Usage:
#   ./scripts/install-kiosk.sh             # auto-detect mode
#   ./scripts/install-kiosk.sh --desktop   # force desktop-session mode
#   ./scripts/install-kiosk.sh --headless  # force headless (Pi OS Lite / Ubuntu Server)
#   ./scripts/install-kiosk.sh --uninstall # remove the kiosk unit
#   ./scripts/install-kiosk.sh --module apollo --server 192.168.1.50
#                                          # edge display: one module, served by the main Pi
#
# Idempotent — running it twice is safe.

set -euo pipefail

# --- args ------------------------------------------------------------------

MODE="auto"
ACTION="install"
KIOSK_MODULE=""
KIOSK_SERVER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop)   MODE="desktop"; shift ;;
    --headless)  MODE="headless"; shift ;;
    --module)
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "--module needs a name" >&2; exit 2; fi
      KIOSK_MODULE="$2"; shift 2 ;;
    --server)
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "--server needs an IP or hostname" >&2; exit 2; fi
      KIOSK_SERVER="$2"; shift 2 ;;
    --uninstall) ACTION="uninstall"; shift ;;
    -h|--help)   sed -n '3,21p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -n "$KIOSK_MODULE" && ! "$KIOSK_MODULE" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "--module must be a module name like 'apollo'" >&2
  exit 2
fi

if [[ -n "$KIOSK_SERVER" && ! "$KIOSK_SERVER" =~ ^[A-Za-z0-9.:-]+$ ]]; then
  echo "--server must be an IP or hostname (letters, digits, '.', ':', '-')" >&2
  exit 2
fi

source "$(dirname "$0")/_common.sh"

if [[ "$OS" != "Linux" ]]; then
  echo "The kiosk is Linux/Raspberry Pi only (systemd + X + Chromium)." >&2
  echo "On macOS, just open http://localhost:8000/ in a browser." >&2
  exit 1
fi

echo "Pantheon kiosk install"
echo "  PANTHEON_HOME = $PANTHEON_HOME"
echo "  USER        = $USER_NAME"

# --- uninstall -------------------------------------------------------------

if [[ "$ACTION" == "uninstall" ]]; then
  echo "Uninstalling Pantheon kiosk unit..."
  systemctl --user disable --now pantheon-kiosk.service 2>/dev/null || true
  rm -f "$SYSTEMD_USER_DIR/pantheon-kiosk.service"
  rm -f "$PANTHEON_HOME/kiosk.env"
  systemctl --user daemon-reload || true
  echo "Done. X stack / tty1 auto-login / .bash_profile changes left in place"
  echo "— remove manually if desired."
  exit 0
fi

# --- install ---------------------------------------------------------------

mkdir -p "$SYSTEMD_USER_DIR"

# Warn (don't fail) if the server unit isn't installed — the kiosk points
# Chromium at the local server, so it's near-useless without it.
if [[ -z "$KIOSK_SERVER" ]]; then
  if [[ ! -f "$SYSTEMD_USER_DIR/pantheon.service" ]]; then
    echo "  NOTE: pantheon.service not found — run ./scripts/install-server.sh"
    echo "        first, or the kiosk will load a server that isn't running."
  fi
fi

# 1. Install pantheon-kiosk.service.
echo
echo "[1/4] writing pantheon-kiosk.service..."
render_unit "$PANTHEON_HOME/web/kiosk/pantheon-kiosk.service" \
            "$SYSTEMD_USER_DIR/pantheon-kiosk.service"
chmod +x "$PANTHEON_HOME/web/kiosk/start-kiosk.sh"

# What this display opens; start-kiosk.sh sources it after .env.
{
  echo "# Written by scripts/install-kiosk.sh — re-run it to change what this display opens."
  if [[ -n "$KIOSK_MODULE" ]]; then echo "KIOSK_MODULE=$KIOSK_MODULE"; fi
  if [[ -n "$KIOSK_SERVER" ]]; then echo "SERVER_IP_ADDRESS=$KIOSK_SERVER"; fi
} > "$PANTHEON_HOME/kiosk.env"
echo "  kiosk opens: $(bash "$PANTHEON_HOME/web/kiosk/start-kiosk.sh" --print-url)"

# 2. Install kiosk dependencies (chromium + unclutter, plus X stack if headless).
echo
echo "[2/4] installing kiosk dependencies..."
KIOSK_PKGS=(unclutter)
# Chromium package name varies: Pi OS Bullseye uses `chromium-browser`,
# while Bookworm/Trixie-based Pi OS and Ubuntu provide `chromium`. Only add
# a package if no chromium binary is already present, and pick whichever
# name apt can actually resolve a candidate for (avoids the
# "package chromium-browser has no installation candidate" failure).
if ! command -v chromium-browser >/dev/null 2>&1 \
     && ! command -v chromium >/dev/null 2>&1; then
  chromium_pkg=""
  for cand in chromium-browser chromium; do
    if apt-cache policy "$cand" 2>/dev/null \
         | grep -q 'Candidate: [^(]'; then
      chromium_pkg="$cand"
      break
    fi
  done
  if [[ -z "$chromium_pkg" ]]; then
    echo "  WARNING: no chromium package candidate found (tried" \
         "chromium-browser, chromium). Run 'sudo apt-get update' and" \
         "check 'apt-cache policy chromium'." >&2
  else
    echo "  using chromium package: $chromium_pkg"
    KIOSK_PKGS+=("$chromium_pkg")
  fi
fi
ensure_apt_packages "${KIOSK_PKGS[@]}"

resolved_mode="$(detect_mode)"
echo "  detected mode: $resolved_mode"
if [[ "$resolved_mode" == "headless" ]]; then
  echo "  installing minimal X stack (xserver-xorg, matchbox-window-manager, xinit)..."
  # --no-recommends keeps this a bare display stack on Pi OS Lite — no
  # desktop bloat. matchbox-window-manager is a tiny, kiosk-oriented WM
  # (smaller than openbox) that reliably gives Chromium a fullscreen
  # surface to attach to.
  #
  # xserver-xorg-legacy is REQUIRED for a non-root user to start X via
  # startx. Without it, Xorg dies with "parse_vt_settings: Cannot open
  # /dev/tty0 (Permission denied)" and the autologin->startx loop fails
  # over and over (getty hits its restart limit; the screen flickers and
  # shows a black console with a cursor). This is the #1 headless-kiosk
  # gotcha on Debian/Ubuntu.
  ensure_apt_packages --no-recommends \
    xserver-xorg xserver-xorg-legacy xinit x11-xserver-utils \
    matchbox-window-manager
  render_unit "$PANTHEON_HOME/deploy/xinitrc.kiosk" "$USER_HOME/.xinitrc"
  chmod +x "$USER_HOME/.xinitrc"

  # Allow any logged-in user to start the X server from the console.
  # Pairs with xserver-xorg-legacy above. needs_root_rights=yes lets Xorg
  # open /dev/tty0 on the Pi's KMS/modeset driver.
  echo "  configuring Xwrapper to allow non-root X (sudo required)..."
  sudo tee /etc/X11/Xwrapper.config >/dev/null <<'EOF'
# Managed by scripts/install-kiosk.sh — allow the kiosk user to
# start X from tty1 without root.
allowed_users=anybody
needs_root_rights=yes
EOF

  # The kiosk user needs these groups to open the console (tty), the GPU
  # (video/render), and input devices (input) under the bare X stack.
  echo "  adding $USER_NAME to tty,video,input,render groups..."
  sudo usermod -aG tty,video,input,render "$USER_NAME" || true

  # Append the startx-on-tty1 hook to ~/.bash_profile if not already there.
  BPROFILE="$USER_HOME/.bash_profile"
  touch "$BPROFILE"
  if ! grep -q 'exec startx -- -nocursor' "$BPROFILE"; then
    echo "" >> "$BPROFILE"
    cat "$PANTHEON_HOME/deploy/bash_profile.kiosk" >> "$BPROFILE"
    echo "  appended startx hook to $BPROFILE"
  fi

  # Auto-login on tty1 so the bash_profile path runs at boot.
  GETTY_DIR="/etc/systemd/system/getty@tty1.service.d"
  GETTY_FILE="$GETTY_DIR/override.conf"
  if [[ ! -f "$GETTY_FILE" ]]; then
    echo "  enabling tty1 auto-login (sudo required)..."
    sudo mkdir -p "$GETTY_DIR"
    sudo tee "$GETTY_FILE" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\u' --noclear --autologin $USER_NAME %I \$TERM
EOF
    sudo systemctl daemon-reload
  fi
fi

# 3. Reload + enable.
echo
echo "[3/4] enabling pantheon-kiosk.service..."
systemctl --user daemon-reload
systemctl --user enable pantheon-kiosk.service || true

# 4. Status
echo
echo "[4/4] status"
echo
systemctl --user status pantheon-kiosk.service --no-pager -l || true

echo
echo "Kiosk install complete."
if [[ "$resolved_mode" == "headless" ]]; then
  echo
  echo "  HEADLESS MODE: reboot to see the kiosk start on the attached display."
  echo "  After reboot, the Pi will auto-login on tty1 and launch X + Chromium."
else
  echo
  echo "  DESKTOP MODE: log out and log back in (or reboot) to start the kiosk."
fi
