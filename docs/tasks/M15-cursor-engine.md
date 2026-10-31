# Task M15-cursor-engine — Cursor Cloud Agents API as an opt-in engine

Role: **Integration worker** (claude in `sbx`, clone mode). Branch: `task/M15-cursor-engine`.

Read first:
- `CLAUDE.md` and `docs/proposal.md` ("Cursor engine (v3, spike)");
- `docs/architecture.md` §2, §3.1, §3.4, §4.1, §7, §8, §12 and §20;
- `docs/tasks/M14-cursor-spike.result.md`, the source of every API fact below (especially the
  "Recommendation for M15" section);
- `spike/cursor/cursor_api.py` and `runner.py`, working stdlib code you may adapt into `src/`.

The sandbox **cannot** reach `api.cursor.com` (M14 C0), and no API key goes into the sandbox. All
tests use fakes. The real-API test is written here but run by the orchestrator on the host.

## Goal

Add `engine = "cursor"` next to the default Ollama engine.
- With it, `translate`, `fix` and `tone` send the text to a fresh **no-repo Cursor cloud agent**,
  read the answer from the run's SSE stream, and paste it like today.
- The agent is deleted **after** the paste, by a detached child process.
- Ollama behaviour, prompts and tests stay unchanged when `engine` is not set.

User decisions (2026-10-31), not to be revisited:
1. `engine = "cursor"` is opt-in, and the default model is `gpt-5.4-nano`.
2. The key comes from the `CURSOR_API_KEY` env var, then the macOS Keychain, then a `0600` file.
3. Agents are deleted in the background after the paste, and leftover `llmtr-` agents are swept.
4. The README carries a privacy note.

## Interface to match

### Config (`config.py`, architecture §4.1)

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `engine` (top level) | `"ollama"`\|`"cursor"` | `"ollama"` | anything else → `ConfigError` |
| `cursor.model` | string | `"gpt-5.4-nano"` | `"auto"` → omit `model` in the request (account default) |
| `cursor.timeout` | float, s, > 0 | `60.0` | create → final text, overall |
| `cursor.request_timeout` | float, s, > 0 | `10.0` | create, get-run |
| `cursor.cancel_timeout` | float, s, > 0 | `5.0` | the cancel `POST` (M14 C9: one hung 17 s) |
| `cursor.delete_timeout` | float, s, > 0 | `60.0` | `DELETE` in the cleanup child (M14: median 11.7 s, max 48.8 s) |
| `cursor.max_chars` | int, > 0 | `8000` | `plan_job` uses this limit instead of `ollama.max_chars` when the engine is cursor |
| `cursor.base_url` | string | `"https://api.cursor.com"` | `https` only (`ConfigError` otherwise); tests point it at a fake |

New frozen dataclass `CursorConfig`. `Config` gains `engine: str = "ollama"` and
`cursor: CursorConfig`, with defaults so every existing `Config(...)` construction still works.
`models.*` still apply only to Ollama.

### CLI

- `--engine {ollama,cursor}` on `translate`, `fix` and `tone`. It overrides config, like `--model`.
  `--model` overrides `cursor.model` when the engine is cursor.
- New subcommand `llmtr cursor-cleanup [AGENT_ID ...]` (help: *"delete llmtr's Cursor agents"*):
  - deletes the given agents, then runs the sweep;
  - with no ids, only sweeps;
  - exits 0 even when deletes fail (failures are logged), and never notifies.

### Key (`cursor_key.py`, new)

```python
CURSOR_KEY_ENV = "CURSOR_API_KEY"
KEYCHAIN_SERVICE = "llmtr-cursor"
def key_path(env: Mapping[str, str] | None = None) -> Path   # $XDG_CONFIG_HOME/llmtr/cursor-api-key
def load_key(platform: Platform, env: Mapping[str, str] | None = None, *,
             run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> str
```

`load_key` tries these sources in order:
1. **Env var.** A non-empty `CURSOR_API_KEY`.
2. **Keychain (macOS only).** `security find-generic-password -s llmtr-cursor -w`, with a 5 s
   timeout. Exit code ≠ 0 means "not there", and the lookup moves on to the file.
3. **Key file.** `key_path()`, stripped.
   - If the mode has any group or other bits (`st_mode & 0o077`), raise `CursorKeyInsecure`
     without reading it.
   - A missing or empty file raises `CursorKeyMissing`.

The key never appears in argv, log lines, exception `detail`, or `repr` of any object.

### Errors (`errors.py`, additive only; architecture §7 / §19 style)

| Class | When | `user_message` |
| --- | --- | --- |
| `CursorKeyMissing(path)` | no key found | `No Cursor API key. Put it in {path} (mode 600).` (macOS adds `or in the Keychain as llmtr-cursor`) |
| `CursorKeyInsecure(path)` | group/other bits set | `Cursor API key file is readable by others. Run: chmod 600 {path}` |
| `CursorAuthError()` | 401 | `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.` |
| `CursorStorageDisabled()` | 403 with `feature_unavailable` | `Cursor agents need storage: set Cursor Privacy to "Privacy Mode" (not Legacy).` |
| `CursorModelInvalid(model)` | 400 with `invalid_model` | `Cursor model {m} is not available. Check cursor.model in config.toml.` |
| `CursorRateLimited(retry_after)` | 429 | `Cursor rate limit reached. Try again in {n} s.` (`Try again in a minute.` without `Retry-After`) |
| `CursorUnavailable(detail="")` | connection error, 5xx | `Can't reach the Cursor API. Check your connection.` |
| `CursorTimeout(timeout)` | no final text within `cursor.timeout` | `Cursor did not answer within {t} s. Try again.` |
| `CursorError(user_message="Cursor refused the request.", detail="")` | other 4xx, bad JSON, run `ERROR`/`EXPIRED` (`Cursor agent failed.`) | as given |

An empty result after `strip_preamble` keeps today's `OllamaError("The model returned no text.")`
path in `run_job`. That message says "the model", so it fits both engines; do not rename it.

### Client (`cursor_client.py`, new)

```python
class CursorTransport(Protocol):
    def request(self, method: str, url: str, payload: Mapping[str, Any] | None,
                timeout: float) -> dict[str, Any]
    def stream(self, url: str, timeout: float) -> Iterator[tuple[str, str]]   # (event, data)
class UrllibCursorTransport:   # the only real network code; Bearer auth from the key it is given
    def __init__(self, key: str) -> None
class CursorClient:            # implements ollama_client.ChatClient
    def __init__(self, config: CursorConfig, transport: CursorTransport,
                 *, spawn_cleanup: Callable[[str], None] = spawn_cleanup) -> None
    def chat(self, model, messages, *, options=None, keep_alive=None) -> str
    last_agent_id: str | None
def spawn_cleanup(agent_id: str) -> None
def delete_agents(ids, config, transport) -> int
def sweep(config, transport, *, now) -> int
```

The transport raises the same low-level set as Ollama's: `HTTPStatusError` (reuse it from
`ollama_client`; `body` and a `retry_after: float | None` attribute set from the header),
`ConnectionError`, `TimeoutError` and `ValueError`. `CursorClient` maps these to the errors above.

`chat` works like this:
1. **Prompt.** The prompt text is the joined `content` of `messages`; `plan_job` sends exactly one
   user message for this engine.
2. **Create.** `POST /v1/agents` with `{"prompt": {"text": …}, "name": "llmtr-<mode-free random
   8 hex>", "mode": "agent"}`, plus `"model": {"id": model}` unless the model is `auto`. No `repos`
   and no `env`. Timeout: `request_timeout`.
3. **Stream.** Read `GET /v1/agents/{id}/runs/{runId}/stream` (`Accept: text/event-stream`) until
   the `result` event, with an overall deadline of `cursor.timeout` from just before the create.
   - Take the text and the final status from the `result` event's JSON (`text`, `status`). Ignore
     the `status` events: M14 C9 saw `status FINISHED` with a `CANCELLED` result.
   - Ignore unknown events and `interaction_update`.
   - A `result` status other than `FINISHED` → `CursorError("Cursor agent failed.")`.
4. **Fallback.** If the stream ends or breaks without a `result`, make one
   `GET /v1/agents/{id}/runs/{runId}`.
   - `FINISHED` → use `result` (a plain string).
   - Not terminal → `CursorTimeout` if the deadline has passed, else `CursorError`.
5. **Cleanup.** Always, in `finally`, once the agent exists: call `spawn_cleanup(agent_id)`. The
   delete never blocks the paste.
6. **Cancel.** On `Cancelled`, raised by the SIGTERM handler while blocked in the stream read:
   - `POST …/runs/{runId}/cancel` with `cancel_timeout`, ignoring every error (including
     `409 run_not_cancellable`);
   - then the cleanup from step 5;
   - then re-raise `Cancelled`.

**`spawn_cleanup`** starts `[sys.executable, "-m", "llmtr", "cursor-cleanup", agent_id]`:
- a detached child, via `subprocess.Popen` with `start_new_session=True`;
- stdin, stdout and stderr all set to `DEVNULL`, and `close_fds=True`;
- the parent does not wait for it.

The child loads config and key itself. Only the agent id goes in argv, never the key.

**`sweep`** runs at most once per hour per machine. It keeps a timestamp file
`$XDG_CACHE_HOME/llmtr/cursor-sweep` and skips when that is younger than 3600 s.
1. `GET /v1/agents?includeArchived=true&limit=100`.
2. Delete agents whose `name` starts with `llmtr-`, whose `status` is not `ACTIVE`, and, when
   `createdAt` is present, that are older than 10 minutes. Another machine on the same account may
   have a run in flight; never delete an `ACTIVE` agent.
3. Count the requests and stop after 10 deletes per sweep (the rate limit is 20 per minute).

### Engine and prompts

**`prompts.py`** gains `build_cursor_messages(mode, text, *, source=None, target=None, tone=None)`,
returning one user `Message` built from `CURSOR_PROMPT_TEMPLATE`.

The template is the M14 contract prompt, word for word, as a constant: the "text-processing
function" framing, the task line, the reply-only line, and the `<text>`/`</text>` markers.
- **Translate** task lines: *"Task: translate the text from {src} to {dst}. Translate every line;
  keep lines that are already in {dst} unchanged."* (the M14 C8 fix for dropped lines).
- **Fix** task line: the M14 one.
- **Tone** task line: *"Task: rewrite the text in this tone: {preset.instruction} Keep its
  language and meaning."*, so presets work as with Ollama.

Language names come from `SUPPORTED_LANGUAGES`. The translategemma template and the Ollama
fix/tone prompts are **not** changed.

**`engine.py`:** `plan_job(...)` gains a keyword `engine: str | None = None` (`None` → `config.engine`).
- For cursor, it uses `build_cursor_messages`, the model `model or config.cursor.model`, and
  `config.cursor.max_chars`. `Job` gains `engine: str = "ollama"`.
- `progress_text` is unchanged except that its body becomes `"{model} (Cursor)"` for the cursor
  engine.
- `run_job` is unchanged. The cursor client ignores `options` and `keep_alive`, and
  `strip_preamble` still runs.

**`cli.py`:** client selection happens in one place, used by both `run_shortcut` and `--stdin`.
- `engine == "cursor"` → `CursorClient(config.cursor,
  UrllibCursorTransport(cursor_key.load_key(platform)))`, otherwise `OllamaClient`, as today.
- Load the key **after** the lock, so a second press still cancels.
- The run log line gains `engine=<name>`. It still carries no user text, no key and no agent id
  beyond its first 6 characters.

**Fakes (`fakes.py`):** `FakeCursorTransport` takes scripted responses per `(method, path)`,
scripted SSE event lists per stream path, and optional raises. It records every call, with
`payload`.

## Tests (fakes only; no socket except a local `http.server` thread on 127.0.0.1)

Add `tests/test_cursor_key.py`, `tests/test_cursor_client.py` and `tests/test_cursor_prompts.py`
(or extend `test_prompts.py`). Extend `test_config.py`, `test_engine.py`, `test_cli.py` and
`test_interfaces.py`. At least these cases:

- **Key:**
  - env var wins;
  - Keychain is used on Darwin only, and its argv is exactly `security find-generic-password -s
    llmtr-cursor -w`;
  - Keychain exit 44 falls through to the file;
  - file mode `0600` is read, `0644` → `CursorKeyInsecure`, missing or empty → `CursorKeyMissing`
    with the path in the message;
  - the key is not present in `repr(transport)`, error messages or log output.
- **Config:** defaults; `engine` validation; each `cursor.*` key, including `base_url` `http://` →
  `ConfigError`; an existing config without `[cursor]` still parses to the same values as before.
- **Prompts:** exact-string tests for translate PL→EN, EN→PL, fix and tone (a custom preset).
  The Ollama prompt tests stay green **unchanged**.
- **Engine:** `plan_job(engine="cursor")` picks the model, the limit and one message;
  `progress_text` shows "(Cursor)"; `engine=None` follows config.
- **Client, request flow:**
  - create body (with and without `model` for `auto`, no `repos`/`env`, `name` prefix);
  - Bearer header;
  - the text from the `result` event;
  - `status FINISHED` + `result CANCELLED` → error, not text;
  - unknown events ignored.
- **Client, failure paths:**
  - stream breaks before `result` → one `GET` fallback (`FINISHED` and not-terminal cases);
  - deadline → `CursorTimeout`;
  - each HTTP status in the error table maps to its class, with `Retry-After` used;
  - `ConnectionError` → `CursorUnavailable`.
- **Client, cleanup:**
  - `spawn_cleanup` is called exactly once on success, on every error after the create, and on
    cancel, and **not** when the create itself failed;
  - on `Cancelled`, cancel is posted with `cancel_timeout`, a cancel error is swallowed, and
    `Cancelled` is re-raised.
- **`spawn_cleanup`:** the `Popen` argv is the module run with the agent id only, with
  `start_new_session=True` and `DEVNULL`s (patch `subprocess.Popen`).
- **`sweep`:**
  - skips within an hour of the last run;
  - deletes only `llmtr-` agents that are not `ACTIVE` and are older than 10 minutes;
  - caps at 10 deletes;
  - delete errors are counted, not raised.
- **`UrllibCursorTransport`:**
  - against a local `http.server` thread: JSON request/response, an SSE stream split across reads
    (multi-line `data:`, comments, a blank-line terminator);
  - a 4xx body with `Retry-After`;
  - a read timeout → `TimeoutError`.
- **CLI:**
  - `--engine cursor --stdin` with a fake client factory prints the result;
  - the shortcut flow with the cursor engine pastes and calls cleanup;
  - a key error notifies its message and restores the clipboard;
  - `cursor-cleanup` with ids calls delete then sweep and exits 0 on failures.
- **Real API:** one test marked `@pytest.mark.cursor`, skipped unless `LLMTR_CURSOR_TESTS=1`.
  It translates `spike/macos/texts/pl_sentence.txt` with the real key and checks for non-empty
  English text. Register the marker in `pyproject.toml` next to `ollama`.

Run the suite twice, as today: `uv run pytest` and `LLMTR_UNAME=Darwin uv run pytest`.

## Docs

- **`docs/architecture.md`:** a new **§23 Cursor engine (v3)**: module list, config keys,
  sequence (create → stream → paste → detached cleanup; cancel), the error table, and the testing
  notes.
  - Add one line under §4.1 pointing to §23 for `engine` and `[cursor]`.
  - Add one line under §7 pointing to the §23 error table.
- **`README.md`:** a new section **"Cursor engine (optional)"**, after "Config":
  1. **Privacy first.** With this engine, the selected text leaves the machine. It is sent to
     Cursor's cloud and runs in a cloud agent, and Cursor stores it (storage mode is required).
     The agent is deleted after each call, but Cursor's own retention rules apply. Don't use it for
     text you may not send to Cursor. Usage counts against the Cursor plan (about 16k cached
     tokens of agent context per call).
  2. **Requirements.** A Cursor plan with Cloud Agents. Cursor Settings → Privacy set to
     **"Privacy Mode"**; "Privacy Mode (Legacy)" blocks API agents.
  3. **Key, Linux:** create it in Cursor Dashboard → API Keys, then
     `install -m 600 /dev/null ~/.config/llmtr/cursor-api-key` and paste the key into it with an
     editor.
  4. **Key, macOS:** `security add-generic-password -s llmtr-cursor -a "$USER" -w`, which prompts
     for the key so it stays out of the shell history. The file also works.
  5. **Config:** `engine = "cursor"` and `[cursor] model`, with `auto` for the account default.
     Mention `--engine cursor` for a quick try with `--stdin`.
  6. **What to expect:** about 6–14 s per call, sentence to 220 words (M14). No streaming into the
     window. At most about 6 calls a minute (rate limit). Agents are deleted in the background a
     few seconds to a minute later; `llmtr cursor-cleanup` removes leftovers.
  7. **Troubleshooting:** the messages from the error table, each with its fix.

## Files you may change

- **Source:** `src/llmtr/config.py`, `src/llmtr/errors.py`, `src/llmtr/prompts.py`,
  `src/llmtr/engine.py`, `src/llmtr/cli.py`, `src/llmtr/fakes.py`, and the new
  `src/llmtr/cursor_key.py` and `src/llmtr/cursor_client.py`.
- **Tests:** `tests/test_config.py`, `tests/test_prompts.py`, `tests/test_engine.py`,
  `tests/test_cli.py`, `tests/test_interfaces.py`, and the new `tests/test_cursor_*.py`.
- **Docs and project files:** `docs/architecture.md` (§23 plus the two pointer lines),
  `README.md`, `pyproject.toml` (marker only), and `docs/tasks/M15-cursor-engine.result.md`.

Nothing else. In particular, not `install.sh`, `scripts/`, `macos/`, the Lua template,
`ollama_client.py` (import `HTTPStatusError` from it; don't change it), or `spike/`.

## Must pass

`uv run pytest`, `LLMTR_UNAME=Darwin uv run pytest`, `uv run ruff check .` and
`uv run ruff format --check .` all pass, and so does `uv sync --locked` (no new dependency: stdlib
only). A final grep shows no test that opens a connection to anything other than `127.0.0.1`.

## Out of scope

- Streaming text into the window, and any Cursor CLI or v0 API.
- Per-mode Cursor models; one `cursor.model` for all modes is enough for now.
- Secret Service on Linux, and any installer change.
- Running the real-API test. The orchestrator does that on the host.
- Mac acceptance (Keychain prompt from a Hammerspoon child). That is a later Mac task.

## Done when

1. Every item in "Interface to match" exists as specified, and every case listed under "Tests"
   has a test.
2. With no `engine` key, behaviour is unchanged: all pre-existing tests pass, with no edits to
   their assertions.
3. Architecture §23 and the README section are written.
4. All "Must pass" commands succeed in a final run after the last edit.
5. Only allowed files changed; result file written; committed on `task/M15-cursor-engine`;
   `git status` clean.

## Reruns

Per `CLAUDE.md`:
- Run `uv run ruff format .` and `uv run ruff check --fix .` first.
- At most 3 fix-and-reruns of the same problem, and one restart.
- Record each rerun under "Reruns", or write "Reruns: none".

## Hand-back

Commit on `task/M15-cursor-engine` (prefix `M15-cursor-engine:`; end with a `Co-Authored-By` line
naming the model you actually run as). Do not push.

Short result file:
- what changed per module;
- the test counts for both runs;
- deviations from this contract, with reasons;
- reruns;
- open issues, including anything the orchestrator must check on the host with the real key.
