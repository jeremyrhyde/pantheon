"""scripts/run-all.sh argument handling and preflight. Starting the real
system is checked by hand (`make run-all`); these only cover the paths that
exit before anything is launched."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run-all.sh"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={**os.environ, **(env or {})},
        capture_output=True, text=True, timeout=30,
    )


def test_help_describes_both_modes():
    out = _run("--help")
    assert out.returncode == 0
    assert "--dev" in out.stdout
    assert "set -euo" not in out.stdout


def test_unknown_argument_is_rejected():
    out = _run("--nope")
    assert out.returncode == 2
    assert "unknown arg" in out.stderr


def test_missing_caddy_stops_before_launching(tmp_path, system_bin_without):
    # A PATH with uv but no caddy: the script must refuse before starting anything.
    uv = subprocess.run(["bash", "-c", "command -v uv || echo $HOME/.local/bin/uv"],
                        capture_output=True, text=True).stdout.strip()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv").symlink_to(uv)
    out = _run(env={"PATH": f"{bin_dir}:{system_bin_without('caddy')}"})
    assert out.returncode == 1
    assert "caddy not found" in out.stderr
