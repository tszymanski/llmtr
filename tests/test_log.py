"""Unit tests for llmtr.log (owner: M6).

Every test points ``XDG_STATE_HOME`` at ``tmp_path``, never the real home directory.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from llmtr import log
from llmtr.config import LogConfig


@pytest.fixture(autouse=True)
def _reset_logger():
    """``setup_logging`` mutates the shared ``llmtr`` logger; leave it clean for other tests."""
    yield
    logger = logging.getLogger(log.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


# --- log_path ------------------------------------------------------------------------------


def test_log_path_uses_xdg_state_home() -> None:
    env = {"XDG_STATE_HOME": "/tmp/xdg-state"}
    assert log.log_path(env) == Path("/tmp/xdg-state/llmtr/llmtr.log")


def test_log_path_falls_back_to_home_local_state() -> None:
    assert log.log_path({}) == Path.home() / ".local" / "state" / "llmtr" / "llmtr.log"


# --- setup_logging ---------------------------------------------------------------------------


def test_setup_logging_creates_log_directory_and_file(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(LogConfig(), env)
    assert logger is not None
    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()
    assert (tmp_path / "llmtr" / "llmtr.log").exists()


def test_setup_logging_disabled_writes_nothing(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(LogConfig(enabled=False), env)
    assert logger is None
    assert not (tmp_path / "llmtr" / "llmtr.log").exists()
    assert not (tmp_path / "llmtr").exists()


def test_setup_logging_none_config_uses_defaults(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(None, env)
    assert logger is not None
    assert logger.getEffectiveLevel() == logging.INFO


@pytest.mark.parametrize(
    ("level", "expected"),
    [("debug", logging.DEBUG), ("info", logging.INFO), ("error", logging.ERROR)],
)
def test_setup_logging_level(tmp_path: Path, level: str, expected: int) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(LogConfig(level=level), env)
    assert logger is not None
    assert logger.getEffectiveLevel() == expected


def test_setup_logging_rotation_settings(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(LogConfig(), env)
    assert logger is not None
    (handler,) = logger.handlers
    assert handler.maxBytes == 1_000_000
    assert handler.backupCount == 1


def test_setup_logging_format(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    logger = log.setup_logging(LogConfig(), env)
    assert logger is not None
    logger.error("boom")
    for handler in logger.handlers:
        handler.flush()
    line = (tmp_path / "llmtr" / "llmtr.log").read_text(encoding="utf-8").strip()
    # "2026-10-05 23:41:07,123 ERROR [12345] boom"
    import re

    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} ERROR \[\d+\] boom$", line)


def test_setup_logging_unwritable_dir_falls_back_silently(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir(mode=0o400)
    env = {"XDG_STATE_HOME": str(blocked)}
    try:
        logger = log.setup_logging(LogConfig(), env)
        assert logger is None
    finally:
        blocked.chmod(0o700)


def test_setup_logging_second_call_does_not_duplicate_handlers(tmp_path: Path) -> None:
    env = {"XDG_STATE_HOME": str(tmp_path)}
    log.setup_logging(LogConfig(), env)
    logger = log.setup_logging(LogConfig(), env)
    assert logger is not None
    assert len(logger.handlers) == 1


# --- RunRecord ---------------------------------------------------------------------------------


def test_run_record_str_includes_fields_and_flags() -> None:
    record = log.RunRecord(
        mode="translate",
        outcome="ok",
        model="translategemma:12b",
        duration=1.5,
        input_length=20,
        output_length=18,
        used_keystrokes=True,
        flags=("quality",),
    )
    text = str(record)
    assert "mode=translate" in text
    assert "--quality" in text
    assert "model=translategemma:12b" in text
    assert "outcome=ok" in text
    assert "duration=1.500s" in text
    assert "input_len=20" in text
    assert "output_len=18" in text
    assert "keystrokes=True" in text


def test_run_record_str_never_includes_raw_text() -> None:
    record = log.RunRecord(mode="fix", outcome="ok", input_length=5, output_length=5)
    assert "Nothing is copied" not in str(record)
