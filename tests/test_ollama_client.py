"""Unit tests for llmtr.ollama_client (owner: M2). No test calls a real Ollama server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from llmtr.errors import ModelMissing, OllamaError, OllamaTimeout, OllamaUnavailable
from llmtr.fakes import FakeTransport
from llmtr.ollama_client import CHAT_PATH, HTTPStatusError, OllamaClient, UrllibTransport

# --- OllamaClient with FakeTransport ---------------------------------------------------------


def test_chat_success_returns_content() -> None:
    transport = FakeTransport([FakeTransport.chat_response("Hello!", model="gemma3")])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    result = client.chat("gemma3", [{"role": "user", "content": "hi"}])

    assert result == "Hello!"
    url, payload, timeout = transport.requests[0]
    assert url == f"http://localhost:11434{CHAT_PATH}"
    assert payload["model"] == "gemma3"
    assert payload["stream"] is False
    assert timeout == 5.0


def test_chat_sends_options_and_keep_alive() -> None:
    transport = FakeTransport([FakeTransport.chat_response("ok")])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    client.chat(
        "gemma3",
        [{"role": "user", "content": "hi"}],
        options={"temperature": 0.0, "num_ctx": 4096},
        keep_alive="30m",
    )

    _, payload, _ = transport.requests[0]
    assert payload["options"] == {"temperature": 0.0, "num_ctx": 4096}
    assert payload["keep_alive"] == "30m"


def test_chat_connection_error_raises_ollama_unavailable() -> None:
    transport = FakeTransport([ConnectionError("refused")])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(OllamaUnavailable) as exc_info:
        client.chat("gemma3", [{"role": "user", "content": "hi"}])
    assert "localhost:11434" in exc_info.value.user_message


def test_chat_timeout_raises_ollama_timeout() -> None:
    transport = FakeTransport([TimeoutError("timed out")])
    client = OllamaClient("http://localhost:11434", timeout=42.0, transport=transport)

    with pytest.raises(OllamaTimeout) as exc_info:
        client.chat("gemma3", [{"role": "user", "content": "hi"}])
    assert "42" in exc_info.value.user_message


def test_chat_model_missing_on_404_not_found() -> None:
    transport = FakeTransport([HTTPStatusError(404, '{"error":"model \\"gemma3\\" not found"}')])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(ModelMissing) as exc_info:
        client.chat("gemma3", [{"role": "user", "content": "hi"}])
    assert "ollama pull gemma3" in exc_info.value.user_message


def test_chat_other_404_is_ollama_error_not_model_missing() -> None:
    transport = FakeTransport([HTTPStatusError(404, '{"error":"route unavailable"}')])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(OllamaError):
        client.chat("gemma3", [{"role": "user", "content": "hi"}])


def test_chat_500_raises_ollama_error() -> None:
    transport = FakeTransport([HTTPStatusError(500, "internal error")])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(OllamaError):
        client.chat("gemma3", [{"role": "user", "content": "hi"}])


def test_chat_bad_json_raises_ollama_error() -> None:
    transport = FakeTransport([ValueError("invalid JSON")])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(OllamaError):
        client.chat("gemma3", [{"role": "user", "content": "hi"}])


def test_chat_missing_message_content_raises_ollama_error() -> None:
    transport = FakeTransport([{"model": "gemma3", "done": True}])
    client = OllamaClient("http://localhost:11434", timeout=5.0, transport=transport)

    with pytest.raises(OllamaError):
        client.chat("gemma3", [{"role": "user", "content": "hi"}])


# --- UrllibTransport against a local http.server ---------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        request = json.loads(body) if body else {}

        if self.path == "/api/chat":
            response = {
                "model": request.get("model", "fake"),
                "message": {"role": "assistant", "content": "Hello from the server!"},
                "done": True,
            }
            payload = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/missing":
            payload = json.dumps({"error": 'model "ghost" not found'}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/api/bad-json":
            payload = b"not json"
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(500)
            self.end_headers()


@pytest.fixture
def http_server() -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def test_urllib_transport_posts_and_decodes_json(http_server: str) -> None:
    transport = UrllibTransport()
    result = transport.post_json(
        f"{http_server}/api/chat", {"model": "gemma3", "messages": []}, timeout=5.0
    )
    assert result["message"]["content"] == "Hello from the server!"


def test_urllib_transport_raises_http_status_error(http_server: str) -> None:
    transport = UrllibTransport()
    with pytest.raises(HTTPStatusError) as exc_info:
        transport.post_json(f"{http_server}/api/missing", {}, timeout=5.0)
    assert exc_info.value.status == 404
    assert "not found" in exc_info.value.body


def test_urllib_transport_raises_value_error_on_bad_json(http_server: str) -> None:
    transport = UrllibTransport()
    with pytest.raises(ValueError):
        transport.post_json(f"{http_server}/api/bad-json", {}, timeout=5.0)


def test_urllib_transport_raises_connection_error_when_unreachable() -> None:
    transport = UrllibTransport()
    with pytest.raises(ConnectionError):
        transport.post_json("http://127.0.0.1:1/api/chat", {}, timeout=1.0)


def test_ollama_client_end_to_end_with_real_transport(http_server: str) -> None:
    client = OllamaClient(http_server, timeout=5.0)
    result = client.chat("gemma3", [{"role": "user", "content": "hi"}])
    assert result == "Hello from the server!"
