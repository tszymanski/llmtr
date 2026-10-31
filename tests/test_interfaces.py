"""M1 interface checks: every module imports and exposes the names in docs/architecture.md."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import llmtr
from llmtr import clipboard, config, errors, fakes, keys, notify, ollama_client, prompts
from llmtr.cli import build_parser

PUBLIC_NAMES: dict[str, list[str]] = {
    "llmtr.errors": [
        "LlmtrError",
        "ConfigError",
        "OllamaUnavailable",
        "ModelMissing",
        "OllamaTimeout",
        "OllamaError",
        "EmptySelection",
        "TextTooLong",
        "ClipboardUnavailable",
        "KeySendError",
        "Cancelled",
    ],
    "llmtr.config": [
        "DEFAULT_OLLAMA_URL",
        "LOG_LEVEL_ENV",
        "OLLAMA_HOST_ENV",
        "SUPPORTED_LANGUAGES",
        "TEAM_TONE",
        "Config",
        "OllamaConfig",
        "ModelsConfig",
        "LanguagesConfig",
        "KeysConfig",
        "KeyOverride",
        "ToneConfig",
        "TonePreset",
        "NotifyConfig",
        "LogConfig",
        "State",
        "config_path",
        "state_path",
        "cache_dir",
        "normalize_ollama_url",
        "parse_config",
        "load_config",
        "load_state",
        "save_state",
        "current_tone",
        "next_tone",
        "save_last_result",
    ],
    "llmtr.langdetect": ["Language", "detect_language", "choose_direction"],
    "llmtr.prompts": [
        "Message",
        "TRANSLATEGEMMA_TEMPLATE",
        "TRANSLATEGEMMA_SEPARATOR",
        "FIX_SYSTEM_PROMPT",
        "TONE_SYSTEM_PROMPT_TEMPLATE",
        "PREAMBLE_PATTERNS",
        "build_translate_messages",
        "build_fix_messages",
        "build_tone_messages",
        "strip_preamble",
    ],
    "llmtr.ollama_client": [
        "Transport",
        "ChatClient",
        "HTTPStatusError",
        "UrllibTransport",
        "OllamaClient",
    ],
    "llmtr.engine": ["Mode", "Job", "plan_job", "progress_text", "run_job"],
    "llmtr.clipboard": ["Clipboard", "WlClipboard", "XclipClipboard", "make_clipboard"],
    "llmtr.keys": [
        "KeyPair",
        "KeySender",
        "YdotoolKeySender",
        "parse_combo",
        "focused_app_id",
        "resolve_key_pair",
    ],
    "llmtr.notify": ["Notifier", "NotifySendNotifier", "Urgency"],
    "llmtr.lock": ["RunLock", "default_lock_path", "cancel_running", "install_cancel_handler"],
    "llmtr.selection": ["Captured", "capture_selection", "deliver_result", "restore_clipboard"],
    "llmtr.fakes": [
        "FakeTransport",
        "FakeChatClient",
        "FakeClipboard",
        "FakeKeySender",
        "FakeNotifier",
        "FakeClock",
        "FakeRunner",
    ],
    "llmtr.cli": ["main", "build_parser", "run_shortcut"],
    # v2 (macOS), architecture sections 11-22
    "llmtr.platforms": [
        "Platform",
        "KeyDefaults",
        "LINUX_KEY_DEFAULTS",
        "MACOS_KEY_DEFAULTS",
        "detect_platform",
        "key_defaults",
    ],
    "llmtr.macos_exec": [
        "PBCOPY",
        "PBPASTE",
        "OSASCRIPT",
        "OPEN",
        "IOREG",
        "PS",
        "LOCALE_VAR",
        "LOCALE_VALUE",
        "SUBPROCESS_TIMEOUT",
        "Runner",
        "child_env",
    ],
    "llmtr.macos_clipboard": ["PbClipboard"],
    "llmtr.macos_keys": [
        "MODIFIER_NAMES",
        "KEY_CODES",
        "ACCESSIBILITY_ERROR",
        "AUTOMATION_ERROR",
        "SEND_TIMEOUT",
        "MacCombo",
        "parse_mac_combo",
        "build_applescript",
        "classify_osascript_error",
        "OsascriptKeySender",
    ],
    "llmtr.macos_notify": [
        "URL_SCHEME",
        "URL_HOST",
        "RUN_ID_ENV",
        "MAX_BODY_CHARS",
        "build_notify_url",
        "HammerspoonNotifier",
        "OsascriptNotifier",
    ],
    "llmtr.macos_probes": [
        "SECURE_INPUT_KEY",
        "PROBE_TIMEOUT",
        "focused_bundle_id",
        "parse_secure_input_pid",
        "secure_input_app",
    ],
    "llmtr.backends": [
        "LINUX_PASTE_HINT",
        "MACOS_PASTE_HINT",
        "Desktop",
        "make_notifier",
        "make_desktop",
    ],
}
PUBLIC_NAMES["llmtr.errors"] += ["MacKeySendError", "SecureInputActive"]
# v3 (Cursor engine), architecture section 23
PUBLIC_NAMES["llmtr.errors"] += [
    "CursorError",
    "CursorKeyMissing",
    "CursorKeyInsecure",
    "CursorAuthError",
    "CursorStorageDisabled",
    "CursorModelInvalid",
    "CursorRateLimited",
    "CursorUnavailable",
    "CursorTimeout",
]
PUBLIC_NAMES["llmtr.config"] += ["CursorConfig", "ENGINES"]
PUBLIC_NAMES["llmtr.prompts"] += ["CURSOR_PROMPT_TEMPLATE", "build_cursor_messages"]
PUBLIC_NAMES["llmtr.fakes"] += ["FakeCursorTransport"]
PUBLIC_NAMES["llmtr.cli"] += ["make_chat_client"]
PUBLIC_NAMES["llmtr.cursor_key"] = ["CURSOR_KEY_ENV", "KEYCHAIN_SERVICE", "key_path", "load_key"]
PUBLIC_NAMES["llmtr.cursor_client"] = [
    "CursorTransport",
    "UrllibCursorTransport",
    "CursorClient",
    "spawn_cleanup",
    "delete_agents",
    "sweep",
]


@pytest.mark.parametrize("module_name", sorted(PUBLIC_NAMES))
def test_module_exposes_public_names(module_name: str) -> None:
    module = importlib.import_module(module_name)
    missing = [n for n in PUBLIC_NAMES[module_name] if not hasattr(module, n)]
    assert not missing, f"{module_name} is missing {missing}"
    assert set(PUBLIC_NAMES[module_name]) <= set(module.__all__)


def test_entry_point_importable() -> None:
    assert callable(llmtr.main)


def test_fakes_satisfy_protocols() -> None:
    assert isinstance(fakes.FakeTransport(), ollama_client.Transport)
    assert isinstance(fakes.FakeChatClient("x"), ollama_client.ChatClient)
    assert isinstance(fakes.FakeClipboard(), clipboard.Clipboard)
    assert isinstance(fakes.FakeKeySender(), keys.KeySender)
    assert isinstance(fakes.FakeNotifier(), notify.Notifier)


def test_fake_key_sender_simulates_copy() -> None:
    clip = fakes.FakeClipboard("old")
    sender = fakes.FakeKeySender(on_send=lambda c: clip.set_text("sel") if c == "ctrl+c" else None)
    sender.send("ctrl+c")
    assert clip.get_text() == "sel"
    assert sender.sent == ["ctrl+c"]


def test_errors_carry_user_messages() -> None:
    assert isinstance(errors.Cancelled(), errors.LlmtrError)
    assert "ollama pull gemma3" in errors.ModelMissing("gemma3").user_message
    assert "localhost:11434" in str(errors.OllamaUnavailable("http://localhost:11434"))
    assert errors.EmptySelection().user_message != errors.EmptySelection(False).user_message


def test_config_defaults() -> None:
    cfg = config.Config()
    assert cfg.models.translate == "translategemma:12b"
    assert cfg.models.translate_quality == "translategemma:27b"
    assert cfg.models.fix == "gemma3"
    assert cfg.models.tone == "gemma3:12b"
    assert cfg.ollama.url == "http://localhost:11434"
    assert cfg.ollama.temperature == 0.0
    assert (cfg.languages.native, cfg.languages.other) == ("pl", "en")
    assert (cfg.keys.copy, cfg.keys.paste) == ("ctrl+c", "ctrl+v")
    assert [p.name for p in cfg.tone.presets] == ["team"]
    assert cfg.notify.enabled is True
    assert cfg.log.enabled is True
    assert cfg.log.level == "info"
    assert config.State().tone == "team"


def _template_from_proposal() -> str:
    text = (Path(__file__).parents[1] / "docs" / "proposal.md").read_text(encoding="utf-8")
    lines = [
        ln[2:] for ln in text.splitlines() if ln.startswith("> You are") or ln.startswith("> ")
    ]
    return " ".join(ln.strip() for ln in lines)


def test_translategemma_template_matches_proposal_verbatim() -> None:
    assert _template_from_proposal() == prompts.TRANSLATEGEMMA_TEMPLATE
    assert prompts.TRANSLATEGEMMA_SEPARATOR == "\n\n\n"


def test_parser_modes() -> None:
    parser = build_parser()
    args = parser.parse_args(["translate", "--quality", "--stdin"])
    assert (args.mode, args.quality, args.stdin) == ("translate", True, True)
    assert parser.parse_args(["tone", "--next"]).next is True
    assert parser.parse_args(["fix"]).mode == "fix"


def test_macos_backends_have_protocol_methods() -> None:
    from llmtr import backends, macos_clipboard, macos_keys, macos_notify

    for method in ("get_text", "set_text", "clear"):
        assert callable(getattr(macos_clipboard.PbClipboard, method))
    for method in ("available", "send"):
        assert callable(getattr(macos_keys.OsascriptKeySender, method))
    for cls in (macos_notify.HammerspoonNotifier, macos_notify.OsascriptNotifier):
        assert callable(cls.notify)
    assert {"platform", "make_clipboard", "keys", "focused_app_id", "paste_hint"} <= set(
        backends.Desktop.__dataclass_fields__
    )
    assert "empty_selection_hint" in backends.Desktop.__dataclass_fields__


def test_platform_key_defaults_constants() -> None:
    from llmtr import platforms

    keys_cfg = config.KeysConfig()
    linux = platforms.LINUX_KEY_DEFAULTS
    assert (linux.copy, linux.paste, linux.start_delay) == (
        keys_cfg.copy,
        keys_cfg.paste,
        keys_cfg.start_delay,
    )
    mac = platforms.MACOS_KEY_DEFAULTS
    assert (mac.copy, mac.paste, mac.start_delay) == ("cmd+c", "cmd+v", 0.0)


def test_macos_constants() -> None:
    from llmtr import macos_exec, macos_notify

    for path in (
        macos_exec.PBCOPY,
        macos_exec.PBPASTE,
        macos_exec.OSASCRIPT,
        macos_exec.OPEN,
        macos_exec.IOREG,
        macos_exec.PS,
    ):
        assert path.startswith("/")
    assert (macos_exec.LOCALE_VAR, macos_exec.LOCALE_VALUE) == ("LC_CTYPE", "UTF-8")
    assert f"{macos_notify.URL_SCHEME}://{macos_notify.URL_HOST}" == "hammerspoon://llmtr"
    assert config.NotifyConfig().backend == "auto"


def test_macos_errors_carry_user_messages() -> None:
    accessibility = errors.MacKeySendError("accessibility")
    automation = errors.MacKeySendError("automation")
    assert isinstance(accessibility, errors.KeySendError)
    assert (
        "Hammerspoon" in accessibility.user_message
        and "Device Control and Data Access (Accessibility)" in accessibility.user_message
    )
    assert "Hammerspoon" in automation.user_message and "Automation" in automation.user_message
    assert str(automation) == automation.user_message
    secure = errors.SecureInputActive("Google Chrome")
    assert isinstance(secure, errors.EmptySelection)
    assert "Google Chrome" in secure.user_message


def test_fake_runner_records_calls_and_replays_responses() -> None:
    run = fakes.FakeRunner([fakes.FakeRunner.ok(b"out"), FileNotFoundError("x")])
    result = run(["/usr/bin/pbpaste"], input=b"in", env={"A": "1"}, timeout=2.0, check=False)
    assert result.stdout == b"out" and result.returncode == 0
    with pytest.raises(FileNotFoundError):
        run(["/usr/bin/pbcopy"])
    first = run.calls[0]
    assert (first.argv, first.input, first.env, first.timeout) == (
        ["/usr/bin/pbpaste"],
        b"in",
        {"A": "1"},
        2.0,
    )
    assert first.kwargs == {"check": False}
    with pytest.raises(AssertionError):
        run(["/usr/bin/open"])


def test_fake_runner_ok_failure_result() -> None:
    result = fakes.FakeRunner.ok(stderr=b"bad", returncode=3)
    assert (result.returncode, result.stderr, result.stdout) == (3, b"bad", b"")


def test_error_message_parameters_default_to_linux_wording() -> None:
    assert errors.ClipboardUnavailable().user_message == (
        "No working clipboard tool. Install wl-clipboard."
    )
    assert errors.ClipboardUnavailable("d", "No working clipboard tool.").user_message == (
        "No working clipboard tool."
    )
    assert errors.EmptySelection(False).user_message == (
        "Clipboard is empty. Copy the text first (ydotool is not set up)."
    )
    assert errors.EmptySelection(False, "Clipboard is empty.").user_message == (
        "Clipboard is empty."
    )
    assert errors.EmptySelection(True, "ignored").user_message == (
        "No text selected. Select some text first."
    )


def test_cursor_fakes_and_client_satisfy_protocols() -> None:
    from llmtr import cursor_client

    transport = fakes.FakeCursorTransport()
    assert isinstance(transport, cursor_client.CursorTransport)
    client = cursor_client.CursorClient(config.CursorConfig(), transport)
    assert isinstance(client, ollama_client.ChatClient)
    assert client.last_agent_id is None


def test_cursor_errors_carry_user_messages() -> None:
    assert isinstance(errors.CursorTimeout(60.0), errors.LlmtrError)
    assert str(errors.CursorTimeout(60.0)) == "Cursor did not answer within 60 s. Try again."
    assert errors.CursorError().user_message == "Cursor refused the request."
    assert errors.CursorRateLimited(12).user_message.endswith("Try again in 12 s.")


def test_parser_engine_and_cursor_cleanup() -> None:
    parser = build_parser()
    args = parser.parse_args(["fix", "--engine", "cursor", "--stdin"])
    assert (args.mode, args.engine) == ("fix", "cursor")
    assert parser.parse_args(["translate"]).engine is None
    assert parser.parse_args(["cursor-cleanup", "a", "b"]).agent_ids == ["a", "b"]
    assert parser.parse_args(["cursor-cleanup"]).agent_ids == []
