# Pantheon

The umbrella repo for a set of independent apps — Apollo, Hermes, Hestia and
Pluto — each a git submodule under `modules/`. Pantheon's own server is the
shared skeleton (a FastAPI server with a no-build web UI at `/ui`, run as a
background service on a Mac or Raspberry Pi). How it presents the modules
together is still to be designed.

## Quickstart

```bash
git clone --recurse-submodules https://github.com/jeremyrhyde/pantheon.git
cd pantheon
make setup-all build-all     # Pantheon, then every module
make run                     # Pantheon only: http://localhost:8000/ui/
make test-all
```

Pluto is a private repo, so cloning it over HTTPS needs git credentials. If
`gh` is logged in, `gh auth setup-git` once lets git use them.

Copy `.env.example` to `.env` to override settings (port, log level, paths).

## Modules

| Module | Tracks branch |
|---|---|
| `modules/apollo` | `main` |
| `modules/hermes` | `feat/feed-categories` |
| `modules/hestia` | `main` |
| `modules/pluto`  | `upgrade-to-full-system` |

Each module is its own repo with the same `make setup build run test clean`.
`make <target>` acts on Pantheon only; `make <target>-all` (setup, build,
test, clean) runs it here and then in each module, stopping at the first
failure. To run one module: `make -C modules/hermes run`.

A module change is made and pushed in that module's repo; Pantheon then
records the new commit:

```bash
make modules-update          # move each module to its branch tip
git add modules && git commit -m "chore: bump modules"
make modules-status          # pinned commit, branch, uncommitted changes
```

Every repo shares the same `.gitignore` block (keep it identical) followed
by its own lines, and an `artifacts/` folder for committed assets such as
diagrams and README images.

## Run it in the background

```bash
make service-install     # systemd user unit on Linux/Pi, launchd agent on macOS
make service-status
make service-logs
make service-restart     # after a git pull
make service-uninstall
```

The service runs `main.py` from the repo root, so it uses the same `.env` as
`make run`. On Linux it enables linger so it starts at boot with no login; on
macOS it starts at login.

### Kiosk display (Raspberry Pi)

After `make service-install` on the Pi:

```bash
make kiosk-install              # auto-detect desktop vs headless
make kiosk-install-headless     # Pi OS Lite / Ubuntu Server: minimal X + auto-login
```

Chromium opens fullscreen on `http://localhost:$PORT/ui/`. Set
`SERVER_IP_ADDRESS` (or `PANTHEON_UI_URL`) in `.env` to point the display at a
server elsewhere on the network.

## Layout

```
Makefile              setup / build / run / test / *-all / modules* / service-* / kiosk-*
pyproject.toml        uv-managed deps (uv.lock committed)
config.py             Settings — every knob, read from env / .env
main.py               build_app() + lifespan; `python main.py` serves it
core/                 app framework: api.py now; events, websocket, state later
schemas/              pydantic models
services/             Pantheon's domain logic
tests/                pytest (+ pytest-asyncio, asyncio_mode=auto)
web/                  index.html + app.js (Alpine.js) + style.css (tokens)
web/kiosk/            Chromium kiosk launcher + its systemd unit
deploy/               systemd unit, launchd plist, headless-X boot files
scripts/              install-server.sh, install-kiosk.sh
docs/                 dated specs and plans
artifacts/            committed assets (diagrams, README images)
modules/              apollo, hermes, hestia, pluto (git submodules)
```
