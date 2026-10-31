"""Cursor Cloud Agents API engine (v3, architecture section 23).

One call = one fresh **no-repo** agent: ``POST /v1/agents`` -> read
``GET /v1/agents/{id}/runs/{runId}/stream`` until the ``result`` event -> hand the text back. The
agent is deleted later by a detached child (``llmtr cursor-cleanup <id>``), so the slow ``DELETE``
(M14: median 11.7 s) never blocks the paste. Leftover ``llmtr-`` agents are swept at most once an
hour.

HTTP is behind ``CursorTransport`` so tests inject ``llmtr.fakes.FakeCursorTransport``. Transport
contract (low-level, no llmtr errors), as for Ollama's ``Transport``:
- ``request`` returns the decoded JSON object of a 2xx response (``{}`` for an empty body);
- ``stream`` yields ``(event, data)`` pairs of a ``text/event-stream`` response;
- both raise ``ollama_client.HTTPStatusError`` (with ``body`` and ``retry_after``) for a non-2xx
  response, ``ConnectionError`` when they cannot connect, ``TimeoutError`` when ``timeout``
  expires and ``ValueError`` for a body that is not a JSON object.
"""

from __future__ import annotations

import json
import logging
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from llmtr.config import CursorConfig, cache_dir
from llmtr.errors import (
    Cancelled,
    CursorAuthError,
    CursorError,
    CursorModelInvalid,
    CursorRateLimited,
    CursorStorageDisabled,
    CursorTimeout,
    CursorUnavailable,
    LlmtrError,
)
from llmtr.ollama_client import HTTPStatusError
from llmtr.prompts import Message

AGENT_PREFIX = "llmtr-"
"""Every agent llmtr creates is named ``llmtr-<8 hex>``; the sweep only touches these."""

AUTO_MODEL = "auto"
"""``cursor.model = "auto"`` omits ``model`` from the create request (account default)."""

TERMINAL_STATUSES = frozenset({"FINISHED", "ERROR", "CANCELLED", "EXPIRED"})

SWEEP_INTERVAL = 3600.0
"""Seconds between two sweeps on one machine."""
SWEEP_MIN_AGE = 600.0
"""Agents younger than this (by ``createdAt``) are never swept."""
SWEEP_MAX_DELETES = 10
"""Delete requests per sweep (the API allows 20 requests per minute)."""
SWEEP_STAMP = "cursor-sweep"
"""Timestamp file in ``$XDG_CACHE_HOME/llmtr``."""

USER_AGENT = "llmtr"

_log = logging.getLogger("llmtr")


def _short(ident: str | None) -> str:
    """First 6 characters of an agent/run id: enough to correlate, never the whole id."""
    return (ident or "")[:6]


# --- transport ---------------------------------------------------------------------------------


@runtime_checkable
class CursorTransport(Protocol):
    """JSON requests and SSE streams against the Cursor API (see the module docstring)."""

    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None, timeout: float
    ) -> dict[str, Any]:
        """Send ``payload`` (or no body) and return the decoded JSON object."""
        ...

    def stream(self, url: str, timeout: float) -> Iterator[tuple[str, str]]:
        """``GET url`` with ``Accept: text/event-stream``; yield ``(event, data)``."""
        ...


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _status_error(exc: urllib.error.HTTPError) -> HTTPStatusError:
    body = exc.read().decode("utf-8", errors="replace")
    error = HTTPStatusError(exc.code, body)
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    error.retry_after = _retry_after(header)  # type: ignore[attr-defined]
    return error


def parse_sse(lines: Iterable[bytes]) -> Iterator[tuple[str, str]]:
    """Server-sent events from raw lines: ``event:``/``data:`` fields, multi-line ``data``
    joined with ``\\n``, ``:`` comments skipped, dispatch on a blank line (an event without
    ``data`` is dropped, as is an unterminated one at the end)."""
    event = ""
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if data:
                yield event or "message", "\n".join(data)
            event, data = "", []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)


class UrllibCursorTransport:
    """``CursorTransport`` on ``urllib.request`` (the only real Cursor network code).

    Sends ``Authorization: Bearer <key>``. The key is kept in a private attribute and is never in
    ``repr``, log lines or exceptions.
    """

    def __init__(self, key: str) -> None:
        self._key = key

    def __repr__(self) -> str:
        return "UrllibCursorTransport(key=<redacted>)"

    def _headers(self, accept: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Accept": accept,
            "User-Agent": USER_AGENT,
        }

    def _open(
        self, method: str, url: str, payload: Mapping[str, Any] | None, accept: str, timeout: float
    ) -> Any:
        headers = self._headers(accept)
        data = None
        if payload is not None:
            data = json.dumps(dict(payload)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            raise _status_error(exc) from None
        except TimeoutError as exc:
            raise TimeoutError(str(exc)) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(str(exc.reason)) from None
            raise ConnectionError(str(exc.reason)) from None
        except OSError as exc:
            raise ConnectionError(str(exc)) from None

    def request(
        self, method: str, url: str, payload: Mapping[str, Any] | None, timeout: float
    ) -> dict[str, Any]:
        """See ``CursorTransport``; an empty 2xx body gives ``{}``."""
        response = self._open(method, url, payload, "application/json", timeout)
        try:
            with response:
                body = response.read().decode("utf-8", errors="replace")
        except TimeoutError as exc:
            raise TimeoutError(str(exc)) from None
        except OSError as exc:
            raise ConnectionError(str(exc)) from None
        if not body.strip():
            return {}
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON response: {exc}") from None
        if not isinstance(decoded, dict):
            raise ValueError(f"expected a JSON object, got {type(decoded).__name__}")
        return decoded

    def stream(self, url: str, timeout: float) -> Iterator[tuple[str, str]]:
        """See ``CursorTransport``; ``timeout`` applies to the connect and to every read."""
        response = self._open("GET", url, None, "text/event-stream", timeout)
        with response:
            try:
                yield from parse_sse(response)
            except TimeoutError as exc:
                raise TimeoutError(str(exc)) from None
            except OSError as exc:
                raise ConnectionError(str(exc)) from None


# --- error mapping ----------------------------------------------------------------------------


def _error_code(body: str) -> str:
    """``error.code`` (or top-level ``code``) of a Cursor error body, else ``""``."""
    try:
        decoded = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(decoded, dict):
        return ""
    error = decoded.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("code"), str):
        return error["code"]
    code = decoded.get("code")
    return code if isinstance(code, str) else ""


def map_error(exc: BaseException, *, model: str = "", timeout: float = 0.0) -> LlmtrError:
    """Map a transport exception to the user error of the section 23 table."""
    if isinstance(exc, LlmtrError):
        return exc
    if isinstance(exc, HTTPStatusError):
        code = _error_code(exc.body)
        detail = f"HTTP {exc.status}: {exc.body[:300]}"
        if exc.status == 401:
            return CursorAuthError()
        if exc.status == 403 and code == "feature_unavailable":
            return CursorStorageDisabled()
        if exc.status == 400 and code == "invalid_model":
            return CursorModelInvalid(model)
        if exc.status == 429:
            return CursorRateLimited(getattr(exc, "retry_after", None))
        if exc.status >= 500:
            return CursorUnavailable(detail)
        return CursorError(detail=detail)
    if isinstance(exc, TimeoutError):
        return CursorTimeout(timeout)
    if isinstance(exc, ConnectionError):
        return CursorUnavailable(str(exc))
    if isinstance(exc, ValueError):
        return CursorError(detail=str(exc))
    return CursorError(detail=f"{type(exc).__name__}: {exc}")


# --- cleanup child ----------------------------------------------------------------------------


def spawn_cleanup(agent_id: str) -> None:
    """Start ``python -m llmtr cursor-cleanup <agent_id>`` detached and return at once.

    New session, all standard streams on ``DEVNULL``, ``close_fds=True``; the parent never waits.
    Only the agent id goes in argv (the child loads config and key itself). A failure to start
    is logged and swallowed: the sweep removes the agent later.
    """
    try:
        subprocess.Popen(
            [sys.executable, "-m", "llmtr", "cursor-cleanup", agent_id],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.error("cursor cleanup not started for agent %s: %s", _short(agent_id), exc)


# --- client -----------------------------------------------------------------------------------


class CursorClient:
    """Cursor engine. Implements ``ollama_client.ChatClient``; ignores ``options``/``keep_alive``.

    ``last_agent_id`` is the id of the agent of the last ``chat`` call (``None`` before the
    create succeeded). ``monotonic`` is injectable for deadline tests.
    """

    def __init__(
        self,
        config: CursorConfig,
        transport: CursorTransport,
        *,
        spawn_cleanup: Callable[[str], None] = spawn_cleanup,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.transport = transport
        self.spawn_cleanup = spawn_cleanup
        self.monotonic = monotonic
        self.last_agent_id: str | None = None

    def __repr__(self) -> str:
        return f"CursorClient(model={self.config.model!r}, base_url={self.config.base_url!r})"

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def chat(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        options: Mapping[str, Any] | None = None,
        keep_alive: str | None = None,
    ) -> str:
        """Create a fresh agent, read its run's result and return the text (unfiltered).

        Raises the Cursor errors of architecture section 23, or ``Cancelled`` (after posting the
        cancel). ``spawn_cleanup(agent_id)`` runs exactly once once the agent exists.
        """
        self.last_agent_id = None
        prompt = "\n\n".join(m["content"] for m in messages)
        body: dict[str, Any] = {
            "prompt": {"text": prompt},
            "name": f"{AGENT_PREFIX}{secrets.token_hex(4)}",
            "mode": "agent",
        }
        if model != AUTO_MODEL:
            body["model"] = {"id": model}

        deadline = self.monotonic() + self.config.timeout
        try:
            created = self.transport.request(
                "POST", self._url("/v1/agents"), body, self.config.request_timeout
            )
        except Cancelled:
            raise
        except Exception as exc:
            raise map_error(exc, model=model, timeout=self.config.request_timeout) from exc

        agent = created.get("agent")
        run = created.get("run")
        agent_id = agent.get("id") if isinstance(agent, Mapping) else None
        run_id = run.get("id") if isinstance(run, Mapping) else None
        if not isinstance(agent_id, str) or not agent_id:
            raise CursorError(detail="create response without agent.id")
        self.last_agent_id = agent_id

        try:
            if not isinstance(run_id, str) or not run_id:
                raise CursorError(detail="create response without run.id")
            try:
                return self._result(agent_id, run_id, deadline, model)
            except Cancelled:
                self._cancel(agent_id, run_id)
                raise
        finally:
            self.spawn_cleanup(agent_id)

    def _result(self, agent_id: str, run_id: str, deadline: float, model: str) -> str:
        run_path = f"/v1/agents/{agent_id}/runs/{run_id}"
        remaining = max(deadline - self.monotonic(), 0.001)
        try:
            for event, data in self.transport.stream(self._url(f"{run_path}/stream"), remaining):
                if event == "result":
                    return self._from_result_event(data)
                if self.monotonic() >= deadline:
                    raise CursorTimeout(self.config.timeout)
        except (Cancelled, CursorError):
            raise
        except (HTTPStatusError, ConnectionError, TimeoutError, ValueError) as exc:
            _log.info("cursor stream for run %s broke: %s", _short(run_id), type(exc).__name__)
        return self._fallback(run_path, deadline, model)

    def _from_result_event(self, data: str) -> str:
        try:
            result = json.loads(data)
        except json.JSONDecodeError as exc:
            raise CursorError(detail=f"bad result event: {exc}") from None
        if not isinstance(result, Mapping):
            raise CursorError(detail="result event is not an object")
        status = result.get("status")
        if status != "FINISHED":
            raise CursorError("Cursor agent failed.", detail=f"run status {status}")
        text = result.get("text")
        return text if isinstance(text, str) else ""

    def _fallback(self, run_path: str, deadline: float, model: str) -> str:
        """One ``GET`` of the run after the stream ended or broke without a ``result``."""
        try:
            run = self.transport.request(
                "GET", self._url(run_path), None, self.config.request_timeout
            )
        except Cancelled:
            raise
        except Exception as exc:
            raise map_error(exc, model=model, timeout=self.config.request_timeout) from exc
        status = run.get("status")
        if status == "FINISHED":
            result = run.get("result")
            return result if isinstance(result, str) else ""
        if status in TERMINAL_STATUSES:
            raise CursorError("Cursor agent failed.", detail=f"run status {status}")
        if self.monotonic() >= deadline:
            raise CursorTimeout(self.config.timeout)
        raise CursorError(detail=f"stream ended before the result (run status {status})")

    def _cancel(self, agent_id: str, run_id: str) -> None:
        """Best effort: every error, including ``409 run_not_cancellable``, is ignored."""
        url = self._url(f"/v1/agents/{agent_id}/runs/{run_id}/cancel")
        try:
            self.transport.request("POST", url, None, self.config.cancel_timeout)
        except Exception as exc:  # also a second Cancelled: the cleanup must still run
            _log.info("cursor cancel of run %s failed: %s", _short(run_id), type(exc).__name__)


# --- deletion and sweep -----------------------------------------------------------------------


def delete_agents(ids: Iterable[str], config: CursorConfig, transport: CursorTransport) -> int:
    """``DELETE /v1/agents/{id}`` for each id with ``delete_timeout``; returns how many
    succeeded. Failures are logged (short id and error class), never raised."""
    deleted = 0
    for agent_id in ids:
        try:
            transport.request(
                "DELETE", f"{config.base_url}/v1/agents/{agent_id}", None, config.delete_timeout
            )
        except Exception as exc:
            _log.error(
                "cursor delete of agent %s failed: %s",
                _short(agent_id),
                map_error(exc).user_message,
            )
            continue
        deleted += 1
        _log.info("cursor agent %s deleted", _short(agent_id))
    return deleted


def _created_at(value: Any) -> float | None:
    """``createdAt`` as a Unix time: ISO 8601 string or epoch (seconds or milliseconds)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value) / 1000.0 if value > 1e11 else float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _sweepable(agent: Any, now: float) -> bool:
    if not isinstance(agent, Mapping):
        return False
    name = agent.get("name")
    if not isinstance(name, str) or not name.startswith(AGENT_PREFIX):
        return False
    if agent.get("status") == "ACTIVE" or not isinstance(agent.get("id"), str):
        return False
    if "createdAt" in agent:
        created = _created_at(agent.get("createdAt"))
        if created is None or now - created < SWEEP_MIN_AGE:
            return False
    return True


def sweep(
    config: CursorConfig,
    transport: CursorTransport,
    *,
    now: float,
    env: Mapping[str, str] | None = None,
) -> int:
    """Delete leftover ``llmtr-`` agents, at most once per ``SWEEP_INTERVAL`` per machine.

    ``now`` is Unix time. Skips (returns 0) when ``$XDG_CACHE_HOME/llmtr/cursor-sweep`` holds a
    time less than an hour old; otherwise writes ``now`` there, lists
    ``GET /v1/agents?includeArchived=true&limit=100`` and deletes agents named ``llmtr-…`` that
    are not ``ACTIVE`` and, when ``createdAt`` is present, older than 10 minutes. At most
    ``SWEEP_MAX_DELETES`` delete requests (failed ones count too). Returns how many deletes
    succeeded; never raises for an API error.
    """
    stamp = cache_dir(env) / SWEEP_STAMP
    try:
        last = float(stamp.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        last = None
    if last is not None and 0 <= now - last < SWEEP_INTERVAL:
        return 0
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(f"{now}\n", encoding="utf-8")
    except OSError as exc:
        _log.error("cursor sweep stamp not written: %s", exc)

    url = f"{config.base_url}/v1/agents?includeArchived=true&limit=100"
    try:
        listing = transport.request("GET", url, None, config.request_timeout)
    except Exception as exc:
        _log.error("cursor sweep list failed: %s", type(exc).__name__)
        return 0
    agents = listing.get("agents") or listing.get("items") or listing.get("data") or []
    if not isinstance(agents, list):
        return 0
    ids = [a["id"] for a in agents if _sweepable(a, now)][:SWEEP_MAX_DELETES]
    deleted = delete_agents(ids, config, transport)
    _log.info("cursor sweep: %d leftover agent(s), %d deleted", len(ids), deleted)
    return deleted


__all__ = [
    "AGENT_PREFIX",
    "AUTO_MODEL",
    "SWEEP_INTERVAL",
    "SWEEP_MAX_DELETES",
    "SWEEP_MIN_AGE",
    "SWEEP_STAMP",
    "CursorClient",
    "CursorTransport",
    "UrllibCursorTransport",
    "delete_agents",
    "map_error",
    "parse_sse",
    "spawn_cleanup",
    "sweep",
]
