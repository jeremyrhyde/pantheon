# Pantheon

Pantheon is a collection of independent home apps — **modules** — run
together on a Raspberry Pi behind one address. Each module (a workout and
self-care routine, a news feed, home automation, a team of financial
analysts) is its own repo and installs and runs **entirely on its own**.
Pantheon adds three things on top, and nothing else:

- **One address.** A Caddy gateway on the main Pi serves every module at
  `http://<main-pi>:8000/<module>/` and Pantheon's home screen at `/`.
- **One switch.** Every service joins `pantheon.target`, so the whole system
  starts, stops and restarts together — while each module still runs,
  fails and restarts on its own.
- **One home screen.** Pantheon's own app lists the modules and their
  health. (A placeholder for now; the unified UI is the next design.)

Pantheon never imports module code. It talks to modules only over HTTP.

## How Pantheon talks to its modules

```
 phone / laptop ─┐
 edge kiosk(s)  ─┤                       ┌─ /         → Pantheon app :8010
 main Pi kiosk  ─┼─▶ main Pi :8000 Caddy ┼─ /apollo/  → Apollo :8001
                 │                       ├─ /hermes/  → Hermes :8002
                 │                       ├─ /hestia/  → Hestia :8003
                 │                       └─ /pluto/   → Pluto  :8004 (disabled: 503)
```

- **Routing.** The gateway strips the prefix: `/hestia/api/devices/` reaches
  Hestia as `/api/devices/`, exactly what it serves standalone. Every
  module's UI uses relative URLs, so it can't tell the difference.
- **Health.** Each module answers `GET /health`. Pantheon probes each enabled
  module on `localhost` and reports it in `GET /api/modules/` (which the home
  screen polls); `make service-status-all` prints the same per unit.
- **Lifecycle.** Each module keeps its own systemd user unit
  (`apollo.service`, …). Pantheon's installer adds a `PartOf=pantheon.target`
  drop-in, so `systemctl --user restart pantheon.target` reaches all of them
  and `systemctl --user restart hestia` still reaches just Hestia.
- **Registry.** `modules.yaml` (copied from `modules.yaml.example` by
  `make setup`; gitignored, per host) lists each module's name, title, port
  and whether it is enabled. The Caddyfile and `pantheon.target` are
  generated from it.

What a module must do to join is in [docs/module-contract.md](docs/module-contract.md).

## Modules

| Module | What it is | Port | Standalone | Inside Pantheon | Status |
|---|---|---|---|---|---|
| [Apollo](https://github.com/jeremyrhyde/apollo) | Workouts and self-care routine | 8001 | `http://<host>:8001/` | `/apollo/` | available |
| [Hermes](https://github.com/jeremyrhyde/hermes) | Personal news feed, summarized and scored | 8002 | `http://<host>:8002/` | `/hermes/` | available |
| [Hestia](https://github.com/jeremyrhyde/hestia) | Home automation: devices, scenes, schedules | 8003 | `http://<host>:8003/` | `/hestia/` | available |
| [Pluto](https://github.com/jeremyrhyde/pluto) (private) | Team of workers analysing financial markets | 8004 | — | `/pluto/` | web server pending (`enabled: false`) |

Each is a git submodule under `modules/`, tracking its `main` branch. Pluto
is private, and `.gitmodules` uses SSH URLs, so cloning the submodules needs
an SSH key with access to the repos. An edge display clones without
submodules and needs no key.

## Installation and connection

There are three kinds of machine. The full install and the gateway are
Linux/Raspberry Pi only (systemd user units).

### Main Pi — the controller node

Runs every enabled module, Pantheon's app and the gateway.

```bash
git clone --recurse-submodules https://github.com/jeremyrhyde/pantheon.git
cd pantheon
make setup-all build-all     # uv + deps for Pantheon and every module; writes modules.yaml
make service-install-all     # module units + Pantheon + Caddy, all under pantheon.target
make kiosk-install           # optional: this Pi's own screen shows the home screen
```

`service-install-all` installs Caddy from apt if it is missing and disables
apt's system-wide `caddy.service` (Pantheon runs its own as a user unit).
Open `http://<main-pi>:8000/`.

### Edge display — a screen somewhere else in the house

Runs only Chromium, pointed at the main Pi. No modules, no uv, no Caddy.

```bash
git clone https://github.com/jeremyrhyde/pantheon.git      # no submodules needed
cd pantheon
make kiosk-install MODULE=apollo SERVER=<main-pi-ip>   # omit MODULE for the home screen
# Pi OS Lite / Ubuntu Server: make kiosk-install-headless MODULE=… SERVER=…
```

`SERVER` is an IP or hostname. The kiosk opens
`http://<SERVER>:8000/<MODULE>/`. Re-run with a different `MODULE`/`SERVER`
to change what the screen shows (it rewrites `kiosk.env`);
`make kiosk-uninstall` removes it.

### Standalone module node

A module on its own, with no Pantheon at all — clone the module's repo and
follow its README. It serves the same UI on its own port.

### Day to day

```bash
make service-status-all          # every unit: active? /health?
make service-restart-all         # restart everything (pantheon.target)
journalctl --user -u hestia -f   # one module's logs
make gateway-config              # after changing a port in modules.yaml: re-render the Caddyfile, reload the gateway
make service-install-all         # after enabling/disabling a module (adds/removes its unit)
make service-uninstall-all       # stop and remove it all (Caddy and linger stay)
```

Updating modules: change a module in its own repo and push to `main`, then
here:

```bash
make modules-update          # move each module to its branch tip
git add modules && git commit -m "chore: bump modules"
make build-all service-restart-all
```

`make <verb>` acts on Pantheon only; `make <verb>-all` (setup, build, test,
clean) runs it here and then in each module, stopping at the first failure.

## Developing Pantheon itself

```bash
make setup build
make run                     # Pantheon app only: http://localhost:8010/
make test
```

Copy `.env.example` to `.env` to override settings (ports, module registry
path, health timeout).

## Layout

```
Makefile              setup / build / run / test / *-all / modules* / service-* / kiosk-* / gateway-config
pyproject.toml        uv-managed deps (uv.lock committed)
config.py             Settings + load_modules_config()
modules.yaml.example  the module registry (copy to modules.yaml)
main.py               build_app() + lifespan; `python main.py` serves it
core/api.py           /health, /api/modules/, the UI at /
schemas/modules.py    ModuleEntry, ModulesConfig
services/gateway.py   render_caddyfile()
services/systemd.py   render_target(), render_partof_dropin()
services/render.py    `python -m services.render …` for the installers
services/health.py    HealthChecker — cached module /health probes
tests/                pytest
web/                  home screen (Alpine.js, no build) + kiosk launcher
deploy/               pantheon.service, pantheon-gateway.service, launchd, headless-X files
scripts/              install-server.sh, install-kiosk.sh, install-all.sh
docs/                 module contract, dated specs and plans
artifacts/            committed assets (diagrams, README images)
modules/              apollo, hermes, hestia, pluto (git submodules)
```
