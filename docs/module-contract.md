# Pantheon module contract

A module is an independent app with its own repo that installs and runs on
its own. To join Pantheon it follows these rules, which let the **same
files** run standalone (`http://<host>:<port>/`) and behind Pantheon's
gateway (`http://<main-pi>:8000/<name>/`) with no configuration change.

## Checklist

- [ ] **Unique default port** (`PORT` in `config.Settings`). Pantheon refuses
      to load a `modules.yaml` whose module port equals its own `PORT` or
      `GATEWAY_PORT`, or repeats another module's port or name.

  | App | Port | Gateway path |
  |---|---|---|
  | Caddy gateway | 8000 | — |
  | Pantheon app | 8010 | `/` |
  | Apollo | 8001 | `/apollo/` |
  | Hermes | 8002 | `/hermes/` |
  | Hestia | 8003 | `/hestia/` |
  | Pluto | 8004 | `/pluto/` |
  | next module | 8005 … 8009 | `/<name>/` |

- [ ] **A name matching `^[a-z][a-z0-9-]*$`** (`status` is reserved: it is
      Pantheon's own screen). Everything else is derived
      from it: gateway path `/<name>/`, unit `<name>.service`, checkout
      `modules/<name>`.
- [ ] **UI at `/`**, mounted **last** (a mount at `/` shadows every route
      registered after it).
- [ ] **Every API route under `/api/`**, WebSocket at `/api/ws`.
- [ ] **`/health` at the root**, 200 when up. Pantheon probes it on
      `localhost:<port>`, directly, not through the gateway.
- [ ] **No root-absolute URLs** in the UI: `href="style.css"`,
      `fetch('api/devices/')`, manifest `start_url`/`scope` `"./"`.
      WebSocket: `new URL('api/ws', document.baseURI)` with `http`→`ws`.
- [ ] **Canonical API paths** (with the trailing slash the route declares) —
      a framework slash-redirect drops the gateway prefix.
- [ ] **No absolute redirects** from the server.
- [ ] **Storage keys prefixed** `<module>:` — behind the gateway every module
      shares one origin.
- [ ] **`make service-install | service-uninstall | service-status |
      service-restart`**, installing a systemd user unit named `<name>.service`.
      (`make service-install-all` calls `service-install` and
      `service-uninstall` in each enabled module.)
- [ ] A **contract test** in the module (port, routes under `/api/`, UI at
      `/` without shadowing `/health`, a static scan for absolute URLs).
      Pantheon's own is `tests/test_contract.py`.
- [ ] **App icon:** `icon-512.png` (512×512 PNG) at the UI root, for
      standalone installs and phones. Pantheon's `modules.yaml` points at the
      same file in the checkout (`icon:`, a `.png`, `.svg` or `.webp` inside
      the Pantheon repo), so the home screen shows it even when the module
      is down.
- [ ] *(optional)* **`GET /api/status`** for Pantheon's status screen:

      {"state": "ok" | "degraded" | "error",
       "summary": "optional one line (max 200 chars)",
       "stats": [{"label": "...", "value": 42,
                  "kind": "number|count|time|text|percent", "warn": false}]}

      `value` is a string, number, boolean or null; `label` is at most 80
      characters and there are at most 20 stats. `time` values are ISO-8601
      UTC. Pantheon shows the stats as-is and never interprets labels;
      `degraded`/`error` turn the module's dot yellow (`/health` still
      decides online vs. offline). A body of the wrong shape is ignored.
      Keep it cheap — Pantheon polls it every `MODULE_POLL_SECONDS` (10 s).
- [ ] A **"Using with Pantheon"** section in the module README.

## What the gateway does

The generated Caddyfile (`build/Caddyfile`) proxies `/<name>/*` to
`localhost:<port>` with the prefix stripped, redirects `/<name>` to
`/<name>/` (308), answers `503` for a disabled module, and sends everything
else to Pantheon's app. That is why the module sees the same paths it serves
standalone, and why it must not emit absolute URLs or redirects.

## Building something new: both levels

- A module feature is built and tested **standalone, in the module's repo**.
  If it only works inside Pantheon, it is in the wrong place.
- Pantheon adds only **composition**: routing, aggregation, the home screen.
  It never imports module code (the modules can't share a process) and reads
  module data **only through module HTTP APIs** (`<name>/api/...`, same
  origin through the gateway).

## Adding a module

1. Make it follow the checklist above, in its own repo.
2. `git submodule add -b main <url> modules/<name>`, add it to `MODULES` in
   the Makefile and to `modules.yaml.example`.
3. On the main Pi: add it to `modules.yaml` (`name`, `title`, `port`,
   `enabled`, `icon`), then `make service-install-all`. Re-routing an existing
   module (port change) needs only `make gateway-config`.
