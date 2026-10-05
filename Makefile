# Pantheon
#
# Common workflows wrapped as `make` targets. Run `make help` for the list.
# Most targets shell out to `uv` — `make setup` installs it (and Caddy) when missing.

# Resolve `uv`: prefer one already on PATH, else the location the official
# installer drops it (~/.local/bin) on both Linux and macOS. Override with
# `make UV=/path/to/uv ...`.
UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest

# Host/port for run-dev and the live checks. `make run` and the background
# service read HOST/PORT from config.Settings (the environment / .env) instead.
HOST ?= 0.0.0.0
PORT ?= 8010
PANTHEON_HOST ?= http://localhost:$(PORT)

# Submodules under modules/, in the order the *-all targets visit them.
MODULES := apollo hermes hestia pluto

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo "Pantheon — make targets"
	@echo ""
	@echo "Pipeline (Linux + macOS):"
	@echo "  make setup            Ensure uv and the Caddy gateway are installed"
	@echo "  make caddy            Install Caddy only (apt on Linux)"
	@echo "  make build            Sync deps into .venv and byte-compile sources"
	@echo "  make run              Start the server in the foreground"
	@echo "  -> full bootstrap:    make setup build run"
	@echo ""
	@echo "Modules (git submodules under modules/):"
	@echo "  make setup-all        setup here, fetch the modules, then setup in each"
	@echo "  make build-all        build here, then in each module"
	@echo "  make test-all         test here, then in each module"
	@echo "  make clean-all        clean here, then in each module"
	@echo "  -> full bootstrap:    make setup-all build-all"
	@echo "  make modules          Check out the pinned module commits"
	@echo "  make modules-update   Move each module to its branch tip (commit the bump)"
	@echo "  make modules-status   Pinned commit, branch and dirtiness of each module"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Alias for build"
	@echo "  make lock             Re-lock dependencies (regenerate uv.lock)"
	@echo "  make clean            Remove caches, build artefacts, *.pyc"
	@echo "  make distclean        clean + remove .venv"
	@echo ""
	@echo "Run:"
	@echo "  make run-dev          Start with auto-reload (HOST/PORT overridable)"
	@echo "  make run-all          Whole system in this terminal: modules + Pantheon + gateway"
	@echo "  make run-dev-all      Same, every app with auto-reload (Ctrl-C stops all)"
	@echo "  make open             Open the web UI in a browser"
	@echo "  make health           curl /health on a running server"
	@echo ""
	@echo "Tests:"
	@echo "  make test             Run the pytest suite"
	@echo ""
	@echo "Background service (systemd on Linux/Pi, launchd on macOS):"
	@echo "  make service-install    Install + start the server at boot/login"
	@echo "  make service-uninstall  Stop and remove it"
	@echo "  make service-status     Show whether it is running"
	@echo "  make service-logs       Follow its logs"
	@echo "  make service-restart    Restart it (e.g. after a git pull)"
	@echo ""
	@echo "Kiosk display (Linux/Pi only; install the service first):"
	@echo "  make kiosk-install            Auto-detect desktop vs headless"
	@echo "    MODULE=apollo SERVER=<main-pi-ip>  Edge display showing one module"
	@echo "  make kiosk-install-headless   Force headless (Pi OS Lite / Ubuntu Server)"
	@echo "  make kiosk-uninstall          Remove the kiosk unit"
	@echo ""
	@echo "Full system on the main Pi (Linux only):"
	@echo "  make service-install-all     Modules + Pantheon + Caddy gateway under pantheon.target"
	@echo "  make service-uninstall-all   Stop and remove all of it"
	@echo "  make service-status-all      One line per unit, with /health"
	@echo "  make service-restart-all     Restart pantheon.target (every unit)"
	@echo "  make gateway-config          Re-render build/Caddyfile and reload the gateway"

# ---------------------------------------------------------------------------
# Setup / build
# ---------------------------------------------------------------------------

# setup — ensure the uv toolchain exists. Idempotent; uses the official
# installer only when uv is missing, preferring curl and falling back to wget.
.PHONY: setup
setup: modules.yaml caddy
	@if [ -x "$(UV)" ] || command -v uv >/dev/null 2>&1; then \
		echo "uv already present: $$($(UV) --version 2>/dev/null || echo $(UV))"; \
	else \
		echo "Installing uv (Linux/macOS)..."; \
		if command -v curl >/dev/null 2>&1; then \
			curl -LsSf https://astral.sh/uv/install.sh | sh; \
		elif command -v wget >/dev/null 2>&1; then \
			wget -qO- https://astral.sh/uv/install.sh | sh; \
		else \
			echo "ERROR: need curl or wget to install uv. See https://docs.astral.sh/uv/"; \
			exit 1; \
		fi; \
		echo "uv installed to $(HOME)/.local/bin — ensure it is on your PATH."; \
	fi

# caddy — the gateway binary run-all and service-install-all need. Linux: apt
# installs it if missing and its system-wide caddy.service is disabled (see
# scripts/install-caddy.sh). macOS: prints how to install it.
.PHONY: caddy
caddy:
	./scripts/install-caddy.sh

# The per-host module registry, seeded from the committed example.
modules.yaml:
	cp modules.yaml.example modules.yaml

# build — sync locked deps into .venv, then byte-compile the sources so a
# syntax error fails the build on any platform.
.PHONY: build
build:
	$(UV) sync
	$(UV) run python -m compileall -q core services schemas main.py config.py
	@echo "Build complete."

.PHONY: install
install: build

.PHONY: lock
lock:
	$(UV) lock

.PHONY: clean
# Skips modules/ — each module cleans itself (see clean-all).
clean:
	@find . -path ./modules -prune -o -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./modules -prune -o -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./modules -prune -o -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./modules -prune -o -type f -name '*.pyc' -exec rm -f {} + 2>/dev/null || true
	@echo "Cleaned caches and build artefacts."

.PHONY: distclean
distclean: clean
	@rm -rf .venv
	@echo "Removed .venv. Run 'make build' to rebuild."

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: run-dev
run-dev:
	$(UV) run uvicorn main:app --reload --host $(HOST) --port $(PORT)

# The whole system in this terminal (local testing): enabled modules +
# Pantheon + the Caddy gateway, tagged logs, Ctrl-C stops all. Needs caddy.
.PHONY: run-all
run-all: modules.yaml
	./scripts/run-all.sh

.PHONY: run-dev-all
run-dev-all: modules.yaml
	./scripts/run-all.sh --dev

.PHONY: open
open:
	@python3 -c "import webbrowser; webbrowser.open('$(PANTHEON_HOST)/')"

.PHONY: health
health:
	@curl -sS $(PANTHEON_HOST)/health && echo ""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

.PHONY: test
test:
	$(PYTEST) -v

# ---------------------------------------------------------------------------
# Modules — each is its own repo with its own Makefile. The *-all targets run
# the Pantheon target first, then `make -C modules/<m> <target>` per module,
# stopping at the first failure.
# ---------------------------------------------------------------------------

.PHONY: modules
modules:
	git submodule update --init --recursive

.PHONY: modules-update
modules-update:
	git submodule update --init --remote --recursive
	@echo "Modules moved to their branch tips. Review, then commit the new pointers."

.PHONY: modules-status
modules-status:
	@git submodule status
	@for m in $(MODULES); do \
		echo "  $$m: $$(git -C modules/$$m branch --show-current 2>/dev/null || echo '?'), $$(git -C modules/$$m status --porcelain 2>/dev/null | wc -l | tr -d ' ') changed file(s)"; \
	done

# run_in_modules <target> — run <target> in every module, in MODULES order.
define run_in_modules
	@for m in $(MODULES); do \
		echo ""; \
		echo "==> $$m: make $(1)"; \
		$(MAKE) -C modules/$$m $(1) || { echo "FAILED: $$m (make $(1))"; exit 1; }; \
	done
endef

.PHONY: setup-all
setup-all: setup modules
	$(call run_in_modules,setup)

.PHONY: build-all
build-all: build
	$(call run_in_modules,build)

.PHONY: test-all
test-all: test
	$(call run_in_modules,test)

.PHONY: clean-all
clean-all: clean
	$(call run_in_modules,clean)

# ---------------------------------------------------------------------------
# Background service — see scripts/install-server.sh
# ---------------------------------------------------------------------------

.PHONY: service-install
service-install:
	./scripts/install-server.sh

.PHONY: service-uninstall
service-uninstall:
	./scripts/install-server.sh --uninstall

.PHONY: service-status
service-status:
	./scripts/install-server.sh --status

.PHONY: service-logs
service-logs:
	./scripts/install-server.sh --logs

.PHONY: service-restart
service-restart:
	./scripts/install-server.sh --restart

# ---------------------------------------------------------------------------
# Full system — gateway + Pantheon + every enabled module (see
# scripts/install-all.sh). Linux/Pi only.
# ---------------------------------------------------------------------------

.PHONY: service-install-all
service-install-all: modules.yaml
	./scripts/install-all.sh

.PHONY: service-uninstall-all
service-uninstall-all:
	./scripts/install-all.sh --uninstall

.PHONY: service-status-all
service-status-all:
	./scripts/install-all.sh --status

.PHONY: service-restart-all
service-restart-all:
	systemctl --user restart pantheon.target

# Re-render the Caddyfile after editing modules.yaml routes/ports and reload
# the running gateway. Enabling/disabling a module needs service-install-all.
.PHONY: gateway-config
gateway-config: modules.yaml
	@mkdir -p build
	$(PYTHON) -m services.render caddyfile > build/Caddyfile.tmp
	@mv build/Caddyfile.tmp build/Caddyfile
	@echo "Wrote build/Caddyfile"
	@if systemctl --user is-active --quiet pantheon-gateway.service 2>/dev/null; then \
		systemctl --user reload pantheon-gateway.service && echo "Reloaded the gateway."; \
	fi

# ---------------------------------------------------------------------------
# Kiosk — see scripts/install-kiosk.sh (Linux/Pi only)
# ---------------------------------------------------------------------------

# MODULE=<name> opens one module; SERVER=<ip> points at the main Pi (edge display).
KIOSK_ARGS = $(if $(MODULE),--module $(MODULE)) $(if $(SERVER),--server $(SERVER))

.PHONY: kiosk-install
kiosk-install:
	./scripts/install-kiosk.sh $(KIOSK_ARGS)

.PHONY: kiosk-install-headless
kiosk-install-headless:
	./scripts/install-kiosk.sh --headless $(KIOSK_ARGS)

.PHONY: kiosk-uninstall
kiosk-uninstall:
	./scripts/install-kiosk.sh --uninstall
