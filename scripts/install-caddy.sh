#!/usr/bin/env bash
# Make sure the Caddy gateway binary is installed (`make caddy`; `make setup`
# runs it). Linux: apt-installs caddy when missing and disables the
# system-wide caddy.service apt enables, since Pantheon runs its own gateway
# (run-all.sh or pantheon-gateway.service). macOS: prints how to install it
# and exits 0, so `make setup` still works for development.

set -euo pipefail
source "$(dirname "$0")/_common.sh"

if ensure_caddy; then
  echo "caddy present: $("$CADDY_BIN" version)"
elif [[ "$OS" == "Linux" ]]; then
  exit 1
fi
