def main() -> None:
    from libercode.tui import LibercodeUI
    from libercode.config import LiberConfig
    cfg = LiberConfig.load()
    app = LibercodeUI(theme_name=cfg.theme, model=cfg.provider.model)
    app.run()

if __name__ == "__main__":
    main()
