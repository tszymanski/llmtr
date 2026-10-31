# M15-cursor-engine — result

Worker: Claude Code in `sbx` (clone mode), model **Claude Opus 5.5**. Branch `task/M15-cursor-engine`.
Fakes only: no API key, and nothing contacted `api.cursor.com`.

## What changed

- **`config.py`**: frozen `CursorConfig` (`model`, `timeout`, `request_timeout`, `cancel_timeout`,
  `delete_timeout`, `max_chars`, `base_url`) and `Config.engine` / `Config.cursor` with defaults,
  so every existing `Config(...)` still works. New `ENGINES` and `DEFAULT_CURSOR_URL`.
  `parse_config` validates `engine` and every `cursor.*` key. `base_url` must be `https://…`, and a
  trailing `/` is removed.
- **`errors.py`** (additive): `CursorError` (base class, default `Cursor refused the request.`),
  `CursorKeyMissing(path, keychain=False)`, `CursorKeyInsecure`, `CursorAuthError`,
  `CursorStorageDisabled`, `CursorModelInvalid`, `CursorRateLimited`, `CursorUnavailable` and
  `CursorTimeout`, with the contract's messages.
- **`cursor_key.py`** (new): `load_key` tries `CURSOR_API_KEY`, then the Keychain (macOS only;
  exact argv, 5 s, exit ≠ 0 or failure falls through), then the `0600` file (refused unread if
  `& 0o077`). `key_path` is the file location.
- **`cursor_client.py`** (new): `CursorTransport` protocol and `UrllibCursorTransport(key)`
  (Bearer auth, `repr` redacted; `HTTPStatusError` from `ollama_client` with `retry_after` set).
  Also:
  - `parse_sse`;
  - `CursorClient.chat`: create, stream until `result`, one GET fallback, `spawn_cleanup` in
    `finally`, cancel on `Cancelled`;
  - `map_error`, `spawn_cleanup` (detached `Popen`), `delete_agents` and `sweep` (hourly stamp,
    `llmtr-` / not `ACTIVE` / older than 10 min, at most 10 deletes).
- **`prompts.py`**: `CURSOR_PROMPT_TEMPLATE` (the M14 prompt, word for word with its line breaks),
  `CURSOR_TASKS` and `build_cursor_messages`. Ollama prompts are unchanged.
- **`engine.py`**: `plan_job(..., engine=None)` and `Job.engine`. For cursor it uses the cursor
  model, `cursor.max_chars` and one message. `progress_text` shows `"{model} (Cursor)"`.
  `run_job` is unchanged.
- **`cli.py`**:
  - `--engine {ollama,cursor}` on the three modes;
  - `make_chat_client(config, engine, platform)`, used by both `run_shortcut` and `--stdin`.
    The key loads after the lock and the capture;
  - the run log line gains `engine=…`, plus `agent=<6 chars>` for Cursor;
  - `llmtr cursor-cleanup [AGENT_ID ...]` (deletes, then sweeps; logs only; always exits 0).
- **`fakes.py`**: `FakeCursorTransport` (scripted `(method, path)` responses, SSE lists with
  breaking exceptions, `stream_error`, `on_stream` hook, records `CursorCall`s with `payload`) and
  `http_error()`.
- **Tests**: new `test_cursor_key.py`, `test_cursor_client.py` and `test_cursor_prompts.py`;
  additions to `test_config.py`, `test_engine.py`, `test_cli.py` and `test_interfaces.py`.
  Pre-existing tests and assertions are unchanged. The only edit to old lines is the
  `llmtr.fakes` import in `test_cli.py`, which gained `FakeCursorTransport`.
- **Docs**: architecture §23 (modules, config, sequence, prompt, error table, testing), with
  pointer lines under §4.1 and §7. README "Cursor engine (optional)" after "Config".
  `pyproject.toml` registers the `cursor` marker.

## Test results (final run after the last edit)

| Command | Result |
| --- | --- |
| `uv run pytest` | **601 passed, 2 skipped** (was 474 passed, 1 skipped) |
| `LLMTR_UNAME=Darwin uv run pytest` | **601 passed, 2 skipped** |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 128 files already formatted |
| `uv sync --locked` | OK (no new dependency) |

The two skips are the real-Ollama test and the new real-Cursor test.

**Network grep** over `tests/` (`UrllibCursorTransport(`, `UrllibTransport(`, `urlopen`,
`socket.`, `OllamaClient(`): every connection goes to a local `http.server` on `127.0.0.1` or to
an `AF_UNIX` socket (existing `test_keys.py`). The exceptions are the two skipped real tests:
`test_engine.py` (Ollama) and `test_cursor_client.py::test_translate_pl_sentence_with_real_cursor_api`.
`test_cursor_key.py` builds an `UrllibCursorTransport` only to check its `repr`; it opens no
connection.

## Deviations

- `CursorClient.__init__` has an extra keyword `monotonic=time.monotonic`, used for deadline tests.
- Cursor error classes subclass `CursorError` so they can be caught as one group.
  `CursorKeyMissing` has an extra `keychain: bool` that adds the macOS wording.
- Request-level timeouts (create, GET fallback) map to `CursorTimeout(request_timeout)`, e.g.
  "did not answer within 10 s", not `CursorUnavailable`.
- If the overall deadline passes **while** events are still arriving, `CursorTimeout` is raised
  right away, with no GET fallback. The fallback runs when the stream ends or breaks: connection
  error, read timeout, HTTP error or bad data. The stream's read timeout is the time left until
  the deadline at stream start.
- The cursor prompt strips the text, as M14 did; `strip_preamble` restores the
  original's outer whitespace.
- `delete_agents` and `sweep` return the number of **successful** deletes. The sweep cap counts
  delete requests, failed ones included.
- `FakeCursorTransport` uses `"STREAM"` as the recorded method for stream calls.
- The `uv` venv here is CPython 3.14.4 (only 3.14 in the sandbox; `requires-python >=3.13`).

## Reruns

Reruns: none. One ruff `F821` (a forward-referenced type in a test helper) was fixed during
normal editing, before the first full check run. Session restarts: none.

## New dependencies

None (standard library only).

## Open issues — for the orchestrator on the host

1. **Real-API test**: `LLMTR_CURSOR_TESTS=1 uv run pytest -m cursor` (needs the key via env,
   Keychain or file). It translates `spike/macos/texts/pl_sentence.txt` and checks for non-empty
   English. It also starts a real detached `cursor-cleanup` child. Afterwards, check that no
   `llmtr-` agent is left once the child's DELETE is done (up to ~1 min).
2. Check `llmtr fix --engine cursor --stdin` once by hand, and look at `llmtr log` for
   `engine=cursor agent=xxxxxx` and the cleanup child's `mode=cursor-cleanup … deleted=1` line.
3. Never exercised against the real API: `GET /v1/agents?…&limit=100` (the M14 spike listed
   without `limit`), the list response key (code accepts `agents`/`items`/`data`), and the
   `createdAt` format (ISO 8601 or epoch seconds/ms are accepted; unparseable → not swept).
4. Keychain argv is `security …` (PATH lookup), as the contract specifies. If a Hammerspoon child
   has no `/usr/bin` in `PATH`, use `/usr/bin/security` instead (later Mac task).
5. On a second press, the SIGTERM handler raises `Cancelled` inside the SSE read. The cancel
   `POST` then has `cancel_timeout` (5 s), so "Cancelled." can show up to ~5 s later. That is by
   design, but worth noticing in the Mac/Linux acceptance.
6. The fix/tone model choice for Cursor (M14 tested only Auto for fix/tone) is still open; one
   `cursor.model` is used for all modes.
