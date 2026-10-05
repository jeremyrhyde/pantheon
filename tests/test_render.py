import pytest

from config import Settings
from services.render import main, render

YAML = (
    "modules:\n"
    "  - {name: apollo, title: Apollo, port: 8001}\n"
    "  - {name: pluto, title: Pluto, port: 8004, enabled: false}\n"
)


@pytest.fixture
def settings(tmp_path):
    (tmp_path / "modules.yaml").write_text(YAML)
    return Settings(_env_file=None, MODULES_CONFIG_PATH=str(tmp_path / "modules.yaml"))


def test_modules_lists_enabled_names_and_ports(settings):
    assert render("modules", settings) == "apollo 8001\n"


def test_units_lists_every_unit_with_its_port(settings):
    assert render("units", settings) == (
        "pantheon-gateway.service 8000\n"
        "pantheon.service 8010\n"
        "apollo.service 8001\n"
    )


def test_caddyfile_target_and_dropin_delegate(settings):
    assert "handle_path /apollo/*" in render("caddyfile", settings)
    assert "apollo.service" in render("target", settings)
    assert "PartOf=pantheon.target" in render("dropin", settings)


def test_main_rejects_unknown(capsys):
    assert main(["nope"]) == 2
    assert "usage" in capsys.readouterr().err
