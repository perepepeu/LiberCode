import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from libercode import __main__


def test_main_delegates_to_cli_when_arguments_are_present(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["libercode", "--version"])

    with patch("libercode.cli.main") as cli_main:
        __main__.main()

    cli_main.assert_called_once_with()


def test_main_starts_agent_connected_tui_without_arguments(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["libercode"])

    cfg = SimpleNamespace(theme="dracula")
    agent = MagicMock()
    agent.provider.model = "test-model"
    app = MagicMock()

    with (
        patch("libercode.config.ensure_config", return_value=cfg),
        patch("libercode.agent.LiberAgent", return_value=agent) as agent_cls,
        patch("libercode.tui.LibercodeUI", return_value=app) as ui_cls,
    ):
        __main__.main()

    agent_cls.assert_called_once_with(cfg)
    ui_cls.assert_called_once_with(theme_name="dracula", model="test-model")
    app.set_agent.assert_called_once_with(agent)
    app.run.assert_called_once_with()
