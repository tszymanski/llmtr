"""User-facing errors shared by every module (owner: M1, frozen).

Every error the user should see is an ``LlmtrError``. Its ``user_message`` is the short, plain
text that ``cli.py`` puts in the notification (or prints to stderr in ``--stdin`` mode).
``detail`` is optional extra context for stderr/debugging; it is never shown in a notification.

Workers must not add subclasses here; if one is truly needed, report it in the hand-back.
"""

from __future__ import annotations

from pathlib import Path


class LlmtrError(Exception):
    """Base class. ``str(err)`` is the user message."""

    def __init__(self, user_message: str, detail: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


class ConfigError(LlmtrError):
    """``config.toml`` or ``state.toml`` cannot be parsed or has an invalid value."""

    def __init__(self, path: Path | str, problem: str) -> None:
        super().__init__(f"Config error in {path}: {problem}")
        self.path = Path(path)
        self.problem = problem


class OllamaUnavailable(LlmtrError):
    """No connection to the Ollama server."""

    def __init__(self, url: str, detail: str = "") -> None:
        super().__init__(f"Can't reach Ollama at {url}. Is it running?", detail)
        self.url = url


class ModelMissing(LlmtrError):
    """Ollama answered that the model is not installed."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Model {model} is not installed. Run: ollama pull {model}")
        self.model = model


class OllamaTimeout(LlmtrError):
    """The request took longer than ``ollama.timeout`` seconds."""

    def __init__(self, timeout: float) -> None:
        super().__init__(f"Ollama did not answer within {timeout:g} s. Try again.")
        self.timeout = timeout


class OllamaError(LlmtrError):
    """Any other Ollama failure: unexpected HTTP status, bad JSON, empty model output."""

    def __init__(self, user_message: str = "Ollama returned an error.", detail: str = "") -> None:
        super().__init__(user_message, detail)


class EmptySelection(LlmtrError):
    """No text was captured (nothing selected, or empty clipboard in fallback mode)."""

    def __init__(self, used_keystrokes: bool = True) -> None:
        if used_keystrokes:
            message = "No text selected. Select some text first."
        else:
            message = "Clipboard is empty. Copy the text first (ydotool is not set up)."
        super().__init__(message)
        self.used_keystrokes = used_keystrokes


class TextTooLong(LlmtrError):
    """The selection is longer than ``ollama.max_chars``."""

    def __init__(self, length: int, limit: int) -> None:
        super().__init__(f"Selection too long ({length} characters, limit {limit}).")
        self.length = length
        self.limit = limit


class ClipboardUnavailable(LlmtrError):
    """Neither wl-clipboard nor xclip is usable, or a clipboard command failed."""

    def __init__(self, detail: str = "") -> None:
        super().__init__("No working clipboard tool. Install wl-clipboard.", detail)


class KeySendError(LlmtrError):
    """``ydotool`` is present but sending a keystroke failed (e.g. ydotoold not running)."""

    def __init__(self, detail: str = "") -> None:
        super().__init__("Could not send keystrokes. Is ydotoold running?", detail)


class Cancelled(LlmtrError):
    """The job was cancelled by a second shortcut press (SIGTERM from the second process)."""

    def __init__(self) -> None:
        super().__init__("Cancelled.")


__all__ = [
    "Cancelled",
    "ClipboardUnavailable",
    "ConfigError",
    "EmptySelection",
    "KeySendError",
    "LlmtrError",
    "ModelMissing",
    "OllamaError",
    "OllamaTimeout",
    "OllamaUnavailable",
    "TextTooLong",
]
