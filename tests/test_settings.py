from config import REPO_ROOT, Settings


def _s(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_explicit_absolute_path():
    assert _s(ACCESS_LOG_PATH="/var/log/a.log", XDG_RUNTIME_DIR="/run/user/1").access_log_path.as_posix() == "/var/log/a.log"


def test_relative_path_is_under_the_repo():
    assert _s(ACCESS_LOG_PATH="logs/a.log").access_log_path == REPO_ROOT / "logs" / "a.log"


def test_xdg_default():
    assert _s(XDG_RUNTIME_DIR="/run/user/1000", ACCESS_LOG_PATH="").access_log_path.as_posix() == "/run/user/1000/pantheon/access.log"


def test_fallback_without_runtime_dir():
    assert _s(XDG_RUNTIME_DIR="", ACCESS_LOG_PATH="").access_log_path == REPO_ROOT / "build" / "access.log"
