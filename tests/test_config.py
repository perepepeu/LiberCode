import yaml

from libercode import config as config_mod
from libercode.config import LiberConfig


def test_save_provider_config_round_trips_through_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "GLOBAL_CONFIG_PATH", config_path)
    monkeypatch.chdir(tmp_path)

    cfg = LiberConfig()
    cfg.data_dir = str(tmp_path / "data")
    cfg.save_provider_config(
        "openai",
        api_key="sk-test",
        model="gpt-test",
        set_active=True,
    )

    raw = yaml.safe_load(config_path.read_text())
    assert raw["provider"]["name"] == "openai"
    assert raw["provider"]["model"] == "gpt-test"
    assert raw["providers"]["openai"]["api_key"] == "sk-test"

    loaded = LiberConfig.load()
    assert loaded.provider.name == "openai"
    assert loaded.provider.model == "gpt-test"
    assert loaded.providers["openai"].api_key == "sk-test"
