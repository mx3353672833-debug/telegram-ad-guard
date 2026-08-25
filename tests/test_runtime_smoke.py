import importlib
import sys
from types import ModuleType


def test_config_get_reads_nested_keys_without_loading_file(monkeypatch):
    fake_yaml_module = ModuleType("yaml")
    fake_yaml_module.safe_load = lambda stream: {}
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml_module)
    sys.modules.pop("config", None)
    config_module = importlib.import_module("config")
    config_module.Config._config = {
        "telegram": {"token": "abc"},
        "strategy": {"spam_score": 88},
    }

    assert config_module.config.get("telegram.token") == "abc"
    assert config_module.config.get("strategy.spam_score") == 88
    assert config_module.config.get("missing.key", "fallback") == "fallback"


def test_i18n_falls_back_to_en_when_current_locale_missing_key(monkeypatch):
    fake_yaml_module = ModuleType("yaml")

    def fake_safe_load(stream):
        if stream.name.endswith("zh.yml"):
            return {"known": "中文"}
        if stream.name.endswith("en.yml"):
            return {"known": "English", "fallback_only": "Fallback"}
        return {}

    fake_yaml_module.safe_load = fake_safe_load
    monkeypatch.setitem(sys.modules, "yaml", fake_yaml_module)
    sys.modules.pop("i18n", None)
    i18n_module = importlib.import_module("i18n")

    i18n_module.set_locale("zh")

    assert i18n_module.t("known") == "中文"
    assert i18n_module.t("fallback_only") == "Fallback"
    assert i18n_module.t("unknown_key") == "unknown_key"
