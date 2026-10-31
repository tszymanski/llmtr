"""Unit tests for llmtr.cursor_client (M15).

All tests use ``FakeCursorTransport`` except the ``UrllibCursorTransport`` ones, which talk to a
local ``http.server`` thread on 127.0.0.1. The real-API test is skipped unless
``LLMTR_CURSOR_TESTS=1`` (host only, with a real key).
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from llmtr import cursor_client
from llmtr.config import CursorConfig
from llmtr.cursor_client import (
    CursorClient,
    UrllibCursorTransport,
    delete_agents,
    parse_sse,
    spawn_cleanup,
    sweep,
)
from llmtr.errors import (
    Cancelled,
    CursorAuthError,
    CursorError,
    CursorModelInvalid,
    CursorRateLimited,
    CursorStorageDisabled,
    CursorTimeout,
    CursorUnavailable,
)
from llmtr.fakes import FakeCursorTransport
from llmtr.ollama_client import ChatClient, HTTPStatusError

BASE = "https://cursor.test"
CFG = CursorConfig(base_url=BASE)
AGENT = "bc-agent-123456"
RUN = "run-abcdef"
RUN_PATH = f"/v1/agents/{AGENT}/runs/{RUN}"
STREAM = f"{RUN_PATH}/stream"
CREATED = {"agent": {"id": AGENT, "status": "ACTIVE"}, "run": {"id": RUN, "status": "CREATING"}}
MESSAGES = [{"role": "user", "content": "PROMPT"}]


def _result(text: str = "Hello", status: str = "FINISHED") -> tuple[str, str]:
    return "result", json.dumps({"status": status, "text": text, "durationMs": 4226})


def _happy_stream(text: str = "Hello") -> list:
    return [
        ("status", '{"status": "RUNNING"}'),
        ("interaction_update", '{"type": "turn-ended"}'),
        ("status", '{"status": "FINISHED"}'),
        _result(text),
        ("done", "{}"),
    ]


class Recorder:
    def __init__(self) -> None:
        self.ids: list[str] = []

    def __call__(self, agent_id: str) -> None:
        self.ids.append(agent_id)


def _client(
    transport: FakeCursorTransport,
    config: CursorConfig = CFG,
    monotonic: Callable[[], float] | None = None,
) -> tuple[CursorClient, Recorder]:
    spawned = Recorder()
    kwargs = {"monotonic": monotonic} if monotonic is not None else {}
    return CursorClient(config, transport, spawn_cleanup=spawned, **kwargs), spawned


def _transport(stream: list | None = None, **responses) -> FakeCursorTransport:
    scripted = {("POST", "/v1/agents"): CREATED}
    scripted.update({tuple(k.split(" ", 1)): v for k, v in responses.items()})
    return FakeCursorTransport(scripted, {STREAM: stream if stream is not None else []})


def _err(status: int, body: str = "", retry_after: float | None = None) -> Exception:
    return FakeCursorTransport.http_error(status, body, retry_after)


# --- request flow --------------------------------------------------------------------------------


def test_client_satisfies_chat_client_protocol() -> None:
    client, _ = _client(_transport())
    assert isinstance(client, ChatClient)
    assert isinstance(FakeCursorTransport(), cursor_client.CursorTransport)
    assert isinstance(UrllibCursorTransport("k"), cursor_client.CursorTransport)


def test_create_body_with_model_and_no_repos_or_env() -> None:
    transport = _transport(_happy_stream())
    client, _ = _client(transport)

    assert client.chat("gpt-5.4-nano", MESSAGES, options={"temperature": 0}, keep_alive="1m")

    create = transport.calls[0]
    assert (create.method, create.url) == ("POST", f"{BASE}/v1/agents")
    assert create.timeout == CFG.request_timeout
    body = create.payload
    assert body is not None
    assert set(body) == {"prompt", "name", "mode", "model"}
    assert body["prompt"] == {"text": "PROMPT"}
    assert body["mode"] == "agent"
    assert body["model"] == {"id": "gpt-5.4-nano"}
    name = body["name"]
    assert name.startswith("llmtr-") and len(name) == len("llmtr-") + 8
    int(name.removeprefix("llmtr-"), 16)


def test_create_body_without_model_for_auto() -> None:
    transport = _transport(_happy_stream())
    client, _ = _client(transport)
    client.chat("auto", MESSAGES)
    body = transport.calls[0].payload
    assert body is not None and "model" not in body and "repos" not in body


def test_agent_names_are_random() -> None:
    names = set()
    for _ in range(3):
        transport = _transport(_happy_stream())
        _client(transport)[0].chat("m", MESSAGES)
        names.add(transport.calls[0].payload["name"])  # type: ignore[index]
    assert len(names) == 3


def test_prompt_joins_message_contents() -> None:
    transport = _transport(_happy_stream())
    _client(transport)[0].chat(
        "m", [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]
    )
    assert transport.calls[0].payload["prompt"]["text"] == "a\n\nb"  # type: ignore[index]


def test_text_comes_from_result_event_and_stream_url() -> None:
    transport = _transport(_happy_stream("Can we meet at three?"))
    client, spawned = _client(transport)

    assert client.chat("m", MESSAGES) == "Can we meet at three?"
    stream_call = transport.calls[1]
    assert (stream_call.method, stream_call.url) == ("STREAM", f"{BASE}{STREAM}")
    assert 0 < stream_call.timeout <= CFG.timeout
    assert [c.method for c in transport.calls] == ["POST", "STREAM"]
    assert client.last_agent_id == AGENT
    assert spawned.ids == [AGENT]


def test_status_finished_with_result_cancelled_is_an_error() -> None:
    stream = [("status", '{"status": "FINISHED"}'), _result("", status="CANCELLED")]
    client, spawned = _client(_transport(stream))
    with pytest.raises(CursorError) as info:
        client.chat("m", MESSAGES)
    assert info.value.user_message == "Cursor agent failed."
    assert spawned.ids == [AGENT]


@pytest.mark.parametrize("status", ["ERROR", "EXPIRED"])
def test_failed_run_result_is_agent_failed(status) -> None:
    client, _ = _client(_transport([_result("partial", status=status)]))
    with pytest.raises(CursorError, match="Cursor agent failed."):
        client.chat("m", MESSAGES)


def test_unknown_events_are_ignored() -> None:
    stream = [
        ("heartbeat", ""),
        ("thinking", '{"text": "hmm"}'),
        ("assistant", '{"text": "draft"}'),
        ("interaction_update", '{"type": "text-delta"}'),
        ("message", "not json"),
        _result("Final"),
    ]
    client, _ = _client(_transport(stream))
    assert client.chat("m", MESSAGES) == "Final"


def test_result_without_text_gives_empty_string() -> None:
    client, _ = _client(_transport([("result", '{"status": "FINISHED"}')]))
    assert client.chat("m", MESSAGES) == ""


# --- failure paths ---------------------------------------------------------------------------


def test_stream_breaks_then_get_finished_uses_result() -> None:
    stream = [("status", '{"status": "RUNNING"}'), ConnectionError("reset")]
    transport = _transport(
        stream, **{f"GET {RUN_PATH}": {"status": "FINISHED", "result": "From GET"}}
    )
    client, spawned = _client(transport)

    assert client.chat("m", MESSAGES) == "From GET"
    assert [c.method for c in transport.calls] == ["POST", "STREAM", "GET"]
    assert transport.calls[2].timeout == CFG.request_timeout
    assert spawned.ids == [AGENT]


def test_stream_ends_without_result_then_get_not_terminal_is_error() -> None:
    transport = _transport(
        [("status", '{"status": "RUNNING"}')], **{f"GET {RUN_PATH}": {"status": "RUNNING"}}
    )
    client, spawned = _client(transport)
    with pytest.raises(CursorError) as info:
        client.chat("m", MESSAGES)
    assert not isinstance(info.value, CursorTimeout)
    assert len(transport.paths("GET")) == 1
    assert spawned.ids == [AGENT]


def test_stream_read_timeout_after_deadline_then_get_not_terminal_is_timeout() -> None:
    clock = iter([0.0, 0.0, 61.0, 61.0, 61.0])
    transport = _transport([TimeoutError("read")], **{f"GET {RUN_PATH}": {"status": "RUNNING"}})
    client, _ = _client(transport, monotonic=lambda: next(clock))
    with pytest.raises(CursorTimeout) as info:
        client.chat("m", MESSAGES)
    assert info.value.user_message == "Cursor did not answer within 60 s. Try again."


def test_deadline_passed_while_streaming_is_timeout() -> None:
    now = [0.0]

    def tick(event: str, data: str) -> None:
        now[0] += 25.0

    transport = FakeCursorTransport(
        {("POST", "/v1/agents"): CREATED},
        {STREAM: [("status", '{"status": "RUNNING"}')] * 5 + [_result()]},
        on_stream=tick,
    )
    client, spawned = _client(transport, config=CFG, monotonic=lambda: now[0])
    with pytest.raises(CursorTimeout):
        client.chat("m", MESSAGES)
    assert spawned.ids == [AGENT]


def test_get_fallback_terminal_failure_is_agent_failed() -> None:
    transport = _transport([], **{f"GET {RUN_PATH}": {"status": "EXPIRED"}})
    with pytest.raises(CursorError, match="Cursor agent failed."):
        _client(transport)[0].chat("m", MESSAGES)


ERROR_TABLE = [
    (_err(401, '{"code":"error","message":"Invalid User API Key"}'), CursorAuthError),
    (
        _err(403, '{"error":{"code":"feature_unavailable","message":"Storage mode is disabled."}}'),
        CursorStorageDisabled,
    ),
    (_err(403, '{"error":{"code":"forbidden"}}'), CursorError),
    (_err(400, '{"error":{"code":"invalid_model","message":"no"}}'), CursorModelInvalid),
    (
        _err(400, '{"error":{"code":"validation_error","message":"Prompt cannot be empty"}}'),
        CursorError,
    ),
    (_err(429, "{}", retry_after=30.0), CursorRateLimited),
    (_err(500, "oops"), CursorUnavailable),
    (_err(503, ""), CursorUnavailable),
    (ConnectionError("refused"), CursorUnavailable),
    (TimeoutError("slow"), CursorTimeout),
    (ValueError("bad json"), CursorError),
]


@pytest.mark.parametrize(("raised", "expected"), ERROR_TABLE)
def test_create_errors_map_to_classes_and_skip_cleanup(raised, expected) -> None:
    transport = FakeCursorTransport({("POST", "/v1/agents"): raised})
    client, spawned = _client(transport)
    with pytest.raises(expected) as info:
        client.chat("my-model", MESSAGES)
    assert type(info.value) is expected
    assert spawned.ids == []
    assert client.last_agent_id is None


def test_error_messages_from_the_table() -> None:
    def message(raised: Exception) -> str:
        client, _ = _client(FakeCursorTransport({("POST", "/v1/agents"): raised}))
        with pytest.raises(CursorError) as info:
            client.chat("no-such-model", MESSAGES)
        return info.value.user_message

    assert message(_err(401)) == (
        "Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys."
    )
    assert message(_err(403, '{"error":{"code":"feature_unavailable"}}')) == (
        'Cursor agents need storage: set Cursor Privacy to "Privacy Mode" (not Legacy).'
    )
    assert message(_err(400, '{"error":{"code":"invalid_model"}}')) == (
        "Cursor model no-such-model is not available. Check cursor.model in config.toml."
    )
    assert message(_err(429, retry_after=30.0)) == ("Cursor rate limit reached. Try again in 30 s.")
    assert message(_err(429)) == "Cursor rate limit reached. Try again in a minute."
    assert message(ConnectionError("x")) == "Can't reach the Cursor API. Check your connection."
    assert message(_err(418, "teapot")) == "Cursor refused the request."


def test_create_response_without_ids_is_error() -> None:
    client, spawned = _client(FakeCursorTransport({("POST", "/v1/agents"): {"agent": {}}}))
    with pytest.raises(CursorError):
        client.chat("m", MESSAGES)
    assert spawned.ids == []


def test_get_fallback_http_error_is_mapped() -> None:
    transport = _transport([], **{f"GET {RUN_PATH}": _err(500, "down")})
    client, spawned = _client(transport)
    with pytest.raises(CursorUnavailable):
        client.chat("m", MESSAGES)
    assert spawned.ids == [AGENT]


# --- cleanup and cancel ----------------------------------------------------------------------


def test_cleanup_once_on_error_after_create() -> None:
    client, spawned = _client(_transport([_result(status="ERROR")]))
    with pytest.raises(CursorError):
        client.chat("m", MESSAGES)
    assert spawned.ids == [AGENT]


def _cancelling_transport(cancel_response) -> FakeCursorTransport:
    def cancel(event: str, data: str) -> None:
        if event == "status":
            raise Cancelled()

    return FakeCursorTransport(
        {("POST", "/v1/agents"): CREATED, ("POST", f"{RUN_PATH}/cancel"): cancel_response},
        {STREAM: [("status", '{"status": "RUNNING"}'), _result()]},
        on_stream=cancel,
    )


def test_cancel_posts_cancel_with_cancel_timeout_then_cleanup_then_reraises() -> None:
    transport = _cancelling_transport({"id": RUN})
    order: list[str] = []
    client = CursorClient(
        CFG,
        transport,
        spawn_cleanup=lambda agent_id: order.append(
            f"cleanup {agent_id} after {len(transport.calls)}"
        ),
    )

    with pytest.raises(Cancelled):
        client.chat("m", MESSAGES)

    cancel = transport.calls[-1]
    assert (cancel.method, cancel.path) == ("POST", f"{RUN_PATH}/cancel")
    assert cancel.timeout == CFG.cancel_timeout
    assert order == [f"cleanup {AGENT} after 3"]


@pytest.mark.parametrize(
    "error",
    [
        _err(409, '{"error":{"code":"run_not_cancellable","message":"Run is already finished"}}'),
        TimeoutError("hung"),
        ConnectionError("gone"),
        Cancelled(),
    ],
)
def test_cancel_errors_are_swallowed(error) -> None:
    transport = _cancelling_transport(error)
    client, spawned = _client(transport)
    with pytest.raises(Cancelled):
        client.chat("m", MESSAGES)
    assert spawned.ids == [AGENT]


def test_cancel_during_create_has_no_cleanup_and_no_cancel() -> None:
    transport = FakeCursorTransport({("POST", "/v1/agents"): Cancelled()})
    client, spawned = _client(transport)
    with pytest.raises(Cancelled):
        client.chat("m", MESSAGES)
    assert spawned.ids == []
    assert len(transport.calls) == 1


def test_spawn_cleanup_starts_detached_child_with_agent_id_only(monkeypatch) -> None:
    seen: list[tuple[list[str], dict]] = []

    class FakePopen:
        def __init__(self, argv, **kwargs) -> None:
            seen.append((argv, kwargs))

        def wait(self) -> None:  # pragma: no cover - must never be called
            raise AssertionError("parent waited")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setenv("CURSOR_API_KEY", "secret-key-value")

    spawn_cleanup(AGENT)

    argv, kwargs = seen[0]
    assert argv == [sys.executable, "-m", "llmtr", "cursor-cleanup", AGENT]
    assert kwargs["start_new_session"] is True
    assert kwargs["close_fds"] is True
    for stream in ("stdin", "stdout", "stderr"):
        assert kwargs[stream] is subprocess.DEVNULL
    assert "secret-key-value" not in " ".join(argv)


def test_spawn_cleanup_start_failure_is_swallowed(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("no python")

    monkeypatch.setattr(subprocess, "Popen", boom)
    spawn_cleanup(AGENT)


def test_default_spawn_cleanup_is_the_module_function() -> None:
    client = CursorClient(CFG, FakeCursorTransport())
    assert client.spawn_cleanup is spawn_cleanup


# --- delete and sweep ------------------------------------------------------------------------

NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC).timestamp()


def _iso(seconds_ago: float) -> str:
    return datetime.fromtimestamp(NOW - seconds_ago, tz=UTC).isoformat().replace("+00:00", "Z")


LIST_PATH = "/v1/agents?includeArchived=true&limit=100"


def _env(tmp_path) -> dict[str, str]:
    return {"XDG_CACHE_HOME": str(tmp_path / "cache")}


def test_delete_agents_uses_delete_timeout_and_counts_successes() -> None:
    transport = FakeCursorTransport(
        {("DELETE", "/v1/agents/a1"): {"id": "a1"}, ("DELETE", "/v1/agents/a2"): _err(500)}
    )
    assert delete_agents(["a1", "a2"], CFG, transport) == 1
    assert [(c.method, c.path, c.timeout) for c in transport.calls] == [
        ("DELETE", "/v1/agents/a1", CFG.delete_timeout),
        ("DELETE", "/v1/agents/a2", CFG.delete_timeout),
    ]


def test_sweep_deletes_only_old_inactive_llmtr_agents(tmp_path) -> None:
    agents = [
        {"id": "old", "name": "llmtr-0a1b2c3d", "status": "FINISHED", "createdAt": _iso(3600)},
        {"id": "nodate", "name": "llmtr-11111111", "status": "IDLE"},
        {"id": "active", "name": "llmtr-22222222", "status": "ACTIVE", "createdAt": _iso(3600)},
        {"id": "young", "name": "llmtr-33333333", "status": "FINISHED", "createdAt": _iso(60)},
        {"id": "other", "name": "my-agent", "status": "FINISHED", "createdAt": _iso(3600)},
        {
            "id": "epoch",
            "name": "llmtr-44444444",
            "status": "EXPIRED",
            "createdAt": (NOW - 900) * 1000,
        },
    ]
    responses = {("GET", LIST_PATH): {"agents": agents}}
    responses.update({("DELETE", f"/v1/agents/{a['id']}"): {"id": a["id"]} for a in agents})
    transport = FakeCursorTransport(responses)

    assert sweep(CFG, transport, now=NOW, env=_env(tmp_path)) == 3
    assert transport.paths("DELETE") == ["/v1/agents/old", "/v1/agents/nodate", "/v1/agents/epoch"]
    assert transport.calls[0].timeout == CFG.request_timeout


def test_sweep_caps_at_ten_deletes_and_counts_failures(tmp_path) -> None:
    agents = [
        {"id": f"a{i}", "name": f"llmtr-{i:08x}", "status": "FINISHED", "createdAt": _iso(3600)}
        for i in range(15)
    ]
    responses = {("GET", LIST_PATH): {"agents": agents}}
    responses.update(
        {
            ("DELETE", f"/v1/agents/a{i}"): (_err(500) if i % 2 else {"id": f"a{i}"})
            for i in range(15)
        }
    )
    transport = FakeCursorTransport(responses)

    assert sweep(CFG, transport, now=NOW, env=_env(tmp_path)) == 5
    assert len(transport.paths("DELETE")) == 10


def test_sweep_skips_within_an_hour(tmp_path) -> None:
    transport = FakeCursorTransport({("GET", LIST_PATH): {"agents": []}})
    assert sweep(CFG, transport, now=NOW, env=_env(tmp_path)) == 0
    assert len(transport.calls) == 1
    stamp = tmp_path / "cache" / "llmtr" / "cursor-sweep"
    assert stamp.exists()

    assert sweep(CFG, transport, now=NOW + 3599, env=_env(tmp_path)) == 0
    assert len(transport.calls) == 1

    assert sweep(CFG, transport, now=NOW + 3601, env=_env(tmp_path)) == 0
    assert len(transport.calls) == 2


def test_sweep_list_error_is_not_raised(tmp_path) -> None:
    transport = FakeCursorTransport({("GET", LIST_PATH): ConnectionError("down")})
    assert sweep(CFG, transport, now=NOW, env=_env(tmp_path)) == 0


# --- SSE parser --------------------------------------------------------------------------------


def test_parse_sse_fields_comments_multiline_and_terminator() -> None:
    raw = [
        b": comment\n",
        b"event: status\n",
        b'data: {"status":\n',
        b'data: "RUNNING"}\n',
        b"\n",
        b"data:no-space\r\n",
        b"\r\n",
        b"event: lonely\n",
        b"\n",
        b"event: result\n",
        b"data: unterminated\n",
    ]
    assert list(parse_sse(raw)) == [
        ("status", '{"status":\n"RUNNING"}'),
        ("message", "no-space"),
    ]


# --- UrllibCursorTransport against a local server --------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    routes: dict[str, Callable[[_Handler], None]] = {}
    seen: list[dict] = []

    def log_message(self, *args) -> None:  # silence stderr
        pass

    def _dispatch(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        self.seen.append(
            {
                "method": self.command,
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "accept": self.headers.get("Accept"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )
        self.routes[self.path](self)

    do_GET = do_POST = do_DELETE = _dispatch

    def send_json(
        self, status: int, payload: object, headers: dict[str, str] | None = None
    ) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server() -> Iterator[tuple[str, type[_Handler]]]:
    handler = type("Handler", (_Handler,), {"routes": {}, "seen": []})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", handler
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_urllib_json_request_and_bearer_header(server) -> None:
    base, handler = server
    handler.routes["/v1/agents"] = lambda h: h.send_json(201, CREATED)
    transport = UrllibCursorTransport("test-key")

    result = transport.request("POST", f"{base}/v1/agents", {"prompt": {"text": "x"}}, 5.0)

    assert result == CREATED
    seen = handler.seen[0]
    assert seen["auth"] == "Bearer test-key"
    assert seen["content_type"] == "application/json"
    assert json.loads(seen["body"]) == {"prompt": {"text": "x"}}


def test_urllib_empty_body_and_no_payload(server) -> None:
    base, handler = server

    def empty(h: _Handler) -> None:
        h.send_response(200)
        h.send_header("Content-Length", "0")
        h.end_headers()

    handler.routes["/v1/agents/a1"] = empty
    assert UrllibCursorTransport("k").request("DELETE", f"{base}/v1/agents/a1", None, 5.0) == {}
    assert handler.seen[0]["method"] == "DELETE" and handler.seen[0]["body"] == ""


def test_urllib_sse_stream_split_across_reads(server) -> None:
    base, handler = server

    def sse(h: _Handler) -> None:
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.end_headers()
        chunks = [
            b": keep-alive\n\n",
            b'event: status\ndata: {"sta',
            b'tus": "RUNNING"}\n\n',
            b'event: result\ndata: {"status": "FINISHED",\n',
            b'data: "text": "Hi"}\n',
            b"\n",
            b"event: done\ndata: {}\n\n",
        ]
        for chunk in chunks:
            h.wfile.write(chunk)
            h.wfile.flush()
            time.sleep(0.02)

    handler.routes["/stream"] = sse
    events = list(UrllibCursorTransport("k").stream(f"{base}/stream", 5.0))

    assert events == [
        ("status", '{"status": "RUNNING"}'),
        ("result", '{"status": "FINISHED",\n"text": "Hi"}'),
        ("done", "{}"),
    ]
    assert handler.seen[0]["accept"] == "text/event-stream"
    assert handler.seen[0]["auth"] == "Bearer k"


def test_urllib_4xx_body_and_retry_after(server) -> None:
    base, handler = server
    handler.routes["/v1/agents"] = lambda h: h.send_json(
        429, {"error": {"code": "rate_limited"}}, {"Retry-After": "12"}
    )
    with pytest.raises(HTTPStatusError) as info:
        UrllibCursorTransport("k").request("POST", f"{base}/v1/agents", {}, 5.0)
    assert info.value.status == 429
    assert "rate_limited" in info.value.body
    assert info.value.retry_after == 12.0  # type: ignore[attr-defined]


def test_urllib_4xx_without_retry_after(server) -> None:
    base, handler = server
    handler.routes["/x"] = lambda h: h.send_json(400, {"error": {"code": "invalid_model"}})
    with pytest.raises(HTTPStatusError) as info:
        UrllibCursorTransport("k").request("GET", f"{base}/x", None, 5.0)
    assert info.value.retry_after is None  # type: ignore[attr-defined]


def test_urllib_stream_read_timeout(server) -> None:
    base, handler = server
    release = threading.Event()

    def slow(h: _Handler) -> None:
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.end_headers()
        h.wfile.write(b"event: status\ndata: {}\n\n")
        h.wfile.flush()
        release.wait(5)

    handler.routes["/slow"] = slow
    events: list = []
    try:
        with pytest.raises(TimeoutError):
            for item in UrllibCursorTransport("k").stream(f"{base}/slow", 0.3):
                events.append(item)
    finally:
        release.set()
    assert events == [("status", "{}")]


def test_urllib_request_read_timeout(server) -> None:
    base, handler = server
    release = threading.Event()
    handler.routes["/hang"] = lambda h: release.wait(5)
    try:
        with pytest.raises(TimeoutError):
            UrllibCursorTransport("k").request("GET", f"{base}/hang", None, 0.3)
    finally:
        release.set()


def test_urllib_connection_refused() -> None:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(ConnectionError):
        UrllibCursorTransport("k").request("GET", f"http://127.0.0.1:{port}/", None, 2.0)


# --- real Cursor API (host only) -------------------------------------------------------------


@pytest.mark.cursor
@pytest.mark.skipif(
    os.environ.get("LLMTR_CURSOR_TESTS") != "1", reason="set LLMTR_CURSOR_TESTS=1 to run"
)
def test_translate_pl_sentence_with_real_cursor_api() -> None:
    from llmtr import cursor_key, langdetect
    from llmtr.config import Config
    from llmtr.engine import Mode, plan_job, run_job
    from llmtr.platforms import detect_platform

    text_file = Path(__file__).parents[1] / "spike" / "macos" / "texts" / "pl_sentence.txt"
    text = text_file.read_text(encoding="utf-8")
    config = dataclasses.replace(Config(), engine="cursor")
    job = plan_job(Mode.TRANSLATE, text, config)
    client = CursorClient(
        config.cursor, UrllibCursorTransport(cursor_key.load_key(detect_platform()))
    )
    result = run_job(job, client, config)
    assert result.strip()
    assert langdetect.detect_language(result) == "en"
