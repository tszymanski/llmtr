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
    ],
    "llmtr.cli": ["main", "build_parser", "run_shortcut"],
}


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
