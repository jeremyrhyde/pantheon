"""Print a generated config to stdout, for the Makefile and install scripts.

    uv run python -m services.render caddyfile   # build/Caddyfile
    uv run python -m services.render target      # pantheon.target
    uv run python -m services.render dropin      # <module>.service.d/pantheon.conf
    uv run python -m services.render modules     # "<name> <port>" per enabled module
    uv run python -m services.render units       # "<unit> <port>" for --status
"""

from __future__ import annotations

import sys

from config import Settings, load_modules_config
from services.gateway import render_caddyfile
from services.systemd import render_partof_dropin, render_target

WHATS = ("caddyfile", "target", "dropin", "modules", "units")


def render(what: str, settings: Settings | None = None) -> str:
    settings = settings or Settings()
    modules = load_modules_config(settings=settings)
    if what == "caddyfile":
        return render_caddyfile(modules, settings)
    if what == "target":
        return render_target(modules)
    if what == "dropin":
        return render_partof_dropin()
    if what == "modules":
        return "".join(f"{m.name} {m.port}\n" for m in modules.enabled)
    if what == "units":
        rows = [
            ("pantheon-gateway.service", settings.GATEWAY_PORT),
            ("pantheon.service", settings.PORT),
            *((m.unit, m.port) for m in modules.enabled),
        ]
        return "".join(f"{unit} {port}\n" for unit, port in rows)
    raise ValueError(f"unknown render target {what!r}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in WHATS:
        print(f"usage: python -m services.render {{{'|'.join(WHATS)}}}", file=sys.stderr)
        return 2
    sys.stdout.write(render(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
