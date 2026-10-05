from pathlib import Path

import pytest

from config import Settings, load_modules_config

EXAMPLE = Path(__file__).resolve().parent.parent / "modules.yaml.example"


def _settings(tmp_path: Path, yaml_text: str | None) -> Settings:
    path = tmp_path / "modules.yaml"
    if yaml_text is not None:
        path.write_text(yaml_text)
    return Settings(_env_file=None, PORT=8010, GATEWAY_PORT=8000, MODULES_CONFIG_PATH=str(path))


def test_defaults(monkeypatch):
    for name in ("PORT", "GATEWAY_PORT", "MODULES_CONFIG_PATH", "MODULE_HEALTH_TIMEOUT_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)
    assert (s.PORT, s.GATEWAY_PORT, s.MODULES_CONFIG_PATH) == (8010, 8000, "./modules.yaml")
    assert s.MODULE_HEALTH_TIMEOUT_SECONDS == 1.0


def test_missing_file_is_empty(tmp_path):
    assert load_modules_config(settings=_settings(tmp_path, None)).modules == []


def test_example_file_loads():
    config = load_modules_config(EXAMPLE, settings=Settings(_env_file=None))
    assert [(m.name, m.port, m.enabled) for m in config.modules] == [
        ("apollo", 8001, True), ("hermes", 8002, True),
        ("hestia", 8003, True), ("pluto", 8004, False),
    ]
    assert [m.name for m in config.enabled] == ["apollo", "hermes", "hestia"]
    assert config.modules[0].path == "apollo/"
    assert config.modules[0].unit == "apollo.service"


@pytest.mark.parametrize("yaml_text, message", [
    ("modules:\n  - {name: a, title: A, port: 8001}\n  - {name: a, title: B, port: 8002}\n",
     "duplicate module name: a"),
    ("modules:\n  - {name: a, title: A, port: 8001}\n  - {name: b, title: B, port: 8001}\n",
     "duplicate module port: 8001"),
    ("modules:\n  - {name: Bad Name, title: A, port: 8001}\n", "must match"),
    ('modules:\n  - {name: a, title: "", port: 8001}\n', "title must not be empty"),
    ('modules:\n  - {name: a, title: "A\\"B", port: 8001}\n', "title must not contain"),
    ('modules:\n  - {name: a, title: "A\\\\B", port: 8001}\n', "title must not contain"),
    ('modules:\n  - {name: a, title: "A\\nB", port: 8001}\n', "title must not contain"),
    ("modules:\n  - {name: a, title: A, port: 8010}\n", "clashes with Pantheon's PORT"),
    ("modules:\n  - {name: a, title: A, port: 8000}\n", "clashes with Pantheon's GATEWAY_PORT"),
])
def test_rejects_bad_registries(tmp_path, yaml_text, message):
    with pytest.raises(ValueError, match=message):
        load_modules_config(settings=_settings(tmp_path, yaml_text))
from config import REPO_ROOT


def test_status_is_a_reserved_name(tmp_path):
    with pytest.raises(ValueError, match="reserved"):
        load_modules_config(settings=_settings(tmp_path, "modules:\n  - {name: status, title: S, port: 8001}\n"))


def test_icon_path_inside_the_repo_is_kept(tmp_path):
    config = load_modules_config(settings=_settings(
        tmp_path, "modules:\n  - {name: a, title: A, port: 8001, icon: web/icon.svg}\n"))
    assert config.modules[0].icon == "web/icon.svg"
    assert (REPO_ROOT / config.modules[0].icon).is_file()


def test_icon_path_outside_the_repo_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="outside the Pantheon repo"):
        load_modules_config(settings=_settings(
            tmp_path, "modules:\n  - {name: a, title: A, port: 8001, icon: ../../etc/passwd}\n"))


def test_example_registry_sets_an_icon_for_every_module():
    config = load_modules_config(EXAMPLE, settings=Settings(_env_file=None, PORT=8010, GATEWAY_PORT=8000))
    assert {m.name: m.icon for m in config.modules} == {
        "apollo": "modules/apollo/frontend/public/icon-512.png",
        "hermes": "modules/hermes/frontend/public/icon-512.png",
        "hestia": "modules/hestia/web/icon-512.png",
        "pluto": "modules/pluto/web/icon-512.png",
    }


@pytest.mark.parametrize("icon", [".env", '""', "web"])
def test_icon_must_be_an_image_file(tmp_path, icon):
    with pytest.raises(ValueError, match=r"icon must be a \.png, \.svg or \.webp file"):
        load_modules_config(settings=_settings(
            tmp_path, f"modules:\n  - {{name: a, title: A, port: 8001, icon: {icon}}}\n"))
