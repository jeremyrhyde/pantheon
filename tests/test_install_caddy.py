"""scripts/install-caddy.sh (`make caddy`) with stand-in caddy, systemctl,
dpkg and sudo on PATH — the fakes only log what they were asked to do, so no
real package or service is ever touched."""

import os
import platform
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install-caddy.sh"

pytestmark = pytest.mark.skipif(platform.system() != "Linux", reason="apt/systemd path is Linux-only")


def _exe(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run(tmp_path: Path, *, caddy_installed: bool, system_caddy_enabled: bool):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sudo_log = tmp_path / "sudo.log"
    sudo_log.touch()
    caddy_body = 'echo "v2.8.4 h1:fake"'
    if caddy_installed:
        _exe(bin_dir / "caddy", caddy_body)
    _exe(bin_dir / "systemctl",
         'case "$*" in *is-enabled*|*is-active*) exit %d ;; *) exit 0 ;; esac'
         % (0 if system_caddy_enabled else 1))
    _exe(bin_dir / "dpkg", "exit 1")  # nothing installed
    # Fake sudo: log the command; "installing" caddy drops the fake binary in.
    _exe(bin_dir / "sudo",
         f'echo "$*" >> "{sudo_log}"\n'
         f'case "$*" in *"apt-get install"*caddy*) '
         f"printf '%s\\n' '#!/usr/bin/env bash' '{caddy_body}' > \"{bin_dir}/caddy\"; "
         f'chmod +x "{bin_dir}/caddy" ;; esac')
    done = subprocess.run(
        ["bash", str(SCRIPT)],
        env={"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True, text=True, timeout=30,
    )
    return done, sudo_log.read_text().splitlines()


def test_present_caddy_and_no_system_service_needs_no_sudo(tmp_path):
    done, sudo = run(tmp_path, caddy_installed=True, system_caddy_enabled=False)
    assert done.returncode == 0, done.stderr
    assert "v2.8.4" in done.stdout
    assert sudo == []


def test_an_enabled_system_caddy_is_disabled(tmp_path):
    done, sudo = run(tmp_path, caddy_installed=True, system_caddy_enabled=True)
    assert done.returncode == 0, done.stderr
    assert sudo == ["systemctl disable --now caddy.service"]


def test_missing_caddy_is_installed_with_apt(tmp_path):
    done, sudo = run(tmp_path, caddy_installed=False, system_caddy_enabled=True)
    assert done.returncode == 0, done.stderr
    assert sudo[:2] == ["apt-get update -qq", "apt-get install -y caddy"]
    assert sudo[-1] == "systemctl disable --now caddy.service"
    assert "v2.8.4" in done.stdout
