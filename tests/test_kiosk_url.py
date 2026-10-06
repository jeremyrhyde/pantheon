"""start-kiosk.sh URL resolution, run in a scratch copy of the repo layout
so the developer's own .env / kiosk.env can't leak in."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "web" / "kiosk" / "start-kiosk.sh"


def _url(tmp_path: Path, env: dict[str, str], kiosk_env: str | None, dotenv: str | None) -> str:
    kiosk_dir = tmp_path / "web" / "kiosk"
    kiosk_dir.mkdir(parents=True)
    shutil.copy(SCRIPT, kiosk_dir / "start-kiosk.sh")
    if dotenv is not None:
        (tmp_path / ".env").write_text(dotenv)
    if kiosk_env is not None:
        (tmp_path / "kiosk.env").write_text(kiosk_env)
    out = subprocess.run(
        ["bash", str(kiosk_dir / "start-kiosk.sh"), "--print-url"],
        env={"PATH": os.environ["PATH"], **env},
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


@pytest.mark.parametrize("env, kiosk_env, dotenv, expected", [
    ({}, None, None, "http://localhost:8000/"),
    ({}, None, "PORT=8010\n", "http://localhost:8000/"),
    ({}, None, "GATEWAY_PORT=9000\n", "http://localhost:9000/"),
    ({}, "KIOSK_MODULE=apollo\n", None, "http://localhost:8000/apollo/"),
    ({}, "KIOSK_MODULE=apollo\nSERVER_IP_ADDRESS=192.168.1.50\n", None,
     "http://192.168.1.50:8000/apollo/"),
    ({}, "SERVER_IP_ADDRESS=192.168.1.60\n", "SERVER_IP_ADDRESS=192.168.1.50\n",
     "http://192.168.1.60:8000/"),
    ({"PANTHEON_UI_URL": "http://x:1/y/"}, "KIOSK_MODULE=apollo\n", None, "http://x:1/y/"),
])
def test_print_url(tmp_path, env, kiosk_env, dotenv, expected):
    assert _url(tmp_path, env, kiosk_env, dotenv) == expected


def _flags(tmp_path: Path, kiosk_env: str | None = None) -> list[str]:
    kiosk_dir = tmp_path / "web" / "kiosk"
    kiosk_dir.mkdir(parents=True)
    shutil.copy(SCRIPT, kiosk_dir / "start-kiosk.sh")
    if kiosk_env is not None:
        (tmp_path / "kiosk.env").write_text(kiosk_env)
    out = subprocess.run(
        ["bash", str(kiosk_dir / "start-kiosk.sh"), "--print-flags"],
        env={"PATH": os.environ["PATH"]}, capture_output=True, text=True, check=True,
    )
    return out.stdout.split()


def test_kiosks_prefer_dark_by_default(tmp_path):
    flags = _flags(tmp_path)
    assert "--force-dark-mode" in flags
    assert "--blink-settings=preferredColorScheme=0" in flags
    assert "--kiosk" in flags


def test_kiosk_theme_light_opts_out(tmp_path):
    flags = _flags(tmp_path, "KIOSK_THEME=light\n")
    assert "--force-dark-mode" not in flags
    assert not any(f.startswith("--blink-settings") for f in flags)
    assert "--kiosk" in flags
