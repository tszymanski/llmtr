"""Ollama HTTP client (owner: M2).

Talks to ``POST {base_url}/api/chat`` with ``stream: false``. HTTP is behind the ``Transport``
protocol so tests inject ``llmtr.fakes.FakeTransport`` and never open a socket.

Transport contract (low-level, no llmtr errors):
- returns the decoded JSON object of a 2xx response;
- raises ``HTTPStatusError`` for a non-2xx response (with the raw body);
- raises ``ConnectionError`` (or a subclass) when it cannot connect;
- raises ``TimeoutError`` when ``timeout`` expires.

``OllamaClient`` maps those to user errors from ``llmtr.errors``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from llmtr.errors import ModelMissing, OllamaError, OllamaTimeout, OllamaUnavailable
from llmtr.prompts import Message

CHAT_PATH = "/api/chat"


class HTTPStatusError(Exception):
    """Non-2xx HTTP response, raised by transports."""

    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


@runtime_checkable
class Transport(Protocol):
    """POSTs JSON and returns the decoded JSON response."""

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        """Send ``payload`` as JSON to ``url``; see the module docstring for errors."""
        ...


@runtime_checkable
class ChatClient(Protocol):
    """What ``engine.run_job`` needs; ``OllamaClient`` and ``fakes.FakeChatClient`` implement it."""

    def chat(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> str:
        """Return the assistant message content (unfiltered)."""
        ...


class UrllibTransport:
    """``Transport`` built on ``urllib.request`` (the only real network code)."""

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        """``urllib.error.HTTPError`` -> ``HTTPStatusError``; ``URLError`` wrapping a socket
        timeout or ``TimeoutError`` -> ``TimeoutError``; other ``URLError``/``OSError`` ->
        ``ConnectionError``. Invalid JSON -> ``ValueError``.
        """
        data = json.dumps(dict(payload)).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise HTTPStatusError(exc.code, body) from exc
        except TimeoutError as exc:
            raise TimeoutError(str(exc)) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(str(exc.reason)) from exc
            raise ConnectionError(str(exc.reason)) from exc
        except OSError as exc:
            raise ConnectionError(str(exc)) from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON response: {exc}") from exc
        if not isinstance(decoded, dict):
            raise ValueError(f"expected a JSON object, got {type(decoded).__name__}")
        return decoded


class OllamaClient:
    """Ollama /api/chat client. Implements ``ChatClient``."""

    def __init__(self, base_url: str, timeout: float, transport: Transport | None = None) -> None:
        """``base_url`` is already normalized (``config.normalize_ollama_url``);
        ``transport`` defaults to ``UrllibTransport()``.
        """
        self.base_url = base_url
        self.timeout = timeout
        self.transport = transport if transport is not None else UrllibTransport()

    def chat(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> str:
        """POST ``{"model", "messages", "stream": False, "options"?, "keep_alive"?}``.

        Returns ``response["message"]["content"]``.

        Raises:
            OllamaUnavailable: transport raised ``ConnectionError``.
            OllamaTimeout: transport raised ``TimeoutError``.
            ModelMissing: HTTP 404 whose body mentions "not found".
            OllamaError: any other HTTP status, ``ValueError``, or a response without
                ``message.content``.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "stream": False,
        }
        if options is not None:
            payload["options"] = dict(options)
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        url = f"{self.base_url}{CHAT_PATH}"
        try:
            response = self.transport.post_json(url, payload, self.timeout)
        except ConnectionError as exc:
            raise OllamaUnavailable(self.base_url, str(exc)) from exc
        except TimeoutError as exc:
            raise OllamaTimeout(self.timeout) from exc
        except HTTPStatusError as exc:
            if exc.status == 404 and "not found" in exc.body.lower():
                raise ModelMissing(model) from exc
            raise OllamaError(detail=f"HTTP {exc.status}: {exc.body}") from exc
        except ValueError as exc:
            raise OllamaError(detail=str(exc)) from exc

        message = response.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise OllamaError(detail=f"unexpected response: {response!r}")
        return content


__all__ = [
    "CHAT_PATH",
    "ChatClient",
    "HTTPStatusError",
    "OllamaClient",
    "Transport",
    "UrllibTransport",
]
