"""End-to-end tests for llmtr.cli (owner: M4).

``run_shortcut`` is tested directly with fakes injected through its keyword-only parameters
(``clipboard``, ``keys``, ``client``, ``lock``, ``sleep``/``monotonic``, ``kill``); ``main`` is
tested the same way plus by monkeypatching the module-level factories it calls
(``make_clipboard``, ``YdotoolKeySender``, ``OllamaClient``, ``NotifySendNotifier``) so no test
touches a real desktop tool, Ollama, or sends a real signal to another process.
"""

from __future__ import annotations

import io
import logging
import os
import signal
import sys
from collections.abc import Callable

import pytest

from llmtr import cli, log
from llmtr.backends import MACOS_PASTE_HINT, Desktop
from llmtr.config import (
    Config,
    LogConfig,
    NotifyConfig,
    OllamaConfig,
    State,
    load_state,
    parse_config,
    save_state,
)
from llmtr.engine import Mode
from llmtr.errors import (
    Cancelled,
    ClipboardUnavailable,
    KeySendError,
    MacKeySendError,
    ModelMissing,
    OllamaTimeout,
    OllamaUnavailable,
)
from llmtr.fakes import FakeChatClient, FakeClipboard, FakeClock, FakeKeySender, FakeNotifier
from llmtr.lock import RunLock


@pytest.fixture(autouse=True)
def _isolated_xdg(tmp_path, monkeypatch):
    """Every config/state/cache/lock path lands under ``tmp_path``, never the real home dir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))


@pytest.fixture(autouse=True)
def _reset_log_handlers():
    """``log.setup_logging`` mutates the shared ``llmtr`` logger; leave it clean afterwards."""
    yield
    logger = logging.getLogger(log.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _log_file(tmp_path):
    return tmp_path / "state" / "llmtr" / "llmtr.log"


class FlakyKeySender:
    """A ``KeySender`` that copies normally but fails on one specific combo."""

    def __init__(self, clipboard: FakeClipboard, copy_combo: str, fail_combo: str) -> None:
        self._clipboard = clipboard
        self._copy_combo = copy_combo
        self._fail_combo = fail_combo
        self.sent: list[str] = []

    def available(self) -> bool:
        return True

    def send(self, combo: str) -> None:
        self.sent.append(combo)
        if combo == self._fail_combo:
            raise KeySendError("boom")
        if combo == self._copy_combo:
            self._clipboard.set_text("selected text")


def _selecting_keys(clipboard: FakeClipboard, selected: str, copy: str = "ctrl+c") -> FakeKeySender:
    return FakeKeySender(on_send=lambda c: clipboard.set_text(selected) if c == copy else None)


# --- run_shortcut: success paths --------------------------------------------------------------


def test_run_shortcut_translate_success_pastes_and_restores_clipboard() -> None:
    clip = FakeClipboard("old clipboard")
    keys = _selecting_keys(clip, "Cześć, jak się masz?")
    chat = FakeChatClient("Hello, how are you?")
    notifier = FakeNotifier()
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.TRANSLATE,
        Config(),
        notifier,
        clipboard=clip,
        keys=keys,
        client=chat,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_OK
    assert clip.get_text() == "old clipboard"
    assert keys.sent == ["ctrl+c", "ctrl+v"]
    assert chat.calls[0].model == Config().models.translate
    assert [n.summary for n in notifier.shown] == ["Translating PL → EN…"]


def test_run_shortcut_fix_mode_uses_fix_model() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "This have a typo.")
    chat = FakeChatClient("This has a typo.")
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_OK
    assert chat.calls[0].model == Config().models.fix
    assert [n.summary for n in notifier.shown] == ["Fixing grammar…"]


def test_run_shortcut_tone_mode_uses_current_tone_preset() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "Hey, status update pls")
    chat = FakeChatClient("Hey team, here's the update")
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.TONE, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_OK
    assert chat.calls[0].model == Config().models.tone
    assert [n.summary for n in notifier.shown] == ["Rewriting: team…"]


def test_run_shortcut_quality_flag_selects_quality_model() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "Hello")
    chat = FakeChatClient("Cześć")
    notifier = FakeNotifier()

    code = cli.run_shortcut(
        Mode.TRANSLATE, Config(), notifier, clipboard=clip, keys=keys, client=chat, quality=True
    )

    assert code == cli.EXIT_OK
    assert chat.calls[0].model == Config().models.translate_quality


def test_run_shortcut_explicit_model_wins_over_quality() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "Hello")
    chat = FakeChatClient("Cześć")
    notifier = FakeNotifier()

    code = cli.run_shortcut(
        Mode.TRANSLATE,
        Config(),
        notifier,
        clipboard=clip,
        keys=keys,
        client=chat,
        quality=True,
        model="custom-model",
    )

    assert code == cli.EXIT_OK
    assert chat.calls[0].model == "custom-model"


def test_run_shortcut_fallback_without_ydotool_leaves_result_on_clipboard() -> None:
    clip = FakeClipboard("already copied by hand")
    keys = FakeKeySender(is_available=False)
    chat = FakeChatClient("already copied by hand, fixed")
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_OK
    assert keys.sent == []
    assert clip.get_text() == "already copied by hand, fixed"
    assert [n.summary for n in notifier.shown] == [
        "Fixing grammar…",
        "Result copied. Press Ctrl+V to paste.",
    ]


def test_run_shortcut_paste_key_failure_leaves_result_on_clipboard() -> None:
    clip = FakeClipboard("old")
    keys = FlakyKeySender(clip, copy_combo="ctrl+c", fail_combo="ctrl+v")
    chat = FakeChatClient("fixed text")
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_OK
    assert keys.sent == ["ctrl+c", "ctrl+v"]
    assert clip.get_text() == "fixed text"
    assert [n.summary for n in notifier.shown] == [
        "Fixing grammar…",
        "Result copied. Press Ctrl+V to paste.",
    ]


def test_run_shortcut_progress_notification_skipped_when_disabled() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "fix me")
    chat = FakeChatClient("fixed")
    notifier = FakeNotifier()

    code = cli.run_shortcut(
        Mode.FIX,
        Config(notify=NotifyConfig(enabled=False)),
        notifier,
        clipboard=clip,
        keys=keys,
        client=chat,
    )

    assert code == cli.EXIT_OK
    assert notifier.shown == []


# --- run_shortcut: error paths (architecture section 7) --------------------------------------


def test_run_shortcut_ollama_down_restores_clipboard_and_notifies_critical() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient(OllamaUnavailable("http://localhost:11434"))
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert [n.summary for n in notifier.shown] == [
        "Fixing grammar…",
        "Can't reach Ollama at http://localhost:11434. Is it running?",
    ]
    assert notifier.shown[-1].urgency == "critical"


def test_run_shortcut_model_missing_restores_clipboard_and_notifies_critical() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient(ModelMissing("gemma3"))
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == "Model gemma3 is not installed. Run: ollama pull gemma3"
    assert notifier.shown[-1].urgency == "critical"


def test_run_shortcut_timeout_restores_clipboard_and_notifies_critical() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient(OllamaTimeout(120.0))
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == "Ollama did not answer within 120 s. Try again."


def test_run_shortcut_empty_selection_restores_clipboard_and_notifies_critical() -> None:
    clip = FakeClipboard("old")
    keys = FakeKeySender()  # on_send does nothing: clipboard stays cleared -> timeout
    chat = FakeChatClient("unused")
    notifier = FakeNotifier()
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.FIX,
        Config(),
        notifier,
        clipboard=clip,
        keys=keys,
        client=chat,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert chat.calls == []
    assert [n.summary for n in notifier.shown] == ["No text selected. Select some text first."]
    assert notifier.shown[-1].urgency == "critical"


def test_run_shortcut_key_send_error_on_copy_restores_clipboard() -> None:
    clip = FakeClipboard("old")
    keys = FakeKeySender(fail=KeySendError("boom"))
    chat = FakeChatClient("unused")
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == "Could not send keystrokes. Is ydotoold running?"


def test_run_shortcut_text_too_long_restores_clipboard() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "a very long selection")
    chat = FakeChatClient("unused")
    notifier = FakeNotifier()
    cfg = Config(ollama=OllamaConfig(max_chars=5))

    code = cli.run_shortcut(Mode.FIX, cfg, notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert chat.calls == []
    assert notifier.shown[-1].summary.startswith("Selection too long")


def test_run_shortcut_model_output_empty_restores_clipboard() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient("   ")  # strips to nothing -> OllamaError
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == "The model returned no text."


def test_run_shortcut_no_clipboard_tool_notifies_critical(monkeypatch) -> None:
    def _raise(env=None):
        raise ClipboardUnavailable("no wl-clipboard or xclip")

    monkeypatch.setattr(cli, "make_clipboard", _raise)
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, keys=FakeKeySender())

    assert code == cli.EXIT_ERROR
    assert notifier.shown[-1].summary == "No working clipboard tool. Install wl-clipboard."


def test_run_shortcut_cancelled_mid_job_restores_clipboard_normal_urgency() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient(Cancelled())
    notifier = FakeNotifier()

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat)

    assert code == cli.EXIT_OK
    assert clip.get_text() == "old"
    assert [n.summary for n in notifier.shown] == ["Fixing grammar…", "Cancelled."]
    assert notifier.shown[-1].urgency == "normal"


def test_run_shortcut_second_press_cancels_first_without_starting_job() -> None:
    first = RunLock(cli.default_lock_path())
    assert first.acquire() is True
    sent: list[tuple[int, int]] = []
    notifier = FakeNotifier()

    code = cli.run_shortcut(
        Mode.TRANSLATE, Config(), notifier, kill=lambda pid, sig: sent.append((pid, sig))
    )

    assert code == cli.EXIT_OK
    assert sent == [(os.getpid(), signal.SIGTERM)]
    assert notifier.shown == []
    first.release()


# --- main(): dispatch, --stdin, tone --next, usage/config errors -----------------------------


def test_main_stdin_translate_prints_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "OllamaClient", lambda url, timeout: FakeChatClient("Hello"))
    monkeypatch.setattr(sys, "stdin", io.StringIO("Cześć"))

    code = cli.main(["translate", "--stdin"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "Hello"


def test_main_stdin_translate_quality_selects_27b_model(monkeypatch) -> None:
    seen_models: list[str] = []

    class _Client:
        def __init__(self, url: str, timeout: float) -> None:
            pass

        def chat(self, model, messages, *, options=None, keep_alive=None):
            seen_models.append(model)
            return "Przetłumaczone"

    monkeypatch.setattr(cli, "OllamaClient", _Client)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Hello there"))

    code = cli.main(["translate", "--quality", "--stdin"])

    assert code == cli.EXIT_OK
    assert seen_models == [Config().models.translate_quality]


def test_main_stdin_empty_text_prints_error_to_stderr(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("   "))

    code = cli.main(["fix", "--stdin"])

    assert code == cli.EXIT_ERROR
    assert "No text selected" in capsys.readouterr().err


def test_main_tone_next_stdin_is_usage_error(capsys) -> None:
    code = cli.main(["tone", "--next", "--stdin"])

    assert code == cli.EXIT_USAGE
    assert capsys.readouterr().err


def test_main_tone_next_single_preset_notes_only_preset(monkeypatch) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)

    code = cli.main(["tone", "--next"])

    assert code == cli.EXIT_OK
    assert notifier.shown[-1].summary == "Tone: team (only preset)"
    assert load_state().tone == "team"


def test_main_tone_next_cycles_between_two_presets(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    config_file = tmp_path / "config.toml"
    config_file.write_text('[[tone.preset]]\nname = "formal"\ninstruction = "Be formal."\n')

    first = cli.main(["--config", str(config_file), "tone", "--next"])
    second = cli.main(["--config", str(config_file), "tone", "--next"])

    assert (first, second) == (cli.EXIT_OK, cli.EXIT_OK)
    assert [n.summary for n in notifier.shown] == ["Tone: formal", "Tone: team"]
    assert load_state().tone == "team"


def _three_preset_config_file(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[[tone.preset]]\nname = "formal"\ninstruction = "Be formal."\n\n'
        '[[tone.preset]]\nname = "concise"\ninstruction = "Be short."\n'
    )
    return config_file


def test_main_tone_show_notifies_name_index_and_instruction(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    config_file = _three_preset_config_file(tmp_path)
    save_state(State(tone="formal"))

    code = cli.main(["--config", str(config_file), "tone", "--show"])

    assert code == cli.EXIT_OK
    assert notifier.shown[-1].summary == "Tone: formal (2/3)"
    assert notifier.shown[-1].body == "Be formal."
    assert load_state().tone == "formal"  # state file untouched by --show


def test_main_tone_show_falls_back_when_stored_tone_is_unknown(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    config_file = _three_preset_config_file(tmp_path)
    save_state(State(tone="does-not-exist"))

    code = cli.main(["--config", str(config_file), "tone", "--show"])

    assert code == cli.EXIT_OK
    assert notifier.shown[-1].summary == "Tone: team (1/3)"
    assert notifier.shown[-1].body == cli.current_tone(Config(), State()).instruction
    assert load_state().tone == "does-not-exist"  # still untouched, including the unknown name


def test_main_tone_show_stdin_prints_to_stdout(tmp_path, capsys) -> None:
    config_file = _three_preset_config_file(tmp_path)
    save_state(State(tone="concise"))

    code = cli.main(["--config", str(config_file), "tone", "--show", "--stdin"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "concise (3/3): Be short.\n"


def test_main_tone_show_and_next_together_is_usage_error(capsys) -> None:
    code = cli.main(["tone", "--show", "--next"])

    assert code == cli.EXIT_USAGE
    assert capsys.readouterr().err


def test_main_tone_show_does_not_touch_clipboard_keys_or_client(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    config_file = _three_preset_config_file(tmp_path)

    def _boom(*args, **kwargs):
        raise AssertionError("tone --show must not touch this")

    monkeypatch.setattr(cli, "make_clipboard", _boom)
    monkeypatch.setattr(cli, "YdotoolKeySender", _boom)
    monkeypatch.setattr(cli, "OllamaClient", _boom)

    code = cli.main(["--config", str(config_file), "tone", "--show"])

    assert code == cli.EXIT_OK
    assert notifier.shown[-1].summary == "Tone: team (1/3)"


def test_main_bad_config_notifies_and_returns_error(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    bad_config = tmp_path / "bad.toml"
    bad_config.write_text("ollama = 5\n")

    code = cli.main(["--config", str(bad_config), "fix"])

    assert code == cli.EXIT_ERROR
    assert "Config error" in notifier.shown[-1].summary
    assert notifier.shown[-1].urgency == "critical"


def test_main_bad_config_writes_error_to_log(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    bad_config = tmp_path / "bad.toml"
    bad_config.write_text("ollama = 5\n")

    code = cli.main(["--config", str(bad_config), "fix"])

    assert code == cli.EXIT_ERROR
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "ConfigError" in log_text
    assert "ollama" in log_text


def test_main_stdin_bad_config_prints_to_stderr_not_notification(
    monkeypatch, tmp_path, capsys
) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    bad_config = tmp_path / "bad.toml"
    bad_config.write_text("ollama = 5\n")

    code = cli.main(["--config", str(bad_config), "fix", "--stdin"])

    assert code == cli.EXIT_ERROR
    assert "Config error" in capsys.readouterr().err
    assert notifier.shown == []


def test_main_fix_mode_end_to_end_with_monkeypatched_factories(monkeypatch) -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "txt to fix")
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "make_clipboard", lambda: clip)
    monkeypatch.setattr(cli, "YdotoolKeySender", lambda: keys)
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)
    monkeypatch.setattr(cli, "OllamaClient", lambda url, timeout: FakeChatClient("fixed txt"))

    code = cli.main(["fix"])

    assert code == cli.EXIT_OK
    assert clip.get_text() == "old"
    assert keys.sent == ["ctrl+c", "ctrl+v"]
    assert [n.summary for n in notifier.shown] == ["Fixing grammar…"]


def test_main_usage_error_bad_flag_returns_exit_usage(capsys) -> None:
    code = cli.main(["translate", "--not-a-real-flag"])

    assert code == cli.EXIT_USAGE
    assert capsys.readouterr().err


# --- logging (M6): run log, error log, unexpected exceptions, `llmtr log` --------------------


def test_run_shortcut_llmtr_error_writes_error_log_with_detail(monkeypatch, tmp_path) -> None:
    def _raise(env=None):
        raise ClipboardUnavailable("Nothing is copied")

    monkeypatch.setattr(cli, "make_clipboard", _raise)
    notifier = FakeNotifier()
    logger = log.setup_logging(LogConfig())

    code = cli.run_shortcut(Mode.FIX, Config(), notifier, keys=FakeKeySender(), logger=logger)

    assert code == cli.EXIT_ERROR
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "ERROR" in log_text
    assert "ClipboardUnavailable" in log_text
    assert "Nothing is copied" in log_text


def test_run_shortcut_unexpected_exception_logged_clipboard_restored_notifies_log_path(
    tmp_path,
) -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "some text")
    chat = FakeChatClient(RuntimeError("boom"))
    notifier = FakeNotifier()
    logger = log.setup_logging(LogConfig())

    code = cli.run_shortcut(
        Mode.FIX, Config(), notifier, clipboard=clip, keys=keys, client=chat, logger=logger
    )

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == f"Unexpected error — see {log.log_path()}"
    assert notifier.shown[-1].urgency == "critical"
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "RuntimeError" in log_text
    assert "boom" in log_text
    assert "Traceback" in log_text


def test_run_shortcut_success_writes_info_line_without_sample_text(tmp_path) -> None:
    clip = FakeClipboard("old clipboard")
    sample_text = "Cześć, jak się masz dzisiaj?"
    keys = _selecting_keys(clip, sample_text)
    reply = "Hello, how are you today?"
    chat = FakeChatClient(reply)
    notifier = FakeNotifier()
    logger = log.setup_logging(LogConfig())

    code = cli.run_shortcut(
        Mode.TRANSLATE, Config(), notifier, clipboard=clip, keys=keys, client=chat, logger=logger
    )

    assert code == cli.EXIT_OK
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "INFO" in lines[0]
    assert f"input_len={len(sample_text)}" in lines[0]
    assert f"output_len={len(reply)}" in lines[0]
    assert "outcome=ok" in lines[0]
    assert sample_text not in log_text
    assert reply not in log_text


def test_main_tone_next_writes_info_line(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)

    code = cli.main(["tone", "--next"])

    assert code == cli.EXIT_OK
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "INFO" in lines[0]
    assert "mode=tone" in lines[0]
    assert "--next" in lines[0]
    assert "outcome=ok" in lines[0]


def test_main_tone_show_writes_info_line(monkeypatch, tmp_path) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)

    code = cli.main(["tone", "--show"])

    assert code == cli.EXIT_OK
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(lines) == 1
    assert "INFO" in lines[0]
    assert "mode=tone" in lines[0]
    assert "--show" in lines[0]
    assert "outcome=ok" in lines[0]


def test_main_tone_next_unexpected_exception_logged_and_notifies_log_path(
    monkeypatch, tmp_path
) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)

    def _raise(state=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "save_state", _raise)

    code = cli.main(["tone", "--next"])

    assert code == cli.EXIT_ERROR
    assert notifier.shown[-1].summary == f"Unexpected error — see {log.log_path()}"
    assert notifier.shown[-1].urgency == "critical"
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "RuntimeError" in log_text
    assert "boom" in log_text
    assert "Traceback" in log_text
    assert "outcome=error:RuntimeError" in log_text


def test_main_tone_show_unexpected_exception_logged_and_notifies_log_path(
    monkeypatch, tmp_path
) -> None:
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "NotifySendNotifier", lambda: notifier)

    def _raise(config, state):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "current_tone", _raise)

    code = cli.main(["tone", "--show"])

    assert code == cli.EXIT_ERROR
    assert notifier.shown[-1].summary == f"Unexpected error — see {log.log_path()}"
    assert notifier.shown[-1].urgency == "critical"
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "RuntimeError" in log_text
    assert "boom" in log_text
    assert "Traceback" in log_text
    assert "outcome=error:RuntimeError" in log_text


def test_main_tone_show_stdin_unexpected_exception_prints_to_stderr(
    monkeypatch, tmp_path, capsys
) -> None:
    def _raise(config, state):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "current_tone", _raise)

    code = cli.main(["tone", "--show", "--stdin"])

    assert code == cli.EXIT_ERROR
    assert f"Unexpected error — see {log.log_path()}" in capsys.readouterr().err
    log_text = _log_file(tmp_path).read_text(encoding="utf-8")
    assert "RuntimeError" in log_text
    assert "boom" in log_text


def test_main_log_tail_prints_last_n_lines(tmp_path, capsys) -> None:
    log_file = _log_file(tmp_path)
    log_file.parent.mkdir(parents=True)
    log_file.write_text("line1\nline2\nline3\n", encoding="utf-8")

    code = cli.main(["log", "--tail", "2"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out.splitlines()
    assert out[0] == str(log_file)
    assert out[1:] == ["line2", "line3"]


def test_main_log_without_file_prints_only_path(tmp_path, capsys) -> None:
    code = cli.main(["log"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == f"{_log_file(tmp_path)}\n"


# --- v2 (macOS): platform layer, Desktop bundle, Secure Input, paste hint --------------------


@pytest.fixture(autouse=True)
def _linux_platform_by_default(monkeypatch):
    """The v1 tests above assume Linux wiring whatever the host OS is (macOS CI runner)."""
    monkeypatch.setattr(cli, "detect_platform", lambda: "linux")


def _mac_desktop(
    clip: FakeClipboard,
    keys: FakeKeySender,
    *,
    hint: Callable[[], str | None] = lambda: None,
    app_id: str | None = None,
) -> Desktop:
    return Desktop(
        platform="macos",
        make_clipboard=lambda: clip,
        keys=keys,
        focused_app_id=lambda: app_id,
        paste_hint=MACOS_PASTE_HINT,
        empty_selection_hint=hint,
    )


def _mac_config() -> Config:
    return parse_config({}, platform="macos")


def test_run_shortcut_uses_desktop_bundle_and_mac_keys() -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "Cześć", copy="cmd+c")
    hint_calls: list[int] = []
    desktop = _mac_desktop(clip, keys, hint=lambda: hint_calls.append(1))
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.FIX,
        _mac_config(),
        FakeNotifier(),
        desktop=desktop,
        client=FakeChatClient("Cześć!"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_OK
    assert keys.sent == ["cmd+c", "cmd+v"]
    assert clip.get_text() == "old"
    assert hint_calls == []  # no Secure Input probe on the happy path
    assert clock.sleeps[0] == 0.0  # macOS start_delay


def test_run_shortcut_desktop_focused_app_selects_override() -> None:
    from llmtr.config import KeyOverride, KeysConfig

    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "txt", copy="cmd+shift+c")
    config = Config(
        keys=KeysConfig(
            copy="cmd+c",
            paste="cmd+v",
            start_delay=0.0,
            override=(KeyOverride(app=("com.apple.Terminal",), copy="cmd+shift+c", paste="cmd+v"),),
        )
    )
    desktop = _mac_desktop(clip, keys, app_id="com.apple.Terminal")
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.FIX,
        config,
        FakeNotifier(),
        desktop=desktop,
        client=FakeChatClient("ok"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_OK
    assert keys.sent == ["cmd+shift+c", "cmd+v"]


def test_run_shortcut_empty_capture_reports_secure_input_app() -> None:
    clip = FakeClipboard("old")
    keys = FakeKeySender()  # nothing arrives on the clipboard
    notifier = FakeNotifier()
    chat = FakeChatClient("unused")
    seen_clipboard: list[str] = []
    desktop = _mac_desktop(
        clip, keys, hint=lambda: seen_clipboard.append(clip.get_text()) or "Google Chrome"
    )
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.TRANSLATE,
        _mac_config(),
        notifier,
        desktop=desktop,
        client=chat,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_ERROR
    assert chat.calls == []
    assert [n.summary for n in notifier.shown] == [
        "Nothing copied: secure input is active in Google Chrome."
    ]
    assert notifier.shown[-1].urgency == "critical"
    assert seen_clipboard == ["old"]  # clipboard restored before the probe runs
    assert clip.get_text() == "old"


def test_run_shortcut_empty_capture_without_secure_input_keeps_plain_message() -> None:
    clip = FakeClipboard("old")
    notifier = FakeNotifier()
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.TRANSLATE,
        _mac_config(),
        notifier,
        desktop=_mac_desktop(clip, FakeKeySender(), hint=lambda: None),
        client=FakeChatClient("unused"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_ERROR
    assert [n.summary for n in notifier.shown] == ["No text selected. Select some text first."]


def test_run_shortcut_secure_input_probe_failure_keeps_plain_message() -> None:
    def _boom() -> str | None:
        raise RuntimeError("probe broke")

    clip = FakeClipboard("old")
    notifier = FakeNotifier()
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.FIX,
        _mac_config(),
        notifier,
        desktop=_mac_desktop(clip, FakeKeySender(), hint=_boom),
        client=FakeChatClient("unused"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_ERROR
    assert notifier.shown[-1].summary == "No text selected. Select some text first."


def test_run_shortcut_paste_failure_uses_desktop_paste_hint() -> None:
    clip = FakeClipboard("old")
    keys = FlakyKeySender(clip, "cmd+c", "cmd+v")
    notifier = FakeNotifier()
    clock = FakeClock()

    code = cli.run_shortcut(
        Mode.FIX,
        _mac_config(),
        notifier,
        desktop=_mac_desktop(clip, keys),  # type: ignore[arg-type]
        client=FakeChatClient("fixed"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert code == cli.EXIT_OK
    assert clip.get_text() == "fixed"
    assert notifier.shown[-1].summary == "Result copied. Press ⌘V to paste."


def test_run_shortcut_linux_paste_hint_unchanged() -> None:
    clip = FakeClipboard("old")
    keys = FlakyKeySender(clip, "ctrl+c", "ctrl+v")
    notifier = FakeNotifier()
    clock = FakeClock()

    cli.run_shortcut(
        Mode.FIX,
        Config(),
        notifier,
        clipboard=clip,
        keys=keys,  # type: ignore[arg-type]
        client=FakeChatClient("fixed"),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    assert notifier.shown[-1].summary == "Result copied. Press Ctrl+V to paste."


@pytest.mark.parametrize("reason", ["accessibility", "automation", "timeout", "failed"])
def test_run_shortcut_mac_key_send_error_is_notified_with_its_message(reason) -> None:
    clip = FakeClipboard("old")
    keys = FakeKeySender(fail=MacKeySendError(reason, detail="osascript stderr"))
    notifier = FakeNotifier()

    code = cli.run_shortcut(
        Mode.FIX,
        _mac_config(),
        notifier,
        desktop=_mac_desktop(clip, keys),
        client=FakeChatClient("unused"),
    )

    assert code == cli.EXIT_ERROR
    assert clip.get_text() == "old"
    assert notifier.shown[-1].summary == MacKeySendError.MESSAGES[reason]
    assert notifier.shown[-1].urgency == "critical"


def test_main_macos_wires_platform_backends(monkeypatch) -> None:
    clip = FakeClipboard("old")
    keys = _selecting_keys(clip, "txt", copy="cmd+c")
    notifier = FakeNotifier()
    made: dict[str, object] = {}

    def fake_make_notifier(platform, backend="auto", env=None):
        made["notifier"] = (platform, backend)
        return notifier

    def fake_make_desktop(platform=None, env=None, *, keys_config=None):
        made["desktop"] = (platform, keys_config.copy, keys_config.start_delay)
        return _mac_desktop(clip, keys)

    monkeypatch.setattr(cli, "detect_platform", lambda: "macos")
    monkeypatch.setattr(cli.backends, "make_notifier", fake_make_notifier)
    monkeypatch.setattr(cli.backends, "make_desktop", fake_make_desktop)
    monkeypatch.setattr(cli, "OllamaClient", lambda url, timeout: FakeChatClient("fixed"))

    code = cli.main(["fix"])

    assert code == cli.EXIT_OK
    assert made["notifier"] == ("macos", "auto")
    assert made["desktop"] == ("macos", "cmd+c", 0.0)  # macOS key defaults reached the config
    assert keys.sent == ["cmd+c", "cmd+v"]


def test_main_macos_uses_configured_notify_backend(monkeypatch, tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[notify]\nbackend = "osascript"\n', encoding="utf-8")
    backends_seen: list[str] = []
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "detect_platform", lambda: "macos")
    monkeypatch.setattr(
        cli.backends,
        "make_notifier",
        lambda platform, backend="auto", env=None: backends_seen.append(backend) or notifier,
    )

    assert cli.main(["--config", str(path), "tone", "--show"]) == cli.EXIT_OK

    assert backends_seen == ["osascript"]
    assert notifier.shown[0].summary.startswith("Tone: team")


def test_main_macos_bad_notify_backend_notifies_with_config_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[notify]\nbackend = "growl"\n', encoding="utf-8")
    notifier = FakeNotifier()
    monkeypatch.setattr(cli, "detect_platform", lambda: "macos")
    monkeypatch.setattr(cli.backends, "make_notifier", lambda platform, backend="auto": notifier)

    assert cli.main(["--config", str(path), "fix"]) == cli.EXIT_ERROR

    assert notifier.shown[0].summary == (
        f"Config error in {path}: 'notify.backend' must be one of auto, hammerspoon, osascript"
    )
    assert notifier.shown[0].urgency == "critical"
