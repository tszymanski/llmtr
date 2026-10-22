"""In-memory fakes for every external boundary (owner: M1, real code, shared by all workers).

Tests use these instead of Ollama, wl-clipboard, ydotool and notify-send. Workers may *use* them
freely; changing them needs the orchestrator (they are shared by M2, M3 and M4).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from llmtr.notify import Urgency
from llmtr.prompts import Message

Response = dict[str, Any] | BaseException


class FakeTransport:
    """``ollama_client.Transport`` returning queued responses.

    Each ``post_json`` pops the next item of ``responses``: a dict is returned, an exception is
    raised. Every call is recorded in ``requests`` as ``(url, payload, timeout)``.
    """

    def __init__(self, responses: Sequence[Response] = ()) -> None:
        self.responses: list[Response] = list(responses)
        self.requests: list[tuple[str, dict[str, Any], float]] = []

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        self.requests.append((url, dict(payload), timeout))
        if not self.responses:
            raise AssertionError("FakeTransport: no response queued")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    @staticmethod
    def chat_response(content: str, model: str = "fake") -> dict[str, Any]:
        """A minimal successful /api/chat response body."""
        return {"model": model, "message": {"role": "assistant", "content": content}, "done": True}


@dataclass
class ChatCall:
    model: str
    messages: list[Message]
    options: dict[str, Any] | None
    keep_alive: str | None


class FakeChatClient:
    """``ollama_client.ChatClient``: replies with ``reply`` (a string, a function of the
    messages, or an exception to raise) and records calls."""

    def __init__(self, reply: str | Callable[[Sequence[Message]], str] | BaseException) -> None:
        self.reply = reply
        self.calls: list[ChatCall] = []

    def chat(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> str:
        self.calls.append(
            ChatCall(model, list(messages), dict(options) if options else None, keep_alive)
        )
        if isinstance(self.reply, BaseException):
            raise self.reply
        if callable(self.reply):
            return self.reply(messages)
        return self.reply


@dataclass
class FakeClipboard:
    """``clipboard.Clipboard`` holding one string. ``history`` records every ``set_text``
    and ``clear`` (as ``""``)."""

    text: str = ""
    history: list[str] = field(default_factory=list)

    def get_text(self) -> str:
        return self.text

    def set_text(self, text: str) -> None:
        self.text = text
        self.history.append(text)

    def clear(self) -> None:
        self.set_text("")


class FakeKeySender:
    """``keys.KeySender`` recording sent combos in ``sent``.

    ``on_send(combo)`` simulates the focused app, e.g. copying the selection::

        clip = FakeClipboard("old")
        keys = FakeKeySender(on_send=lambda c: clip.set_text("selected") if c == "ctrl+c" else None)

    ``fail`` (an exception) is raised by ``send`` after recording, to simulate ydotool errors.
    """

    def __init__(
        self,
        *,
        is_available: bool = True,
        on_send: Callable[[str], None] | None = None,
        fail: BaseException | None = None,
    ) -> None:
        self.is_available = is_available
        self.on_send = on_send
        self.fail = fail
        self.sent: list[str] = []

    def available(self) -> bool:
        return self.is_available

    def send(self, combo: str) -> None:
        self.sent.append(combo)
        if self.fail is not None:
            raise self.fail
        if self.on_send is not None:
            self.on_send(combo)


@dataclass
class Notification:
    summary: str
    body: str
    urgency: Urgency


@dataclass
class FakeNotifier:
    """``notify.Notifier`` recording notifications in ``shown``."""

    shown: list[Notification] = field(default_factory=list)

    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None:
        self.shown.append(Notification(summary, body, urgency))


@dataclass
class FakeClock:
    """Injectable ``sleep``/``monotonic`` pair: ``sleep`` advances ``now`` instantly."""

    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now


__all__ = [
    "ChatCall",
    "FakeChatClient",
    "FakeClipboard",
    "FakeClock",
    "FakeKeySender",
    "FakeNotifier",
    "FakeTransport",
    "Notification",
]
