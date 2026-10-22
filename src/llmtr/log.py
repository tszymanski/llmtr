"""Run and error log, written to a file so GNOME shortcut failures are diagnosable (owner: M6).

``$XDG_STATE_HOME/llmtr/llmtr.log`` (default ``~/.local/state/llmtr/llmtr.log``), stdlib
``logging`` with a 1 MB / 1 backup ``RotatingFileHandler``. ``cli.py`` calls ``setup_logging``
twice: once with ``None`` before the config loads (so a bad config file is still logged), then
again with ``config.log`` once it has. Never logs selected text, model output or clipboard
contents -- lengths only.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from llmtr.config import LogConfig

LOGGER_NAME = "llmtr"

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "error": logging.ERROR}

_FORMAT = "%(asctime)s %(levelname)s [%(process)d] %(message)s"

_MAX_BYTES = 1_000_000
_BACKUP_COUNT = 1


def log_path(env: Mapping[str, str] | None = None) -> Path:
    """``$XDG_STATE_HOME/llmtr/llmtr.log``; ``env`` defaults to ``os.environ``."""
    env = env if env is not None else os.environ
    base = env.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "llmtr" / "llmtr.log"


def setup_logging(
    config: LogConfig | None, env: Mapping[str, str] | None = None
) -> logging.Logger | None:
    """(Re)configure the ``llmtr`` logger and return it, or ``None`` when logging is off.

    ``config=None`` uses ``LogConfig()`` defaults (enabled, info) -- used before the real config
    has loaded. Any previously attached handler is removed first, so calling this twice (once
    with defaults, once with the loaded config) never duplicates log lines. If the log file can't
    be opened (read-only directory, missing permissions, ...), logging is silently disabled
    instead of raising: a broken log must never stop llmtr from working.
    """
    cfg = config if config is not None else LogConfig()
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.propagate = False

    if not cfg.enabled:
        return None

    path = log_path(env)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(_LEVELS.get(cfg.level, logging.INFO))
    return logger


@dataclass(frozen=True)
class RunRecord:
    """One run's summary, logged as a single INFO line at the end (``cli.py`` fills it in).

    Never carries the selected text, the model output or clipboard contents -- lengths only.
    """

    mode: str
    outcome: str = "ok"
    """``"ok"``, ``"cancelled"``, or ``f"error:{type(exc).__name__}"``."""
    model: str | None = None
    duration: float = 0.0
    input_length: int = 0
    output_length: int = 0
    used_keystrokes: bool | None = None
    """``None`` when the run never reached the point of capturing a selection."""
    flags: tuple[str, ...] = field(default_factory=tuple)
    """e.g. ``("quality",)``, ``("stdin",)``."""

    def __str__(self) -> str:
        parts = [f"mode={self.mode}"]
        parts.extend(f"--{flag}" for flag in self.flags)
        if self.model:
            parts.append(f"model={self.model}")
        parts.append(f"outcome={self.outcome}")
        parts.append(f"duration={self.duration:.3f}s")
        parts.append(f"input_len={self.input_length}")
        parts.append(f"output_len={self.output_length}")
        if self.used_keystrokes is not None:
            parts.append(f"keystrokes={self.used_keystrokes}")
        return " ".join(parts)


__all__ = ["LOGGER_NAME", "RunRecord", "log_path", "setup_logging"]
