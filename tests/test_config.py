"""Unit tests for llmtr.config (owner: M2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmtr import config
from llmtr.errors import ConfigError

# --- paths -----------------------------------------------------------------------------------


def test_config_path_uses_xdg_config_home() -> None:
    env = {"XDG_CONFIG_HOME": "/tmp/xdg-config"}
    assert config.config_path(env) == Path("/tmp/xdg-config/llmtr/config.toml")


def test_config_path_falls_back_to_home_dot_config() -> None:
    assert config.config_path({}) == Path.home() / ".config" / "llmtr" / "config.toml"


def test_state_path_uses_xdg_state_home() -> None:
    env = {"XDG_STATE_HOME": "/tmp/xdg-state"}
    assert config.state_path(env) == Path("/tmp/xdg-state/llmtr/state.toml")


def test_state_path_falls_back_to_home_local_state() -> None:
    assert config.state_path({}) == Path.home() / ".local" / "state" / "llmtr" / "state.toml"


def test_cache_dir_uses_xdg_cache_home() -> None:
    env = {"XDG_CACHE_HOME": "/tmp/xdg-cache"}
    assert config.cache_dir(env) == Path("/tmp/xdg-cache/llmtr")


def test_cache_dir_falls_back_to_home_dot_cache() -> None:
    assert config.cache_dir({}) == Path.home() / ".cache" / "llmtr"


# --- normalize_ollama_url ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("localhost", "http://localhost:11434"),
        ("http://host.docker.internal:11434/", "http://host.docker.internal:11434"),
        ("http://localhost:11434", "http://localhost:11434"),
        ("localhost:9999", "http://localhost:9999"),
        ("0.0.0.0", "http://127.0.0.1:11434"),
        ("http://0.0.0.0:11434", "http://127.0.0.1:11434"),
        ("https://example.com:443", "https://example.com:443"),
    ],
)
def test_normalize_ollama_url(value: str, expected: str) -> None:
    assert config.normalize_ollama_url(value) == expected


# --- parse_config ------------------------------------------------------------------------------


def test_parse_config_empty_gives_defaults() -> None:
    cfg = config.parse_config({})
    assert cfg == config.Config()


def test_parse_config_unknown_keys_ignored() -> None:
    cfg = config.parse_config({"unknown_table": {"x": 1}, "ollama": {"bogus_key": "x"}})
    assert cfg.ollama == config.OllamaConfig()


def test_parse_config_overrides_values() -> None:
    cfg = config.parse_config(
        {
            "ollama": {"url": "http://example:11434", "timeout": 30.0, "max_chars": 100},
            "models": {"fix": "custom-model"},
            "languages": {"native": "en", "other": "pl"},
            "notify": {"enabled": False},
        }
    )
    assert cfg.ollama.url == "http://example:11434"
    assert cfg.ollama.timeout == 30.0
    assert cfg.ollama.max_chars == 100
    assert cfg.models.fix == "custom-model"
    assert (cfg.languages.native, cfg.languages.other) == ("en", "pl")
    assert cfg.notify.enabled is False


def test_parse_config_ollama_host_env_overrides_url() -> None:
    cfg = config.parse_config(
        {"ollama": {"url": "http://example:11434"}}, env={"OLLAMA_HOST": "host.docker.internal"}
    )
    assert cfg.ollama.url == "http://host.docker.internal:11434"


def test_parse_config_empty_ollama_host_env_does_not_override() -> None:
    cfg = config.parse_config({"ollama": {"url": "http://example:11434"}}, env={"OLLAMA_HOST": ""})
    assert cfg.ollama.url == "http://example:11434"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example:21", "myapp://localhost"])
def test_parse_config_rejects_non_http_scheme_in_config(url: str) -> None:
    scheme = url.split("://", 1)[0]
    with pytest.raises(ConfigError) as excinfo:
        config.parse_config({"ollama": {"url": url}}, env={})
    message = excinfo.value.user_message
    assert f"'{scheme}'" in message
    assert "[ollama] url" in message


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example:21", "myapp://localhost"])
def test_parse_config_rejects_non_http_scheme_in_ollama_host(url: str) -> None:
    scheme = url.split("://", 1)[0]
    with pytest.raises(ConfigError) as excinfo:
        config.parse_config({}, env={"OLLAMA_HOST": url})
    message = excinfo.value.user_message
    assert f"'{scheme}'" in message
    assert "OLLAMA_HOST" in message


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://example:11434", "http://example:11434"),
        ("https://example:443", "https://example:443"),
        ("HTTP://example:11434", "http://example:11434"),
        ("localhost:11434", "http://localhost:11434"),
    ],
)
def test_parse_config_accepts_http_schemes(url: str, expected: str) -> None:
    assert config.parse_config({"ollama": {"url": url}}, env={}).ollama.url == expected
    assert config.parse_config({}, env={"OLLAMA_HOST": url}).ollama.url == expected


def test_parse_config_rejects_unsupported_language() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"languages": {"native": "de"}})


def test_parse_config_rejects_same_native_and_other() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"languages": {"native": "pl", "other": "pl"}})


def test_parse_config_rejects_non_positive_timeout() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"ollama": {"timeout": 0}})


def test_parse_config_rejects_non_positive_max_chars() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"ollama": {"max_chars": -1}})


def test_parse_config_rejects_wrong_type() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"ollama": {"timeout": "not-a-number"}})


def test_parse_config_key_overrides() -> None:
    cfg = config.parse_config(
        {
            "keys": {
                "override": [
                    {
                        "app": ["org.gnome.Terminal", "kitty"],
                        "copy": "ctrl+shift+c",
                        "paste": "ctrl+shift+v",
                    }
                ]
            }
        }
    )
    assert cfg.keys.override == (
        config.KeyOverride(
            app=("org.gnome.Terminal", "kitty"), copy="ctrl+shift+c", paste="ctrl+shift+v"
        ),
    )


def test_parse_config_tone_presets_append_after_team() -> None:
    cfg = config.parse_config(
        {"tone": {"preset": [{"name": "formal", "instruction": "Be formal."}]}}
    )
    assert [p.name for p in cfg.tone.presets] == ["team", "formal"]


def test_parse_config_tone_preset_named_team_replaces_builtin() -> None:
    cfg = config.parse_config({"tone": {"preset": [{"name": "team", "instruction": "Custom."}]}})
    assert [p.name for p in cfg.tone.presets] == ["team"]
    assert cfg.tone.presets[0].instruction == "Custom."


# --- log ---------------------------------------------------------------------------------------


def test_parse_config_log_defaults() -> None:
    cfg = config.parse_config({})
    assert cfg.log == config.LogConfig()
    assert (cfg.log.enabled, cfg.log.level) == (True, "info")


def test_parse_config_log_overrides_values() -> None:
    cfg = config.parse_config({"log": {"enabled": False, "level": "debug"}})
    assert (cfg.log.enabled, cfg.log.level) == (False, "debug")


def test_parse_config_log_rejects_bad_level() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"log": {"level": "verbose"}})


def test_parse_config_log_level_env_overrides_config_value() -> None:
    cfg = config.parse_config({"log": {"level": "info"}}, env={"LLMTR_LOG_LEVEL": "error"})
    assert cfg.log.level == "error"


def test_parse_config_log_level_env_rejects_bad_value() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({}, env={"LLMTR_LOG_LEVEL": "verbose"})


def test_parse_config_empty_log_level_env_does_not_override() -> None:
    cfg = config.parse_config({"log": {"level": "debug"}}, env={"LLMTR_LOG_LEVEL": ""})
    assert cfg.log.level == "debug"


def test_parse_config_log_level_accepts_mixed_case_from_config_and_env() -> None:
    cfg = config.parse_config({"log": {"level": "  INFO "}})
    assert cfg.log.level == "info"

    cfg = config.parse_config({}, env={"LLMTR_LOG_LEVEL": "DEBUG"})
    assert cfg.log.level == "debug"


# --- load_config ---------------------------------------------------------------------------


def test_load_config_missing_file_gives_defaults(tmp_path: Path) -> None:
    cfg = config.load_config(tmp_path / "does-not-exist.toml")
    assert cfg == config.Config()


def test_load_config_reads_toml_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[models]\nfix = "gemma3-custom"\n', encoding="utf-8")
    cfg = config.load_config(path)
    assert cfg.models.fix == "gemma3-custom"


def test_load_config_invalid_toml_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("not valid toml =", encoding="utf-8")
    with pytest.raises(ConfigError):
        config.load_config(path)


def test_load_config_applies_ollama_host_even_without_file(tmp_path: Path) -> None:
    cfg = config.load_config(
        tmp_path / "does-not-exist.toml", env={"OLLAMA_HOST": "host.docker.internal"}
    )
    assert cfg.ollama.url == "http://host.docker.internal:11434"


# --- state & tone --------------------------------------------------------------------------


def test_load_state_missing_file_gives_default(tmp_path: Path) -> None:
    state = config.load_state(tmp_path / "state.toml")
    assert state == config.State()


def test_load_state_reads_tone(tmp_path: Path) -> None:
    path = tmp_path / "state.toml"
    path.write_text('tone = "formal"\n', encoding="utf-8")
    assert config.load_state(path).tone == "formal"


def test_load_state_unreadable_file_gives_default(tmp_path: Path) -> None:
    path = tmp_path / "state.toml"
    path.write_text("not valid toml =", encoding="utf-8")
    assert config.load_state(path) == config.State()


def test_save_state_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.toml"
    config.save_state(config.State(tone="formal"), path)
    assert config.load_state(path).tone == "formal"


def test_save_state_escapes_quotes(tmp_path: Path) -> None:
    path = tmp_path / "state.toml"
    config.save_state(config.State(tone='weird"name'), path)
    assert config.load_state(path).tone == 'weird"name'


def test_current_tone_known_name() -> None:
    cfg = config.Config(
        tone=config.ToneConfig(
            presets=(config.TEAM_TONE, config.TonePreset(name="formal", instruction="Be formal."))
        )
    )
    state = config.State(tone="formal")
    assert config.current_tone(cfg, state).name == "formal"


def test_current_tone_unknown_name_falls_back_to_first() -> None:
    cfg = config.Config()
    state = config.State(tone="does-not-exist")
    assert config.current_tone(cfg, state) == cfg.tone.presets[0]


def test_next_tone_cycles() -> None:
    formal = config.TonePreset(name="formal", instruction="Be formal.")
    cfg = config.Config(tone=config.ToneConfig(presets=(config.TEAM_TONE, formal)))
    assert config.next_tone(cfg, config.State(tone="team")) == formal
    assert config.next_tone(cfg, config.State(tone="formal")) == config.TEAM_TONE


def test_next_tone_single_preset_returns_itself() -> None:
    cfg = config.Config()
    assert config.next_tone(cfg, config.State(tone="team")) == config.TEAM_TONE


# --- cache ----------------------------------------------------------------------------------


def test_save_last_result_writes_file(tmp_path: Path) -> None:
    path = config.save_last_result("translated text", tmp_path)
    assert path == tmp_path / "last.txt"
    assert path.read_text(encoding="utf-8") == "translated text"


def test_save_last_result_overwrites(tmp_path: Path) -> None:
    config.save_last_result("first", tmp_path)
    path = config.save_last_result("second", tmp_path)
    assert path.read_text(encoding="utf-8") == "second"


# --- v2: platform-dependent key defaults and notify.backend --------------------------------------


def test_parse_config_default_platform_is_linux() -> None:
    cfg = config.parse_config({})
    assert (cfg.keys.copy, cfg.keys.paste, cfg.keys.start_delay) == ("ctrl+c", "ctrl+v", 0.25)
    assert cfg == config.parse_config({}, platform="linux")


def test_parse_config_macos_without_keys_table_uses_mac_defaults() -> None:
    cfg = config.parse_config({}, platform="macos")
    assert (cfg.keys.copy, cfg.keys.paste, cfg.keys.start_delay) == ("cmd+c", "cmd+v", 0.0)
    assert cfg.keys.copy_timeout == config.KeysConfig().copy_timeout
    assert cfg.keys.paste_delay == config.KeysConfig().paste_delay


def test_parse_config_macos_explicit_keys_win() -> None:
    data = {"keys": {"copy": "ctrl+c", "paste": "ctrl+shift+v", "start_delay": 0.25}}
    cfg = config.parse_config(data, platform="macos")
    assert (cfg.keys.copy, cfg.keys.paste, cfg.keys.start_delay) == (
        "ctrl+c",
        "ctrl+shift+v",
        0.25,
    )


def test_parse_config_macos_defaults_only_for_missing_keys() -> None:
    cfg = config.parse_config({"keys": {"paste": "cmd+shift+v"}}, platform="macos")
    assert (cfg.keys.copy, cfg.keys.paste, cfg.keys.start_delay) == ("cmd+c", "cmd+shift+v", 0.0)


def test_load_config_passes_platform(tmp_path) -> None:
    missing = tmp_path / "none.toml"
    assert config.load_config(missing, env={}, platform="macos").keys.copy == "cmd+c"
    assert config.load_config(missing, env={}).keys.copy == "ctrl+c"
    existing = tmp_path / "config.toml"
    existing.write_text("[ollama]\ntimeout = 30\n", encoding="utf-8")
    mac = config.load_config(existing, env={}, platform="macos")
    assert (mac.keys.copy, mac.keys.paste, mac.keys.start_delay) == ("cmd+c", "cmd+v", 0.0)
    assert mac.ollama.timeout == 30
    existing.write_text('[keys]\ncopy = "ctrl+c"\n', encoding="utf-8")
    assert config.load_config(existing, env={}, platform="macos").keys.copy == "ctrl+c"


def test_notify_backend_default_is_auto() -> None:
    assert config.parse_config({}).notify.backend == "auto"


@pytest.mark.parametrize("backend", ["auto", "hammerspoon", "osascript"])
def test_notify_backend_valid_values(backend) -> None:
    assert config.parse_config({"notify": {"backend": backend}}).notify.backend == backend


def test_notify_backend_invalid_value_is_config_error() -> None:
    with pytest.raises(ConfigError) as info:
        config.parse_config({"notify": {"backend": "growl"}}, source="/x/config.toml")
    assert str(info.value) == (
        "Config error in /x/config.toml: 'notify.backend' must be one of auto, hammerspoon, "
        "osascript"
    )


def test_notify_backend_wrong_type_is_config_error() -> None:
    with pytest.raises(ConfigError):
        config.parse_config({"notify": {"backend": 3}})
