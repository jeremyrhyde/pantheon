from pathlib import Path

import pytest


@pytest.fixture
def system_bin_without(tmp_path):
    """Return a factory: a directory of symlinks to /usr/bin and /bin minus
    the named tools, for PATHs where a tool the host really has installed
    (e.g. caddy on a Pi) must not leak into a "tool is missing" test."""
    def make(*excluded: str) -> Path:
        sys_dir = tmp_path / "sysbin"
        sys_dir.mkdir()
        for src in (Path("/usr/bin"), Path("/bin")):
            for tool in src.iterdir():
                link = sys_dir / tool.name
                if tool.name not in excluded and not link.exists():
                    link.symlink_to(tool)
        return sys_dir
    return make
