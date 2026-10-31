"""In-memory fakes for every external boundary (owner: M1, real code, shared by all workers).

Tests use these instead of Ollama, wl-clipboard, ydotool and notify-send. Workers may *use* them
freely; changing them needs the orchestrator (they are shared by M2, M3 and M4).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

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
class RunnerCall:
    """One call of ``FakeRunner``: ``argv`` plus the keyword arguments of ``subprocess.run``."""

    argv: list[str]
    env: Mapping[str, str] | None
    input: bytes | None
    timeout: float | None
    kwargs: dict[str, Any]


class FakeRunner:
    """``macos_exec.Runner`` (same call shape as ``subprocess.run``) returning queued results.

    Each call pops the next item of ``responses``: a ``CompletedProcess`` is returned, an
    exception is raised. Every call is recorded in ``calls``. Nothing real is started::

        run = FakeRunner([FakeRunner.ok(b"text")])
        PbClipboard({}, run=run).get_text()
        assert run.calls[0].argv == ["/usr/bin/pbpaste"]
    """

    def __init__(
        self, responses: Sequence[subprocess.CompletedProcess[bytes] | BaseException] = ()
    ) -> None:
        self.responses: list[subprocess.CompletedProcess[bytes] | BaseException] = list(responses)
        self.calls: list[RunnerCall] = []

    def __call__(self, argv: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        call_kwargs = dict(kwargs)
        self.calls.append(
            RunnerCall(
                argv=list(argv),
                env=call_kwargs.pop("env", None),
                input=call_kwargs.pop("input", None),
                timeout=call_kwargs.pop("timeout", None),
                kwargs=call_kwargs,
            )
        )
        if not self.responses:
            raise AssertionError("FakeRunner: no response queued")
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    @staticmethod
    def ok(
        stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0
    ) -> subprocess.CompletedProcess[bytes]:
        """A finished process; ``returncode`` non-zero for a failure."""
        return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


@dataclass
class CursorCall:
    """One call of ``FakeCursorTransport``. ``path`` is the URL path plus ``?query``;
    ``method`` is ``"STREAM"`` for ``stream``."""

    method: str
    url: str
    path: str
    payload: dict[str, Any] | None
    timeout: float


CursorScript = Response | Sequence[Response]
StreamItem = tuple[str, str] | BaseException


class FakeCursorTransport:
    """``cursor_client.CursorTransport`` with scripted answers; nothing touches the network.

    - ``responses[(method, path)]``: a dict (returned on every call), an exception (raised on
      every call) or a list of those (popped in order; an empty list is an error).
    - ``streams[path]``: a list of ``(event, data)`` pairs and exceptions; an exception is raised
      at its position, i.e. the stream breaks there. ``path`` is the stream URL's path.
    - ``stream_error``: optional exception raised when a stream is opened.
    - ``on_stream``: optional callback run with each yielded event (e.g. to raise ``Cancelled``
      or advance a fake clock).

    Every call is recorded in ``calls`` (``CursorCall``, with the ``payload``). An unscripted call
    raises ``AssertionError``. Use ``http_error`` to build an ``HTTPStatusError``.
    """

    def __init__(
        self,
        responses: Mapping[tuple[str, str], CursorScript] | None = None,
        streams: Mapping[str, Sequence[StreamItem]] | None = None,
        *,
        stream_error: BaseException | None = None,
        on_stream: Callable[[str, str], None] | None = None,
    ) -> None:
        self.responses: dict[tuple[str, str], Any] = {
            key: list(value) if isinstance(value, list | tuple) else value
            for key, value in (responses or {}).items()
        }
        self.streams: dict[str, list[StreamItem]] = {
            key: list(value) for key, value in (streams or {}).items()
        }
        self.stream_error = stream_error
        self.on_stream = on_stream
        self.calls: list[CursorCall] = []

    @staticmethod
    def _path(url: str) -> str:
        parts = urlsplit(url)
        return f"{parts.path}?{parts.query}" if parts.query else parts.path

    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None, timeout: float
    ) -> dict[str, Any]:
        path = self._path(url)
        self.calls.append(
            CursorCall(method, url, path, dict(payload) if payload is not None else None, timeout)
        )
        key = (method, path)
        if key not in self.responses:
            raise AssertionError(f"FakeCursorTransport: no response for {method} {path}")
        item = self.responses[key]
        if isinstance(item, list):
            if not item:
                raise AssertionError(f"FakeCursorTransport: responses for {method} {path} used up")
            item = item.pop(0)
        if isinstance(item, BaseException):
            raise item
        return dict(item)

    def stream(self, url: str, timeout: float) -> Iterator[tuple[str, str]]:
        path = self._path(url)
        self.calls.append(CursorCall("STREAM", url, path, None, timeout))
        if self.stream_error is not None:
            raise self.stream_error
        if path not in self.streams:
            raise AssertionError(f"FakeCursorTransport: no stream for {path}")
        return self._events(self.streams[path])

    def _events(self, items: list[StreamItem]) -> Iterator[tuple[str, str]]:
        for item in items:
            if isinstance(item, BaseException):
                raise item
            if self.on_stream is not None:
                self.on_stream(*item)
            yield item

    def paths(self, method: str | None = None) -> list[str]:
        """Recorded paths, optionally only for one method."""
        return [c.path for c in self.calls if method is None or c.method == method]

    @staticmethod
    def http_error(status: int, body: str = "", retry_after: float | None = None) -> Exception:
        """An ``ollama_client.HTTPStatusError`` as ``UrllibCursorTransport`` raises it."""
        from llmtr.ollama_client import HTTPStatusError

        error = HTTPStatusError(status, body)
        error.retry_after = retry_after  # type: ignore[attr-defined]
        return error


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
    "CursorCall",
    "FakeCursorTransport",
    "FakeChatClient",
    "FakeClipboard",
    "FakeClock",
    "FakeKeySender",
    "FakeNotifier",
    "FakeRunner",
    "FakeTransport",
    "Notification",
    "RunnerCall",
]
