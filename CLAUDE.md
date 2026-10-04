# Pantheon — notes for Claude

## Status

Skeleton plus four modules. Pantheon's own server is the Apollo `template`
skeleton, renamed; how it presents the modules together is not designed yet.

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
