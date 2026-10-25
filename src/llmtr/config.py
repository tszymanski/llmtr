"""Config, state and cache files (owner: M2; dataclasses and constants are final from M1).

- Config: ``$XDG_CONFIG_HOME/llmtr/config.toml`` (default ``~/.config/llmtr/config.toml``),
  read with ``tomllib``. A missing file means all defaults. Unknown keys are ignored.
- State:  ``$XDG_STATE_HOME/llmtr/state.toml`` (default ``~/.local/state/llmtr/state.toml``),
  one key: ``tone = "<preset name>"``. Written by a tiny writer, atomically.
- Cache:  ``$XDG_CACHE_HOME/llmtr/last.txt`` (default ``~/.cache/llmtr/last.txt``), last result.

The dataclasses below are the schema; ``docs/architecture.md`` documents every key. Other modules
read these dataclasses but never parse files themselves.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llmtr.errors import ConfigError
from llmtr.platforms import Platform, key_defaults

DEFAULT_OLLAMA_URL = "http://localhost:11434"
"""Used when neither ``OLLAMA_HOST`` nor ``[ollama] url`` is set."""

OLLAMA_HOST_ENV = "OLLAMA_HOST"
"""Environment variable that overrides ``[ollama] url`` (same meaning as for the ollama CLI)."""

NOTIFY_BACKENDS = ("auto", "hammerspoon", "osascript")
"""Valid values of ``[notify] backend``."""

LOG_LEVEL_ENV = "LLMTR_LOG_LEVEL"
"""Environment variable that overrides ``[log] level``."""

_LOG_LEVELS = frozenset({"debug", "info", "error"})

SUPPORTED_LANGUAGES: dict[str, str] = {"pl": "Polish", "en": "English"}
"""Language code -> English name, as used in the translategemma template. v1: PL and EN only."""

TEAM_TONE_INSTRUCTION = (
    "Informal team message: casual and friendly, short sentences, first names, "
    "no stiff formulas or corporate phrases."
)


@dataclass(frozen=True)
class OllamaConfig:
    """``[ollama]`` table."""

    url: str = DEFAULT_OLLAMA_URL
    timeout: float = 120.0
    """Seconds for one /api/chat request (covers a cold start of the 27b model)."""
    keep_alive: str = "30m"
    """Sent with every request so the model stays loaded between shortcut presses."""
    temperature: float = 0.0
    num_ctx: int = 4096
    max_chars: int = 8000
    """Longer selections are refused with ``TextTooLong`` instead of being silently truncated."""


@dataclass(frozen=True)
class ModelsConfig:
    """``[models]`` table: the Ollama model per mode."""

    translate: str = "translategemma:12b"
    translate_quality: str = "translategemma:27b"
    """Used by ``llmtr translate --quality``."""
    fix: str = "gemma3"
    tone: str = "gemma3:12b"


@dataclass(frozen=True)
class LanguagesConfig:
    """``[languages]`` table: the translation pair.

    Text detected as ``native`` is translated to ``other``; everything else to ``native``.
    """

    native: str = "pl"
    other: str = "en"


@dataclass(frozen=True)
class KeyOverride:
    """One ``[[keys.override]]`` entry: copy/paste keys for specific apps."""

    app: tuple[str, ...]
    """App ids / WM classes, e.g. ``("org.gnome.Terminal", "kitty")``; case-insensitive."""
    copy: str
    paste: str


@dataclass(frozen=True)
class KeysConfig:
    """``[keys]`` table: keys llmtr *sends* (never triggers), plus timing."""

    copy: str = "ctrl+c"
    paste: str = "ctrl+v"
    start_delay: float = 0.25
    """Seconds to wait before sending the copy key, so the user can release Super+Alt."""
    copy_timeout: float = 1.0
    """Seconds to wait for the copied text to appear on the clipboard."""
    paste_delay: float = 0.3
    """Seconds to wait after the paste key before restoring the old clipboard."""
    override: tuple[KeyOverride, ...] = ()


@dataclass(frozen=True)
class TonePreset:
    """One tone preset: a name and the style instruction given to the model."""

    name: str
    instruction: str


TEAM_TONE = TonePreset(name="team", instruction=TEAM_TONE_INSTRUCTION)
"""The built-in default preset. Always available; a config preset named ``team`` replaces it."""


@dataclass(frozen=True)
class ToneConfig:
    """``[tone]`` table. ``presets`` is in cycling order and is never empty."""

    presets: tuple[TonePreset, ...] = (TEAM_TONE,)


@dataclass(frozen=True)
class NotifyConfig:
    """``[notify]`` table.

    ``enabled = false`` hides progress notifications ("Translating..."). Errors, the
    "Press Ctrl+V" fallback hint and the tone name after ``tone --next`` are always shown.
    """

    enabled: bool = True
    backend: str = "auto"
    """v2 (macOS): ``"auto"`` (= ``"hammerspoon"``), ``"hammerspoon"`` or ``"osascript"``. Ignored
    on Linux. Parsed from ``notify.backend``."""


@dataclass(frozen=True)
class LogConfig:
    """``[log]`` table: the run/error log in ``$XDG_STATE_HOME/llmtr/llmtr.log``."""

    enabled: bool = True
    """``false`` disables file logging entirely; no log file is created."""
    level: str = "info"
    """One of ``"debug"``, ``"info"``, ``"error"``; the ``LLMTR_LOG_LEVEL`` env overrides this."""


@dataclass(frozen=True)
class Config:
    """The whole parsed ``config.toml``."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    languages: LanguagesConfig = field(default_factory=LanguagesConfig)
    keys: KeysConfig = field(default_factory=KeysConfig)
    tone: ToneConfig = field(default_factory=ToneConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    log: LogConfig = field(default_factory=LogConfig)


@dataclass(frozen=True)
class State:
    """The whole ``state.toml``."""

    tone: str = TEAM_TONE.name


# --- paths ---------------------------------------------------------------------------------


def config_path(env: Mapping[str, str] | None = None) -> Path:
    """``$XDG_CONFIG_HOME/llmtr/config.toml``; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    base = env.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "llmtr" / "config.toml"


def state_path(env: Mapping[str, str] | None = None) -> Path:
    """``$XDG_STATE_HOME/llmtr/state.toml``; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    base = env.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "llmtr" / "state.toml"


def cache_dir(env: Mapping[str, str] | None = None) -> Path:
    """``$XDG_CACHE_HOME/llmtr``; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    base = env.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "llmtr"


# --- config ------------------------------------------------------------------------------


def normalize_ollama_url(value: str) -> str:
    """Turn an ``OLLAMA_HOST``-style value into a base URL without a trailing slash.

    Rules: add ``http://`` when there is no scheme; add port ``11434`` when there is none;
    the bind-all hosts ``0.0.0.0`` and ``[::]`` become ``127.0.0.1`` (a server bind address is
    not a client address). Examples: ``"localhost"`` -> ``"http://localhost:11434"``,
    ``"http://host.docker.internal:11434/"`` -> ``"http://host.docker.internal:11434"``.
    """
    from urllib.parse import urlsplit, urlunsplit

    value = value.strip()
    if "://" not in value:
        value = f"http://{value}"
    parts = urlsplit(value)
    hostname = parts.hostname or ""
    if hostname in ("0.0.0.0", "::"):
        hostname = "127.0.0.1"
    port = parts.port if parts.port is not None else 11434
    netloc = f"{hostname}:{port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, netloc, path, "", ""))


def _require_table(data: Mapping[str, Any], key: str, source: Path | str) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ConfigError(source, f"'{key}' must be a table")
    return value


def _as_str(table: Mapping[str, Any], key: str, default: str, path: str, source: Path | str) -> str:
    if key not in table:
        return default
    value = table[key]
    if not isinstance(value, str):
        raise ConfigError(source, f"'{path}' must be a string")
    return value


def _as_number(
    table: Mapping[str, Any],
    key: str,
    default: float,
    path: str,
    source: Path | str,
    *,
    positive: bool = False,
) -> float:
    if key not in table:
        return default
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(source, f"'{path}' must be a number")
    value = float(value)
    if positive and value <= 0:
        raise ConfigError(source, f"'{path}' must be > 0")
    return value


def _as_int(
    table: Mapping[str, Any],
    key: str,
    default: int,
    path: str,
    source: Path | str,
    *,
    positive: bool = False,
) -> int:
    if key not in table:
        return default
    value = table[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(source, f"'{path}' must be an integer")
    if positive and value <= 0:
        raise ConfigError(source, f"'{path}' must be > 0")
    return value


def _as_bool(
    table: Mapping[str, Any], key: str, default: bool, path: str, source: Path | str
) -> bool:
    if key not in table:
        return default
    value = table[key]
    if not isinstance(value, bool):
        raise ConfigError(source, f"'{path}' must be a boolean")
    return value


def _parse_key_overrides(
    keys_table: Mapping[str, Any], source: Path | str
) -> tuple[KeyOverride, ...]:
    raw = keys_table.get("override", [])
    if not isinstance(raw, list):
        raise ConfigError(source, "'keys.override' must be a list")
    overrides: list[KeyOverride] = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ConfigError(source, f"'keys.override[{i}]' must be a table")
        app = item.get("app")
        if not isinstance(app, list) or not all(isinstance(a, str) for a in app):
            raise ConfigError(source, f"'keys.override[{i}].app' must be a list of strings")
        copy = item.get("copy")
        paste = item.get("paste")
        if not isinstance(copy, str) or not isinstance(paste, str):
            raise ConfigError(source, f"'keys.override[{i}]' requires 'copy' and 'paste'")
        overrides.append(KeyOverride(app=tuple(app), copy=copy, paste=paste))
    return tuple(overrides)


def _parse_tone_presets(
    tone_table: Mapping[str, Any], source: Path | str
) -> tuple[TonePreset, ...]:
    raw = tone_table.get("preset", [])
    if not isinstance(raw, list):
        raise ConfigError(source, "'tone.preset' must be a list")
    presets: list[TonePreset] = [TEAM_TONE]
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ConfigError(source, f"'tone.preset[{i}]' must be a table")
        name = item.get("name")
        instruction = item.get("instruction")
        if not isinstance(name, str) or not isinstance(instruction, str):
            raise ConfigError(source, f"'tone.preset[{i}]' requires 'name' and 'instruction'")
        preset = TonePreset(name=name, instruction=instruction)
        for j, existing in enumerate(presets):
            if existing.name == name:
                presets[j] = preset
                break
        else:
            presets.append(preset)
    return tuple(presets)


def parse_config(
    data: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    source: Path | str = "config.toml",
    *,
    platform: Platform = "linux",
) -> Config:
    """Build a ``Config`` from already-parsed TOML data (pure; the unit-test entry point).

    ``platform`` only changes the defaults of ``keys.copy``/``keys.paste``/``keys.start_delay``
    when the user did not set them (macOS: ``cmd+c``/``cmd+v``/``0``); a value in the file
    always wins. ``notify.backend`` must be ``auto``, ``hammerspoon`` or ``osascript``.

    Missing keys take dataclass defaults; unknown keys are ignored. A non-empty ``OLLAMA_HOST``
    in ``env`` overrides ``[ollama] url``; the final URL goes through ``normalize_ollama_url``.
    ``[[tone.preset]]`` entries are appended after the built-in ``team`` preset, and an entry
    named ``team`` replaces the built-in one in place.

    Raises ``ConfigError(source, ...)`` for a wrong type, an unsupported language code, a
    language pair with ``native == other``, a non-positive timeout/max_chars, or an Ollama URL
    whose scheme is not ``http``/``https``.
    """
    env = env if env is not None else os.environ
    if not isinstance(data, Mapping):
        raise ConfigError(source, "top-level config must be a table")

    ollama_table = _require_table(data, "ollama", source)
    url = _as_str(ollama_table, "url", DEFAULT_OLLAMA_URL, "ollama.url", source)
    url_source = "[ollama] url"
    host_env = env.get(OLLAMA_HOST_ENV, "")
    if host_env:
        url = host_env
        url_source = OLLAMA_HOST_ENV
    url = normalize_ollama_url(url)
    scheme = url.split("://", 1)[0]
    if scheme.lower() not in ("http", "https"):
        raise ConfigError(
            source,
            f"unsupported Ollama URL scheme '{scheme}' in {url_source} (use http or https)",
        )
    ollama = OllamaConfig(
        url=url,
        timeout=_as_number(
            ollama_table, "timeout", OllamaConfig.timeout, "ollama.timeout", source, positive=True
        ),
        keep_alive=_as_str(
            ollama_table, "keep_alive", OllamaConfig.keep_alive, "ollama.keep_alive", source
        ),
        temperature=_as_number(
            ollama_table, "temperature", OllamaConfig.temperature, "ollama.temperature", source
        ),
        num_ctx=_as_int(ollama_table, "num_ctx", OllamaConfig.num_ctx, "ollama.num_ctx", source),
        max_chars=_as_int(
            ollama_table,
            "max_chars",
            OllamaConfig.max_chars,
            "ollama.max_chars",
            source,
            positive=True,
        ),
    )

    models_table = _require_table(data, "models", source)
    models = ModelsConfig(
        translate=_as_str(
            models_table, "translate", ModelsConfig.translate, "models.translate", source
        ),
        translate_quality=_as_str(
            models_table,
            "translate_quality",
            ModelsConfig.translate_quality,
            "models.translate_quality",
            source,
        ),
        fix=_as_str(models_table, "fix", ModelsConfig.fix, "models.fix", source),
        tone=_as_str(models_table, "tone", ModelsConfig.tone, "models.tone", source),
    )

    languages_table = _require_table(data, "languages", source)
    native = _as_str(languages_table, "native", LanguagesConfig.native, "languages.native", source)
    other = _as_str(languages_table, "other", LanguagesConfig.other, "languages.other", source)
    if native not in SUPPORTED_LANGUAGES:
        raise ConfigError(source, f"unsupported language code '{native}'")
    if other not in SUPPORTED_LANGUAGES:
        raise ConfigError(source, f"unsupported language code '{other}'")
    if native == other:
        raise ConfigError(source, "'languages.native' and 'languages.other' must differ")
    languages = LanguagesConfig(native=native, other=other)

    keys_table = _require_table(data, "keys", source)
    key_default = key_defaults(platform)
    keys = KeysConfig(
        copy=_as_str(keys_table, "copy", key_default.copy, "keys.copy", source),
        paste=_as_str(keys_table, "paste", key_default.paste, "keys.paste", source),
        start_delay=_as_number(
            keys_table, "start_delay", key_default.start_delay, "keys.start_delay", source
        ),
        copy_timeout=_as_number(
            keys_table, "copy_timeout", KeysConfig.copy_timeout, "keys.copy_timeout", source
        ),
        paste_delay=_as_number(
            keys_table, "paste_delay", KeysConfig.paste_delay, "keys.paste_delay", source
        ),
        override=_parse_key_overrides(keys_table, source),
    )

    tone_table = _require_table(data, "tone", source)
    tone = ToneConfig(presets=_parse_tone_presets(tone_table, source))

    notify_table = _require_table(data, "notify", source)
    notify = NotifyConfig(
        enabled=_as_bool(notify_table, "enabled", NotifyConfig.enabled, "notify.enabled", source),
        backend=_as_str(notify_table, "backend", NotifyConfig.backend, "notify.backend", source),
    )
    if notify.backend not in NOTIFY_BACKENDS:
        raise ConfigError(source, f"'notify.backend' must be one of {', '.join(NOTIFY_BACKENDS)}")

    log_table = _require_table(data, "log", source)
    level = _as_str(log_table, "level", LogConfig.level, "log.level", source)
    level_env = env.get(LOG_LEVEL_ENV, "")
    if level_env:
        level = level_env
    level = level.strip().lower()
    if level not in _LOG_LEVELS:
        raise ConfigError(source, f"'log.level' must be one of {sorted(_LOG_LEVELS)}")
    log = LogConfig(
        enabled=_as_bool(log_table, "enabled", LogConfig.enabled, "log.enabled", source),
        level=level,
    )

    return Config(
        ollama=ollama,
        models=models,
        languages=languages,
        keys=keys,
        tone=tone,
        notify=notify,
        log=log,
    )


def load_config(
    path: Path | None = None,
    env: Mapping[str, str] | None = None,
    *,
    platform: Platform = "linux",
) -> Config:
    """Read ``path`` (default ``config_path(env)``) and call ``parse_config`` with ``platform``.

    A missing file gives the defaults (still applying ``OLLAMA_HOST``). Invalid TOML raises
    ``ConfigError``.
    """
    env = env if env is not None else os.environ
    cfg_path = path if path is not None else config_path(env)
    if not cfg_path.exists():
        return parse_config({}, env=env, source=cfg_path, platform=platform)
    try:
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(cfg_path, f"invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(cfg_path, str(exc)) from exc
    return parse_config(data, env=env, source=cfg_path, platform=platform)


# --- state & tone ------------------------------------------------------------------------


def load_state(path: Path | None = None) -> State:
    """Read ``state.toml``. A missing or unreadable file gives ``State()`` (never raises)."""
    state_file = path if path is not None else state_path()
    try:
        with state_file.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return State()
    tone = data.get("tone")
    if not isinstance(tone, str):
        return State()
    return State(tone=tone)


def save_state(state: State, path: Path | None = None) -> None:
    """Write ``state.toml`` atomically (temp file + ``os.replace``), creating parent dirs.

    Format: a single line ``tone = "<name>"`` with TOML basic-string escaping.
    """
    state_file = path if path is not None else state_path()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    escaped = state.tone.replace("\\", "\\\\").replace('"', '\\"')
    tmp_file = state_file.with_name(f"{state_file.name}.tmp{os.getpid()}")
    tmp_file.write_text(f'tone = "{escaped}"\n', encoding="utf-8")
    os.replace(tmp_file, state_file)


def current_tone(config: Config, state: State) -> TonePreset:
    """The preset named by ``state.tone``, or the first preset if that name is unknown."""
    for preset in config.tone.presets:
        if preset.name == state.tone:
            return preset
    return config.tone.presets[0]


def next_tone(config: Config, state: State) -> TonePreset:
    """The preset after the current one in ``config.tone.presets``, wrapping around.

    With a single preset it returns that preset.
    """
    presets = config.tone.presets
    index = presets.index(current_tone(config, state))
    return presets[(index + 1) % len(presets)]


# --- cache -------------------------------------------------------------------------------


def save_last_result(text: str, directory: Path | None = None) -> Path:
    """Write ``text`` to ``<directory or cache_dir()>/last.txt`` and return the path."""
    dir_path = directory if directory is not None else cache_dir()
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / "last.txt"
    path.write_text(text, encoding="utf-8")
    return path


__all__ = [
    "DEFAULT_OLLAMA_URL",
    "LOG_LEVEL_ENV",
    "NOTIFY_BACKENDS",
    "OLLAMA_HOST_ENV",
    "SUPPORTED_LANGUAGES",
    "TEAM_TONE",
    "TEAM_TONE_INSTRUCTION",
    "Config",
    "KeyOverride",
    "KeysConfig",
    "LanguagesConfig",
    "LogConfig",
    "ModelsConfig",
    "NotifyConfig",
    "OllamaConfig",
    "State",
    "ToneConfig",
    "TonePreset",
    "cache_dir",
    "config_path",
    "current_tone",
    "load_config",
    "load_state",
    "next_tone",
    "normalize_ollama_url",
    "parse_config",
    "save_last_result",
    "save_state",
    "state_path",
]
