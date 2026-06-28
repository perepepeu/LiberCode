import os
import sys
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "libercode"
GLOBAL_CONFIG_PATH = CONFIG_DIR / "config.yaml"
DATA_DIR = CONFIG_DIR / "data"
DEFAULT_MODE = "build"


@dataclass
class ProviderConfig:
    name: str = "builtin"
    api_key: str = ""
    api_base: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7

    @classmethod
    def builtin_defaults(cls):
        return cls(name="builtin", model="Qwen/Qwen2.5-Coder-7B-Instruct")

    @classmethod
    def openai_defaults(cls):
        return cls(name="openai", model="gpt-4o", api_base="https://api.openai.com/v1")

    @classmethod
    def anthropic_defaults(cls):
        return cls(
            name="anthropic",
            model="claude-sonnet-4-20250514",
            api_base="https://api.anthropic.com/v1",
        )

    @classmethod
    def nvidia_defaults(cls):
        return cls(
            name="nvidia",
            model="nvidia/llama-3.1-nemotron-ultra-253b-v1",
            api_base="https://integrate.api.nvidia.com/v1",
        )

    @classmethod
    def mistral_defaults(cls):
        return cls(
            name="mistral",
            model="mistral-large-latest",
            api_base="https://api.mistral.ai/v1",
        )

    @classmethod
    def cohere_defaults(cls):
        return cls(
            name="cohere",
            model="command-r-plus",
            api_base="",
        )

    @classmethod
    def xai_defaults(cls):
        return cls(
            name="xai",
            model="grok-3",
            api_base="https://api.x.ai/v1",
        )

    @classmethod
    def cerebras_defaults(cls):
        return cls(
            name="cerebras",
            model="llama-4-scout-17b-16e-instruct",
            api_base="https://api.cerebras.ai/v1",
        )


@dataclass
class LiberConfig:
    provider: ProviderConfig = field(default_factory=ProviderConfig.builtin_defaults)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    active_provider: str = "builtin"
    theme: str = "dracula"
    mode: str = DEFAULT_MODE
    data_dir: str = str(DATA_DIR)
    max_turns: int = 30
    verbose: bool = False
    enable_checkpoints: bool = True
    checkpoint_interval: int = 5
    enable_memory: bool = True
    enable_task_tracking: bool = True
    stop_condition_enabled: bool = True
    agent_max_subagents: int = 3
    builtin_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    builtin_api_base: str = "https://api-inference.huggingface.co/models/"

    @classmethod
    def from_dict(cls, d: dict):
        d = dict(d)
        provider_dict = d.pop("provider", {})
        cfg = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if provider_dict:
            cfg.provider = ProviderConfig(**provider_dict)
        return cfg

    def to_dict(self):
        d = asdict(self)
        return d

    @classmethod
    def load(cls) -> "LiberConfig":
        if GLOBAL_CONFIG_PATH.exists():
            with open(GLOBAL_CONFIG_PATH) as f:
                raw = yaml.safe_load(f) or {}
            cfg = cls.from_dict(raw)
        else:
            cfg = cls()
        project_cfg_path = Path.cwd() / ".libercoderc"
        if project_cfg_path.exists():
            with open(project_cfg_path) as f:
                raw = yaml.safe_load(f) or {}
            for k, v in raw.items():
                if k == "provider" and isinstance(v, dict):
                    for pk, pv in v.items():
                        if hasattr(cfg.provider, pk):
                            setattr(cfg.provider, pk, pv)
                elif hasattr(cfg, k):
                    setattr(cfg, k, v)
        cfg.data_dir = str(Path(cfg.data_dir).expanduser().resolve())
        os.makedirs(cfg.data_dir, exist_ok=True)
        return cfg

    def save_global(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if self.provider.api_key:
            import stat
            config_path = str(GLOBAL_CONFIG_PATH)
            with open(config_path, "w") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False)
            try:
                os.chmod(config_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        else:
            with open(GLOBAL_CONFIG_PATH, "w") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False)

    def save_provider_config(
        self,
        provider_name: str,
        api_key:       str  = "",
        model:         str  = "",
        api_base:      str  = "",
        set_active:    bool = True,
    ) -> None:
        import tempfile, shutil

        config_path = Path(
            self.config_file
            if hasattr(self, "config_file")
            else Path.home() / ".config" / "libercode" / "config.toml"
        )
        config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(config_path, "rb") as f:
                data = __import__("tomllib").load(f)
        except Exception:
            data = {}

        data.setdefault("providers", {})
        data["providers"].setdefault(provider_name, {})
        if api_key:
            data["providers"][provider_name]["api_key"] = api_key
        if model:
            data["providers"][provider_name]["model"] = model
        if api_base:
            data["providers"][provider_name]["api_base"] = api_base
        if set_active:
            data.setdefault("provider", {})
            data["provider"]["name"] = provider_name
            if model:
                data["provider"]["model"] = model

        tmp = config_path.with_suffix(".tmp")
        try:
            import tomli_w
            with open(tmp, "wb") as f:
                tomli_w.dump(data, f)
            shutil.move(str(tmp), str(config_path))
        except Exception as e:
            if tmp.exists():
                tmp.unlink()
            raise e


def first_run_wizard():
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]Welcome to LiberCode![/]\n"
            "Your open-source terminal pair programmer.\n\n"
            "Let's get you set up.",
            border_style="cyan",
        )
    )

    provider_choice = Prompt.ask(
        "Choose a provider",
        choices=["builtin", "openai", "anthropic", "google", "groq",
                 "nvidia", "mistral", "cohere", "xai", "cerebras",
                 "deepseek", "together", "openrouter", "ollama", "custom"],
        default="builtin",
    )

    cfg = LiberConfig()

    if provider_choice == "builtin":
        cfg.provider = ProviderConfig.builtin_defaults()
        console.print(
            "[green]✓ Using built-in free provider (HuggingFace Inference API)[/]"
        )
        console.print("  No API key needed. Uses free open models.")
        console.print(
            "  For production, set up a custom provider later with `libercode config`"
        )
    else:
        defaults_map = {
            "openai":     ProviderConfig.openai_defaults,
            "anthropic":  ProviderConfig.anthropic_defaults,
            "nvidia":     ProviderConfig.nvidia_defaults,
            "mistral":    ProviderConfig.mistral_defaults,
            "cohere":     ProviderConfig.cohere_defaults,
            "xai":        ProviderConfig.xai_defaults,
            "cerebras":   ProviderConfig.cerebras_defaults,
        }
        if provider_choice in defaults_map:
            cfg.provider = defaults_map[provider_choice]()
        else:
            cfg.provider = ProviderConfig(name=provider_choice)

        cfg.provider.api_key = Prompt.ask("API key", password=True)
        if provider_choice == "custom":
            cfg.provider.api_base = Prompt.ask("API base URL")
            cfg.provider.model = Prompt.ask("Model name")

    cfg.mode = Prompt.ask(
        "Default working mode", choices=["build", "plan", "spec"], default="build"
    )

    cfg.save_global()
    console.print("[bold green]✓ Configuration saved![/]")
    console.print(f"  Config: {GLOBAL_CONFIG_PATH}")
    if cfg.provider.api_key:
        console.print(
            "[yellow]⚠ Security note: API key is stored in plaintext. "
            "Restrict file permissions and avoid sharing this config.[/]"
        )
    console.print(
        "\n[dim]Tip: Create a [bold].libercoderc[/] file in any project to override settings.[/]"
    )
    return cfg


def ensure_config():
    if not GLOBAL_CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg = first_run_wizard()
        return cfg
    return LiberConfig.load()
