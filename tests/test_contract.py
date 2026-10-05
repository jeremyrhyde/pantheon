"""Pantheon follows its own module contract: only relative URLs in the web
UI, so it works at :8010/ directly and at :8000/ behind the gateway."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

_ABSOLUTE = [
    re.compile(r'(?:href|src)="/(?!/)'),
    re.compile(r"""fetch\(\s*['"`]/(?!/)"""),
    re.compile(r'"(?:start_url|scope|src)":\s*"/(?!/)'),
    re.compile(r"location\.host\}?/"),
]


def test_web_ui_uses_only_relative_urls():
    offenders = []
    for f in sorted(WEB.rglob("*")):
        if f.suffix not in {".html", ".js", ".webmanifest"}:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(p.search(line) for p in _ABSOLUTE):
                offenders.append(f"{f.relative_to(WEB)}:{n}: {line.strip()}")
    assert offenders == []


STYLE = (WEB / "style.css").read_text(encoding="utf-8")


def test_pantheon_ui_tokens_exist():
    for token in ("--color-ok", "--color-bad", "--color-off", "--color-hot", "--color-space",
                  "--color-star", "--color-hud-edge", "--node-size", "--dot-size",
                  "--duration-float", "--duration-leave", "--duration-sheet"):
        assert f"{token}:" in STYLE, token


def test_state_dot_covers_every_state():
    for state in ("online", "degraded", "kiosk_issue", "offline"):
        assert f".state-dot--{state}" in STYLE, state


def test_page_css_uses_tokens_not_literal_colours():
    for css in ("home.css", "status/status.css"):
        path = WEB / css
        if path.exists():
            assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", path.read_text()), css
