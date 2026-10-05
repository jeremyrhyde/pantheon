# Pantheon — notes for Claude

## Status

Pantheon fronts four modules through a Caddy gateway (`:8000/<module>/`),
groups their units under `pantheon.target`, and shows a starfield home
screen and a HUD status screen (`/status/`) fed by in-memory collectors
(`services/`), edge heartbeats and optional module `/api/status`. Pluto's web
server is pending (registered, `enabled: false`).

## Modules

`modules/{apollo,hermes,hestia,pluto}` are git submodules — independent apps,
each its own repo with its own `make setup build run test clean`. Pantheon's
`make <verb>` touches only Pantheon; `make <verb>-all` runs Pantheon, then
`make -C modules/<m> <verb>` for each module in turn.

- Change a module inside its own repo (here under `modules/<m>`, or its
  standalone clone), push to its tracked branch (`branch =` in
  `.gitmodules`), then commit the new pointer here (`make modules-update`).
- Every module keeps the shared `.gitignore` block identical; the lines below
  `<repo>-specific` are each repo's own.
- When a piece is needed, look in the modules first for a working version:
  `hermes/core/{events,websocket,state}.py`, `hermes/config.py`,
  `hestia/web/`, `hestia/scripts/` + `hestia/deploy/`.

## Module contract (docs/module-contract.md)

- Ports: gateway 8000, Pantheon app 8010, apollo 8001, hermes 8002,
  hestia 8003, pluto 8004.
- UI at `/` (mounted last), API under `/api/` (WebSocket `/api/ws`),
  `/health` at the root, `make service-*`.
- `icon-512.png` at the UI root; optional `GET /api/status` (generic stats).
- Only relative URLs in any UI — no leading `/` in `href`, `src`, `fetch`,
  manifests. That is what lets one build run standalone and under a prefix.
- Pantheon composes over HTTP only; anything new must work standalone in its
  module first.

## Conventions

- Python ≥3.11, managed with `uv`. `make build` / `make test` / `make run`.
- Every setting is a field on `config.Settings` and a commented line in
  `.env.example`. Never read `os.environ` at a call site.
- A hand-edited YAML config gets a committed `<name>.yaml.example`; the real
  file is gitignored.
- API: one `_build_<area>_router()` per area in `core/api.py`; shared objects
  live on `app.state`, set up in `main.py`'s lifespan.
- Web UI: no build step. Alpine.js from the CDN; all colors, radii, spacing,
  type sizes, and durations are tokens in `web/style.css` `:root`.
- Design docs: `docs/YYYY-MM-DD-<topic>-spec.md`, then `-plan.md`.
