import sys


def _run_tui() -> None:
    from libercode.agent import LiberAgent
    from libercode.config import ensure_config
    from libercode.tui import LibercodeUI

    cfg = ensure_config()
    agent = LiberAgent(cfg)
    app = LibercodeUI(theme_name=cfg.theme, model=agent.provider.model)
    app.set_agent(agent)
    app.run()


def main() -> None:
    if len(sys.argv) > 1:
        from libercode.cli import main as cli_main

        cli_main()
        return

    _run_tui()


if __name__ == "__main__":
    main()
