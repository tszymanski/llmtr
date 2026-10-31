# llmtr architecture (M1, v2 macOS in sections 11-22)

Sections 1-10 are the v1 (Linux) design and stay valid. Sections 11-22 are **v2** (macOS, task
M9): they add a platform layer and macOS backends behind the same Protocols; Linux behaviour does
not change.

Status (v1): proposed by the Architect on 2026-10-03, awaiting user approval. Scope and decisions come
from `docs/proposal.md`; this document fixes module boundaries, interfaces, the config schema and
the work split. The typed stubs in `src/llmtr/` are the binding interface; when this document and
a stub disagree, the stub's signature wins and the disagreement is a bug to report.

## 1. Overview

```
GNOME shortcut ─▶ cli.py (M4) ──────────────────────────────────────────────────────────────┐
                    │ model side (M2)                      │ desktop side (M3)               │
                    ├─ config.py      files, schema        ├─ lock.py       single run/cancel│
                    ├─ engine.py      mode → Job → result  ├─ selection.py  capture/deliver  │
                    │   ├─ langdetect.py  PL/EN            │   ├─ clipboard.py wl-*/xclip    │
                    │   ├─ prompts.py     prompts, filter  │   └─ keys.py      ydotool       │
                    │   └─ ollama_client.py HTTP (Transport)└─ notify.py     notify-send      │
                    └─ shared, final in M1: errors.py, fakes.py, config dataclasses           │
```

Rules:

- The model side never imports the desktop side and vice versa. Only `cli.py` imports both.
  (Exception: `keys.py`/`selection.py` import the `KeysConfig` dataclass from `config.py`;
  dataclasses are final in M1, so M3 never edits `config.py`.)
- Every external boundary is a `Protocol` with a fake in `llmtr/fakes.py`:
  `Transport`, `ChatClient`, `Clipboard`, `KeySender`, `Notifier`. Time is injected as
  `sleep`/`monotonic` callables.
- Every user-visible failure is an `llmtr.errors.LlmtrError` with a ready `user_message`. Modules
  raise; only `cli.py` turns errors into notifications.
- Runtime is stdlib only (`tomllib`, `urllib.request`, `subprocess`, `fcntl`, `signal`).

## 2. Modules

Legend: **M1** = written now, final (changes need the orchestrator). **M2/M3/M4** = stub now,
implemented by that worker. Full signatures and docstrings are in the stubs; summary here.

### `errors.py` — M1, final

| Class | Raised when | `user_message` |
| --- | --- | --- |
| `LlmtrError(user_message, detail="")` | base | — |
| `ConfigError(path, problem)` | bad TOML / bad value | `Config error in {path}: {problem}` |
| `OllamaUnavailable(url, detail="")` | cannot connect | `Can't reach Ollama at {url}. Is it running?` |
| `ModelMissing(model)` | HTTP 404 "model … not found" | `Model {m} is not installed. Run: ollama pull {m}` |
| `OllamaTimeout(timeout)` | request > `ollama.timeout` | `Ollama did not answer within {t} s. Try again.` |
| `OllamaError(msg=…, detail="")` | other HTTP error, bad JSON, empty output | `Ollama returned an error.` / `The model returned no text.` |
| `EmptySelection(used_keystrokes=True)` | nothing captured | `No text selected. Select some text first.` / fallback: `Clipboard is empty. Copy the text first (ydotool is not set up).` |
| `TextTooLong(length, limit)` | `len(text) > ollama.max_chars` | `Selection too long ({n} characters, limit {max}).` |
| `ClipboardUnavailable(detail="")` | no wl-clipboard/xclip, or it failed | `No working clipboard tool. Install wl-clipboard.` |
| `KeySendError(detail="")` | ydotool present but failed | `Could not send keystrokes. Is ydotoold running?` |
| `Cancelled()` | SIGTERM from a second press | `Cancelled.` |

### `config.py` — M2 (dataclasses and constants final in M1)

Dataclasses (frozen): `Config(ollama, models, languages, keys, tone, notify)`, `OllamaConfig`,
`ModelsConfig`, `LanguagesConfig`, `KeysConfig`, `KeyOverride`, `ToneConfig`, `TonePreset`,
`NotifyConfig`, `State`. Constants: `DEFAULT_OLLAMA_URL`, `OLLAMA_HOST_ENV`,
`SUPPORTED_LANGUAGES = {"pl": "Polish", "en": "English"}`, `TEAM_TONE`.

```python
def config_path(env: Mapping[str, str] | None = None) -> Path
def state_path(env: Mapping[str, str] | None = None) -> Path
def cache_dir(env: Mapping[str, str] | None = None) -> Path
def normalize_ollama_url(value: str) -> str
def parse_config(data: Mapping[str, Any], env: Mapping[str, str] | None = None,
                 source: Path | str = "config.toml") -> Config          # raises ConfigError
def load_config(path: Path | None = None, env: Mapping[str, str] | None = None) -> Config
def load_state(path: Path | None = None) -> State                     # never raises
def save_state(state: State, path: Path | None = None) -> None        # atomic
def current_tone(config: Config, state: State) -> TonePreset
def next_tone(config: Config, state: State) -> TonePreset
def save_last_result(text: str, directory: Path | None = None) -> Path
```

### `langdetect.py` — M2

```python
Language = Literal["pl", "en"]
def detect_language(text: str) -> Language
def choose_direction(text: str, native: str, other: str) -> tuple[str, str]   # (source, target)
```

### `prompts.py` — M2 (constants final in M1)

```python
class Message(TypedDict): role: Literal["system", "user", "assistant"]; content: str
TRANSLATEGEMMA_TEMPLATE, TRANSLATEGEMMA_SEPARATOR = "\n\n\n", FIX_SYSTEM_PROMPT,
TONE_SYSTEM_PROMPT_TEMPLATE, TEXT_OPEN = "<text>", TEXT_CLOSE = "</text>", PREAMBLE_PATTERNS
def build_translate_messages(text: str, source: str, target: str) -> list[Message]
def build_fix_messages(text: str) -> list[Message]
def build_tone_messages(text: str, preset: TonePreset) -> list[Message]
def strip_preamble(output: str, original: str) -> str
```

### `ollama_client.py` — M2

```python
class HTTPStatusError(Exception): status: int; body: str
class Transport(Protocol):
    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> dict[str, Any]
class ChatClient(Protocol):
    def chat(self, model: str, messages: Sequence[Message], *,
             options: Mapping[str, Any] | None = None, keep_alive: str | None = None) -> str
class UrllibTransport:  # Transport
class OllamaClient:     # ChatClient
    def __init__(self, base_url: str, timeout: float, transport: Transport | None = None) -> None
```

Transport raises only `HTTPStatusError`, `ConnectionError`, `TimeoutError`, `ValueError`.
`OllamaClient.chat` maps them: `ConnectionError` → `OllamaUnavailable`, `TimeoutError` →
`OllamaTimeout`, 404 + "not found" → `ModelMissing`, everything else → `OllamaError`.
Request: `POST {base_url}/api/chat`, `{"model", "messages", "stream": false, "options":
{"temperature", "num_ctx"}, "keep_alive"}`; result `response["message"]["content"]`.

### `engine.py` — M2

```python
class Mode(StrEnum): TRANSLATE = "translate"; FIX = "fix"; TONE = "tone"
@dataclass(frozen=True)
class Job: mode; model; messages: tuple[Message, ...]; original: str;
           source_lang: str | None; target_lang: str | None; tone: TonePreset | None
def plan_job(mode: Mode, text: str, config: Config, *, tone: TonePreset | None = None,
             quality: bool = False, model: str | None = None) -> Job  # EmptySelection, TextTooLong
def progress_text(job: Job) -> tuple[str, str]                         # (summary, body)
def run_job(job: Job, client: ChatClient, config: Config) -> str       # client errors, OllamaError
```

### `clipboard.py` — M3

```python
class Clipboard(Protocol):
    def get_text(self) -> str        # "" when empty / not text
    def set_text(self, text: str) -> None
    def clear(self) -> None
class WlClipboard: ...   # wl-paste --no-newline --type text / wl-copy / wl-copy --clear
class XclipClipboard: ...# xclip -selection clipboard
def make_clipboard(env: Mapping[str, str] | None = None) -> Clipboard   # ClipboardUnavailable
```

Never uses the PRIMARY selection. Text only: non-text clipboard content is not preserved.

### `keys.py` — M3

```python
@dataclass(frozen=True) class KeyPair: copy: str; paste: str
class KeySender(Protocol):
    def available(self) -> bool       # cheap, never raises
    def send(self, combo: str) -> None   # KeySendError, ValueError
def parse_combo(combo: str) -> list[int]          # "ctrl+shift+c" -> [29, 42, 46]
class YdotoolKeySender:  # KeySender; __init__(self, env=None)
def focused_app_id() -> str | None                # Window Calls extension via gdbus; never raises
def resolve_key_pair(keys: KeysConfig, app_id: str | None) -> KeyPair
```

### `notify.py` — M3

```python
Urgency = Literal["low", "normal", "critical"]
class Notifier(Protocol):
    def notify(self, summary: str, body: str = "", *, urgency: Urgency = "normal") -> None
class NotifySendNotifier:  # uses --print-id/--replace-id so one run shows one bubble; never raises
```

### `lock.py` — M3

```python
def default_lock_path(env: Mapping[str, str] | None = None) -> Path   # $XDG_RUNTIME_DIR/llmtr/run.lock
class RunLock:
    def __init__(self, path: Path) -> None
    def acquire(self) -> bool          # flock(LOCK_EX|LOCK_NB), writes PID
    def release(self) -> None
    def holder_pid(self) -> int | None
    # context manager after a successful acquire
def cancel_running(lock: RunLock, *, sig: int = SIGTERM,
                   kill: Callable[[int, int], None] | None = None) -> bool
def install_cancel_handler() -> None   # SIGTERM -> raise Cancelled
```

### `selection.py` — M3

```python
@dataclass(frozen=True)
class Captured: text: str; saved_clipboard: str; used_keystrokes: bool
def capture_selection(clipboard, keys, pair, timing: KeysConfig, *, sleep=time.sleep,
                      monotonic=time.monotonic) -> Captured   # EmptySelection, ClipboardUnavailable, KeySendError
def deliver_result(result, captured, clipboard, keys, pair, timing: KeysConfig, *,
                   sleep=time.sleep) -> bool                  # True = pasted, False = left on clipboard
def restore_clipboard(captured: Captured, clipboard: Clipboard) -> None   # never raises
```

### `cli.py` — M4 (`build_parser` final in M1)

```python
def build_parser() -> argparse.ArgumentParser
def main(argv: Sequence[str] | None = None) -> int
def run_shortcut(mode: Mode, config: Config, notifier: Notifier, *, quality: bool = False,
                 model: str | None = None) -> int     # M4 may add keyword-only injection params
```

Command line:

```
llmtr [--config PATH] translate [--quality] [--model NAME] [--stdin]
llmtr [--config PATH] fix                   [--model NAME] [--stdin]
llmtr [--config PATH] tone [--next]         [--model NAME] [--stdin]
```

`--stdin` reads the text from stdin and prints the result to stdout: no lock, clipboard, keys or
notifications; errors go to stderr. It is the path for manual checks (M2) and evaluation (M5).
Exit codes: 0 ok (including a cancelling second press and `tone --next`), 1 `LlmtrError`, 2 usage.

### `fakes.py` — M1, final (real code)

`FakeTransport(responses)` (+ `chat_response(content)`), `FakeChatClient(reply)`,
`FakeClipboard(text)`, `FakeKeySender(is_available=, on_send=, fail=)`, `FakeNotifier()`,
`FakeClock()`. They record calls (`requests`, `calls`, `history`, `sent`, `shown`, `sleeps`).

### `__init__.py`, `__main__.py` — M1, final

`from llmtr.cli import main`; `python -m llmtr` calls `main()`.

## 3. Call sequences

Common start for every command: `args = build_parser().parse_args(argv)`;
`config = load_config(args.config)` (a `ConfigError` here is notified and exits 1).
`notifier = NotifySendNotifier()`. "Progress" notifications are skipped when
`config.notify.enabled` is false; all other notifications are always shown.

### 3.1 `llmtr translate | fix | tone` (shortcut flow, `run_shortcut`)

```
 1. lock = RunLock(default_lock_path())
 2. if not lock.acquire():                       # second press while a job runs
        cancel_running(lock); return 0           # do NOT start a new job (any mode)
 3. with lock:
 4.   install_cancel_handler()
 5.   clipboard = make_clipboard(); keys = YdotoolKeySender()
 6.   pair = resolve_key_pair(config.keys, focused_app_id())
 7.   captured = capture_selection(clipboard, keys, pair, config.keys)
          keystrokes:  saved = get_text(); clear(); sleep(start_delay); send(pair.copy);
                       poll get_text() until non-empty or copy_timeout
                       → empty: restore saved, raise EmptySelection
          fallback:    text = current clipboard (user copied by hand); saved = ""
 8.   tone = current_tone(config, load_state())            # tone mode only
 9.   job = plan_job(mode, captured.text, config, tone=tone, quality=args.quality,
                     model=args.model)
10.   notifier.notify(*progress_text(job))                 # progress: "Translating PL → EN…"
11.   client = OllamaClient(config.ollama.url, config.ollama.timeout)
12.   result = run_job(job, client, config)
13.   save_last_result(result)                             # ~/.cache/llmtr/last.txt
14.   pasted = deliver_result(result, captured, clipboard, keys, pair, config.keys)
          keystrokes:  set_text(result); send(pair.paste); sleep(paste_delay);
                       restore saved clipboard
          fallback / paste KeySendError: result stays on the clipboard
15.   if not pasted: notifier.notify("Result copied. Press Ctrl+V to paste.")
      return 0
   on LlmtrError e (incl. Cancelled) after step 7:
      restore_clipboard(captured, clipboard)   # no-op in fallback
      notifier.notify(e.user_message, urgency="normal" if Cancelled else "critical")
      return 1  (Cancelled: return 0)
   lock is released by the context manager / process exit.
```

### 3.2 `llmtr tone --next`

No lock, no clipboard, no model. `state = load_state()`; `preset = next_tone(config, state)`;
`save_state(State(tone=preset.name))`; notify `"Tone: {name}"` with the instruction as body (with
a single preset: `"Tone: team (only preset)"`). Return 0.

### 3.3 `--stdin` (any text mode)

`text = sys.stdin.read()` → `plan_job` → `run_job` → print result (no extra newline beyond the
one the post-filter restored from the input). `LlmtrError` → `user_message` to stderr, exit 1.
`tone --next --stdin` is a usage error (exit 2).

### 3.4 Cancel on second press

```
process A (running)                      process B (second press)
 holds flock on run.lock (PID in file)    acquire() → False
 blocked in HTTP read                     cancel_running(lock) → os.kill(A, SIGTERM); exit 0
 SIGTERM handler raises Cancelled ◀───────┘
 → restore clipboard, notify "Cancelled.", exit 0; kernel drops the flock
```

Closing the HTTP socket makes Ollama stop generating. A crash never leaves a stale lock because
`flock` locks die with the process.

## 4. Files and schema

### 4.1 `~/.config/llmtr/config.toml` (`$XDG_CONFIG_HOME/llmtr/config.toml`)

All keys optional; a missing file means all defaults; unknown keys are ignored.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `ollama.url` | string | `"http://localhost:11434"` | `OLLAMA_HOST` env (non-empty) overrides it; normalized: scheme and port 11434 added if missing, `0.0.0.0`/`[::]` → `127.0.0.1`; only `http`/`https` are accepted |
| `ollama.timeout` | float, s | `120.0` | per request; > 0 |
| `ollama.keep_alive` | string | `"30m"` | sent with every request |
| `ollama.temperature` | float | `0.0` | |
| `ollama.num_ctx` | int | `4096` | |
| `ollama.max_chars` | int | `8000` | longer selections → `TextTooLong`; > 0 |
| `models.translate` | string | `"translategemma:12b"` | |
| `models.translate_quality` | string | `"translategemma:27b"` | `translate --quality` |
| `models.fix` | string | `"gemma3"` | confirmed by M5 + M5b |
| `models.tone` | string | `"gemma3:12b"` | M5b, user decision 2026-10-04 |
| `languages.native` | `"pl"`\|`"en"` | `"pl"` | text detected as this → `other` |
| `languages.other` | `"pl"`\|`"en"` | `"en"` | everything else → `native`; must differ |
| `keys.copy` | combo | `"ctrl+c"` | sent, never a trigger |
| `keys.paste` | combo | `"ctrl+v"` | sent, never a trigger |
| `keys.start_delay` | float, s | `0.25` | wait before copy so Super+Alt are released |
| `keys.copy_timeout` | float, s | `1.0` | wait for copied text |
| `keys.paste_delay` | float, s | `0.3` | wait before restoring the old clipboard |
| `[[keys.override]]` `app` | list of strings | — | app ids / WM classes, case-insensitive |
| `[[keys.override]]` `copy`, `paste` | combo | — | both required |
| `[[tone.preset]]` `name`, `instruction` | strings | built-in `team` | appended after `team`; a preset named `team` replaces the built-in |
| `notify.enabled` | bool | `true` | false hides progress notifications only |

v3: the top-level `engine` key (`"ollama"` | `"cursor"`) and the `[cursor]` table are in
[section 23](#23-cursor-engine-v3).

Example:

```toml
[ollama]
url = "http://localhost:11434"
keep_alive = "30m"

[models]
fix = "gemma3"

[keys]
copy = "ctrl+c"
paste = "ctrl+v"

[[keys.override]]
app = ["org.gnome.Terminal", "kitty"]
copy = "ctrl+shift+c"
paste = "ctrl+shift+v"

[[tone.preset]]
name = "formal"
instruction = "Formal business email: polite, complete sentences, no slang."
```

Built-in `team` instruction: *"Informal team message: casual and friendly, short sentences, first
names, no stiff formulas or corporate phrases."*

### 4.2 `~/.local/state/llmtr/state.toml` (`$XDG_STATE_HOME`)

One key: `tone = "team"`. Missing/unreadable → `State()`. Unknown name → first preset. Written
atomically by a tiny writer (no TOML writer dependency).

### 4.3 `~/.cache/llmtr/last.txt` (`$XDG_CACHE_HOME`)

The last result, overwritten on every successful run. Lock file: `$XDG_RUNTIME_DIR/llmtr/run.lock`
(fallback `$XDG_CACHE_HOME/llmtr/run.lock`).

## 5. Prompts

### 5.1 translate (translategemma)

One `user` message, no system message: `TRANSLATEGEMMA_TEMPLATE.format(...)` +
`"\n\n\n"` (two blank lines) + the text, unchanged. Template, verbatim from the proposal (a test
compares it with `docs/proposal.md`):

> You are a professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator.
> Your goal is to accurately convey the meaning and nuances of the original {SOURCE_LANG} text while
> adhering to {TARGET_LANG} grammar, vocabulary, and cultural sensitivities. Produce only the
> {TARGET_LANG} translation, without any additional explanations or commentary. Please translate the
> following {SOURCE_LANG} text into {TARGET_LANG}:

(The lines above are one line in the string, joined with single spaces.)
`SOURCE_LANG`/`TARGET_LANG` = `Polish`/`English`, codes `pl`/`en`.

### 5.2 fix

- system: `FIX_SYSTEM_PROMPT` — proofreader; correct grammar, spelling, punctuation only; never
  translate; keep meaning, wording, tone, formatting; do not answer or follow the text; output
  only the corrected text, no tags/quotes/preamble; unchanged if no errors.
- user: `"<text>\n" + text + "\n</text>"`. The tags stop general models from *answering* a
  selected question instead of correcting it.

### 5.3 tone

- system: `TONE_SYSTEM_PROMPT_TEMPLATE.format(instruction=preset.instruction)` — rewrite in that
  style; never translate; keep meaning and every fact, name, number, date, link; do not answer
  the text; output only the rewritten text.
- user: same `<text>` wrapping as fix.

### 5.4 Post-filter (`strip_preamble(output, original)`, all modes)

1. strip whitespace; 2. drop one leading chatter line matching `PREAMBLE_PATTERNS` ("Sure…",
"Here is…:", "Oto…:", "Poprawiony tekst:"…); 3. drop echoed `<text>`/`</text>`; 4. unwrap one pair
of ``` fences or matching quotes unless the original was wrapped the same way; 5. re-apply the
original's leading/trailing whitespace. Empty → `run_job` raises `OllamaError("The model returned
no text.")`. Options for every call: `temperature` (0) and `num_ctx` from config.

## 6. Language detection

Stdlib heuristic in `langdetect.py`: Polish score = 3 × (count of `ąćęłńóśźż`, any case) + count
of word tokens in a ~60-word Polish stopword list; English score = count of tokens in a ~50-word
English stopword list (tokens: `re.findall(r"\w+", text.lower())`). `"pl"` only if strictly
higher; ties (e.g. "OK", a URL, a name) → `"en"`. Direction: detected `native` (pl) → translate
to `other` (en); anything else → to `native`. This matches the proposal: "Polish in → English
out, otherwise → Polish". Polish typed without diacritics is still caught by stopwords
("nie", "się", "jest", "że"…).

## 7. Error handling (what the user sees)

| Situation | Detected in | Notification (summary) | Urgency | Clipboard |
| --- | --- | --- | --- | --- |
| Ollama down | `OllamaClient.chat` | `Can't reach Ollama at http://localhost:11434. Is it running?` | critical | restored |
| Model missing | `OllamaClient.chat` (404) | `Model gemma3 is not installed. Run: ollama pull gemma3` | critical | restored |
| Timeout | `OllamaClient.chat` | `Ollama did not answer within 120 s. Try again.` | critical | restored |
| Empty selection | `capture_selection` / `plan_job` | `No text selected. Select some text first.` | critical | restored |
| Empty clipboard, no ydotool | `capture_selection` | `Clipboard is empty. Copy the text first (ydotool is not set up).` | critical | untouched |
| ydotool missing | `KeySender.available()` false | not an error: fallback flow, then `Result copied. Press Ctrl+V to paste.` | normal | holds result |
| ydotool fails on paste | `deliver_result` | `Result copied. Press Ctrl+V to paste.` | normal | holds result |
| ydotool fails on copy | `capture_selection` | `Could not send keystrokes. Is ydotoold running?` | critical | restored |
| Text too long | `plan_job` | `Selection too long (9000 characters, limit 8000).` | critical | restored |
| Model output empty | `run_job` | `The model returned no text.` | critical | restored |
| No clipboard tool | `make_clipboard` | `No working clipboard tool. Install wl-clipboard.` | critical | — |
| Bad config | `load_config` | `Config error in …/config.toml: …` (incl. an Ollama URL that is not `http`/`https`) | critical | — |
| Second press | `RunLock.acquire` false | (first process) `Cancelled.` | normal | restored |

`detail` (exception text) goes to stderr only, which GNOME sends to the journal.

v3: the Cursor engine's errors are in the [section 23 error table](#235-errors).

## 8. Testing strategy

- No unit test touches Ollama, a clipboard, `ydotool`, `notify-send`, `gdbus` or real signals to
  other processes. Real-model tests are marked `@pytest.mark.ollama`.
- **M2** tests `parse_config`/`normalize_ollama_url` with dicts and fake `env` mappings; file
  functions with `tmp_path`; `detect_language`/`choose_direction` with PL/EN samples (with and
  without diacritics); prompt builders by exact string comparison (template + `"\n\n\n"`);
  `strip_preamble` table-driven; `OllamaClient` with `FakeTransport` (success, `ConnectionError`,
  `TimeoutError`, `HTTPStatusError(404, '{"error":"model \"x\" not found"}')`, 500, bad JSON);
  `UrllibTransport` against a local `http.server` thread on 127.0.0.1 (stdlib, no Ollama);
  `plan_job`/`run_job` with `FakeChatClient`.
- **M3** tests `capture_selection`/`deliver_result`/`restore_clipboard` with `FakeClipboard`,
  `FakeKeySender(on_send=…)` and `FakeClock`; `parse_combo`/`resolve_key_pair` as pure
  functions; `WlClipboard`/`XclipClipboard`/`YdotoolKeySender`/`NotifySendNotifier`/
  `focused_app_id` by monkeypatching `subprocess.run`/`shutil.which` and asserting argv;
  `RunLock` with two locks on one `tmp_path` file (same process, separate file descriptors);
  `cancel_running` with an injected `kill`; `install_cancel_handler` with `os.kill(os.getpid(),
  SIGTERM)` inside `pytest.raises(Cancelled)` (restore the old handler afterwards).
- **M4** tests `main()` end to end with all fakes injected through `run_shortcut`'s keyword-only
  parameters, and `--stdin` with `FakeChatClient`.
- Real desktop checks (gedit, Firefox) and real-model checks happen on the host (M3/M4/M5).

## 9. Work split

| Worker | May change | Must not change |
| --- | --- | --- |
| **M2 core** | `src/llmtr/config.py` (function bodies only), `src/llmtr/langdetect.py`, `src/llmtr/prompts.py` (function bodies only), `src/llmtr/ollama_client.py`, `src/llmtr/engine.py`; tests `tests/test_config.py`, `tests/test_langdetect.py`, `tests/test_prompts.py`, `tests/test_ollama_client.py`, `tests/test_engine.py` | dataclasses/constants in `config.py`, `TRANSLATEGEMMA_TEMPLATE` and the other prompt constants (prompt wording changes go through M5/orchestrator), anything else |
| **M3 desktop** | `src/llmtr/clipboard.py`, `src/llmtr/keys.py`, `src/llmtr/notify.py`, `src/llmtr/lock.py`, `src/llmtr/selection.py`; tests `tests/test_clipboard.py`, `tests/test_keys.py`, `tests/test_notify.py`, `tests/test_lock.py`, `tests/test_selection.py` | `config.py`, anything else |
| **M4 integration** | `src/llmtr/cli.py`, `install.sh`, `README.md`, `tests/test_cli.py` | M2/M3 modules (report bugs back) |
| **M1 / orchestrator only** | `src/llmtr/errors.py`, `src/llmtr/fakes.py`, `src/llmtr/__init__.py`, `src/llmtr/__main__.py`, `tests/test_interfaces.py`, `docs/architecture.md` | — |

Both M2 and M3 must keep `tests/test_interfaces.py` green. Neither needs `uv add`.

## 10. Open points for later milestones

- Whether GNOME delivers the copy keystroke while the user still holds Super+Alt: `start_delay`
  is the v1 answer; M3 checks on the host and may add explicit modifier key-up events in
  `YdotoolKeySender.send`.
- `focused_app_id` depends on the Window Calls extension; without it only the default key pair is
  used (as the proposal says).
- Fix/tone default model and prompt wording are confirmed in M5.

---

# v2 — macOS (M9, 2026-10-25)

Source of the decisions: `docs/proposal.md` "macOS support (v2)" and the evidence in
`docs/tasks/M8-spike.result.md`. This part turns them into interfaces; the typed stubs in
`src/llmtr/` are binding (see the status paragraph at the top).

## 11. Overview (v2)

```
Hammerspoon (llmtr.lua) ──hs.task, absolute path──▶ cli.py ──▶ backends.py (platform choice)
        ▲                                                         ├─ platforms.py      detect, key defaults
        └── hammerspoon://llmtr?… (open -g) ◀── macos_notify.py   ├─ macos_clipboard.py pbcopy/pbpaste
                                                                  ├─ macos_keys.py      osascript keystrokes
                                                                  ├─ macos_probes.py    focused app, Secure Input
                                                                  └─ macos_exec.py      paths, env, Runner
```

Unchanged and shared: `engine`, `prompts`, `ollama_client`, `langdetect`, `selection`, `lock`,
`log`, `fakes` (extended additively), `errors` (two new classes). Rules from section 1 hold:
only `cli.py` imports both sides; `backends.py` and `macos_*.py` are desktop side and import no
model-side module (they import `config.KeysConfig` and `errors`, as `keys.py` does).

## 12. Platform selection

`platforms.py` (pure):

```python
Platform = Literal["linux", "macos"]
def detect_platform(sys_platform: str | None = None) -> Platform   # "darwin" -> "macos", else "linux"
@dataclass(frozen=True) class KeyDefaults: copy; paste; start_delay
LINUX_KEY_DEFAULTS = KeyDefaults("ctrl+c", "ctrl+v", 0.25)    # == KeysConfig defaults (test)
MACOS_KEY_DEFAULTS = KeyDefaults("cmd+c", "cmd+v", 0.0)
def key_defaults(platform: Platform) -> KeyDefaults
```

`backends.py` is the **one place** that maps a platform to backends. `cli.py` stops building
`NotifySendNotifier` / `YdotoolKeySender` directly:

```python
@dataclass(frozen=True)
class Desktop:
    platform: Platform
    make_clipboard: Callable[[], Clipboard]       # lazy: ClipboardUnavailable stays inside run_shortcut
    keys: KeySender
    focused_app_id: Callable[[], str | None]
    paste_hint: str                                # LINUX_PASTE_HINT / MACOS_PASTE_HINT
    empty_selection_hint: Callable[[], str | None] # macOS: Secure Input app name; Linux: lambda: None
def make_notifier(platform=None, backend="auto", env=None) -> Notifier
def make_desktop(platform=None, env=None, *, keys_config: KeysConfig | None = None) -> Desktop
```

| | Linux | macOS |
| --- | --- | --- |
| `make_notifier` | `NotifySendNotifier()` | `HammerspoonNotifier(env)` for `"auto"`/`"hammerspoon"`, `OsascriptNotifier()` for `"osascript"` |
| `Desktop.make_clipboard` | `lambda: make_clipboard(env)` | `lambda: PbClipboard(env)` |
| `Desktop.keys` | `YdotoolKeySender(env)` | `OsascriptKeySender()` |
| `Desktop.focused_app_id` | `keys.focused_app_id` | `focused_bundle_id` if `keys_config.override` is non-empty, else `lambda: None` (saves ~0.25 s per run; the id is only needed for overrides) |
| `Desktop.paste_hint` | `Result copied. Press Ctrl+V to paste.` | `Result copied. Press ⌘V to paste.` |
| `Desktop.empty_selection_hint` | `lambda: None` | `secure_input_app` |

`platform=None` means `detect_platform()`. Tests pass the platform (and `env`) explicitly, so the
host OS never matters. `cli.main` (M10):

```
platform = detect_platform()
notifier = make_notifier(platform)                     # before the config exists (config errors)
config   = load_config(path, platform=platform)        # platform-dependent key defaults (13)
notifier = make_notifier(platform, config.notify.backend)
desktop  = make_desktop(platform, keys_config=config.keys)   # shortcut flow only
```

`run_shortcut` gets one more keyword-only parameter `desktop: Desktop | None = None` (default:
`make_desktop(keys_config=config.keys)`); the existing `clipboard=`, `keys=` overrides stay and win
over the bundle, so existing tests keep working. It uses `desktop.focused_app_id()`,
`desktop.paste_hint` and `desktop.empty_selection_hint` (section 18).

## 13. Platform-dependent defaults

`KeysConfig` keeps its Linux defaults (`ctrl+c`, `ctrl+v`, `0.25`), so existing configs, tests and
`Config()` do not change. Instead `parse_config` and `load_config` get a keyword-only
`platform: Platform = "linux"`: a key **missing** from `[keys]` takes `key_defaults(platform)`;
a key written by the user always wins (so `start_delay = 0.25` is respected on macOS). Only
`cli.main` passes `detect_platform()`; everything else (all existing tests, `--stdin`) keeps
"linux" defaults, which is also what keeps the suite green on the macOS CI runner.
`[[keys.override]]` combos on macOS use the same combo syntax (`cmd+shift+c`).

New key: `notify.backend` = `"auto"` (default) | `"hammerspoon"` | `"osascript"`, field
`NotifyConfig.backend`. `"auto"` means Hammerspoon on macOS (Hammerspoon is required anyway: it
starts `llmtr`); `"osascript"` is the user's switch if `hs.notify` is not allowed (Settings ->
Notifications). Ignored on Linux. Any other value is a `ConfigError`. There is no auto-detection
of the Notifications setting (macOS gives no API for it) — a user whose Hammerspoon bubbles do
not show sets `backend = "osascript"`.

## 14. macOS backends

All take an injectable `run: Runner` (same call shape as `subprocess.run`, bytes mode); tests pass
a fake, nothing real starts. Every tool is called by **absolute path** (constants in
`macos_exec.py`) because `hs.task` children have `PATH=/usr/bin:/bin:/usr/sbin:/sbin`.

### 14.1 `macos_exec.py`

`PBCOPY`, `PBPASTE`, `OSASCRIPT`, `OPEN`, `IOREG`, `PS`, `SUBPROCESS_TIMEOUT`, `Runner`,
`child_env(env=None) -> dict[str, str]`: copy of `env` (default `os.environ`) with
`LC_CTYPE=UTF-8` **always** set (also when `env` has no locale; M8 bug) and `LC_ALL` removed
(it would override `LC_CTYPE`).

### 14.2 `macos_clipboard.py` — `PbClipboard(env=None, *, run=subprocess.run)`

`Clipboard` implementation. `get_text`: `/usr/bin/pbpaste`, exit 0, empty output (empty or non-text
clipboard) -> `""`. `set_text`: UTF-8 text on `/usr/bin/pbcopy`'s stdin (returns at once, leaves
no process). `clear`: `set_text("")`. All calls use `child_env(env)`. Missing binary, non-zero
exit, timeout -> `ClipboardUnavailable("pbcopy failed: …")` (user message "No working clipboard
tool. Install wl-clipboard." is wrong on macOS; M10 adds an optional `tool` argument to the
message, see 21).

### 14.3 `macos_keys.py` — `OsascriptKeySender(*, run=subprocess.run)`

`KeySender` implementation.

- `parse_mac_combo("cmd+c") -> MacCombo("c", ("command down",))`; modifiers: `cmd|command|super`
  -> `command down`, `ctrl|control` -> `control down`, `alt|opt|option` -> `option down`,
  `shift` -> `shift down`. Key: one letter/digit (`keystroke`), or `enter`/`tab`/`space`
  (`key code 36/48/49`). Anything else, or not exactly one key -> `ValueError`.
- `build_applescript("cmd+c")` -> `tell application "System Events" to keystroke "c" using {command down}`;
  named keys: `… to key code 36 using {…}`; no modifiers: no `using` clause. The script is built
  from a validated combo only (no user text reaches it).
- `send(combo)`: `ValueError` first (nothing runs); then `/usr/bin/osascript -e <script>` with
  `child_env`, timeout `SEND_TIMEOUT` = 30 s (the first call blocks while the Automation dialog
  is open: 43 s in M8).
- `available()`: `/usr/bin/osascript` exists and is executable. Cheap, never raises. It does
  **not** probe permissions: a probe would trigger the Automation dialog and cost ~0.2 s, and
  Accessibility cannot be read without trying. A missing permission therefore shows up in `send`.
- Error mapping (`classify_osascript_error(stderr)`), all raised as `MacKeySendError(reason,
  detail=stderr)` (a `KeySendError`):

| osascript result | reason | user message |
| --- | --- | --- |
| stderr has `(1002)` / "not allowed to send keystrokes" | `accessibility` | `Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security > Device Control and Data Access (Accessibility).` |
| stderr has `(-1743)` / "Not authorized to send Apple events" | `automation` | `Keystrokes blocked. In System Settings > Privacy & Security > Automation, allow Hammerspoon to control System Events.` |
| `TimeoutExpired` (dialog unanswered) | `timeout` | `Keystrokes timed out. Answer the Hammerspoon permission prompt, then retry.` |
| other non-zero exit, `OSError` | `failed` | `Could not send keystrokes. See: llmtr log` |

("Accessibility" is titled "Device Control and Data Access" on macOS 27; the message uses the name
that older versions and the Privacy list heading also use. The README shows both.)

### 14.4 `macos_notify.py`

Both classes are `Notifier`s and **never raise** (errors -> stderr, like `NotifySendNotifier`).

- `HammerspoonNotifier(env=None, *, run_id=None, run=subprocess.run)`: each `notify` runs
  `/usr/bin/open -g <url>` with `url = build_notify_url(run_id, summary, body, urgency)` =
  `hammerspoon://llmtr?action=notify&id=<run_id>&summary=…&body=…&urgency=…` (values
  percent-encoded, body cut to 500 characters). `-g` keeps the focus where it is (the paste goes
  to the app the user is in). **One bubble per run:** the id is constant for the instance
  (`$LLMTR_RUN_ID` set by `llmtr.lua`, else the PID) and Lua replaces/withdraws the previous
  bubble of the same id, so "Translating…" is replaced by the result or error. Latency of the
  channel is unmeasured (M8); `open` is given a 2 s timeout.
- `OsascriptNotifier(*, run=...)`: `/usr/bin/osascript` with `on run argv … display notification
  (item 2 of argv) with title (item 1 of argv) … end run`, summary and body passed as argv items
  (no escaping, no injection). Shows as "Script Editor", cannot replace a bubble; urgency is
  ignored.
- **Choice:** only through config `notify.backend` (13). No runtime detection and no automatic
  second attempt: a failed `open` is logged to stderr, the run continues.

### 14.5 `macos_probes.py`

- `focused_bundle_id(*, run=...) -> str | None`: `/usr/bin/osascript` asking System Events for the
  frontmost process' bundle identifier (0.2-0.3 s). For logging and `[[keys.override]]` only
  (M8: no override is needed on macOS). Returns `None` on any failure; never raises.
- `parse_secure_input_pid(ioreg_output) -> int | None` (pure) and
  `secure_input_app(*, run=...) -> str | None`: `/usr/sbin/ioreg -l -w 0`, find
  `"kCGSSessionSecureInputPID"=<n>`, then `/bin/ps -p <n> -o comm=`, basename ("Google Chrome").
  `None` if no PID or on failure; never raises. **Called only after "nothing copied"**
  (section 18), never on the happy path (0.36 s).

### 14.6 Errors (`errors.py`, two additive classes)

`MacKeySendError(reason, detail="")` (subclass of `KeySendError`, messages above) and
`SecureInputActive(app)` (subclass of `EmptySelection`, `used_keystrokes=True`): `Nothing copied:
secure input is active in {app}.`

## 15. Lock path on macOS

`default_lock_path` already works unchanged. macOS sets no `$XDG_RUNTIME_DIR`, so the existing
fallback applies: `$XDG_CACHE_HOME/llmtr/run.lock`, else `~/.cache/llmtr/run.lock` (`HOME` is set
for `hs.task` children, M8). `fcntl.flock` and `os.kill(pid, SIGTERM)` behave the same on macOS,
so cancel on the second press works. M10 only adds a test (a `tmp_path` HOME, no
`XDG_RUNTIME_DIR` -> `…/.cache/llmtr/run.lock`) and does not edit `lock.py`.

## 16. Hammerspoon side — `llmtr.lua`

Lives in the repo as the template **`macos/llmtr.lua.in`**; the installer copies it to
`~/.hammerspoon/llmtr.lua` with `@LLMTR_BIN@` replaced by the absolute path of the installed
`llmtr` (`uv tool` puts it at `~/.local/bin/llmtr`; resolved at install time). No logic beyond
launching `llmtr` and showing notifications.

```lua
local LLMTR = "@LLMTR_BIN@"                       -- absolute: hs.task children get a minimal PATH
local bindings = {                                -- mods, key, args
  { {"ctrl","alt"},          "t", {"translate"} },
  { {"ctrl","alt"},          "g", {"fix"} },
  { {"ctrl","alt"},          "r", {"tone"} },
  { {"shift","ctrl","alt"},  "r", {"tone","--next"} },
  { {"shift","ctrl","alt"},  "t", {"tone","--show"} },
}
-- for each: hs.hotkey.bind(mods, key, nil, function() run(args) end)   -- fires on key RELEASE
```

- **Release binding** (`pressedfn = nil`, `releasedfn = fn`; M8: a press binding fails while the
  letter key is still down). A second press starts a second `llmtr`, which cancels the first.
- **`run(args)`:** `hs.task.new(LLMTR, onExit, args)` with environment `LLMTR_RUN_ID=<counter>`
  and `LC_CTYPE=UTF-8` (belt and braces; the Python backends do not rely on it), started
  immediately. `onExit` schedules the withdrawal of this run's bubble (`hs.timer.doAfter`, 8 s;
  15 s after exit code 1), so the last message disappears by itself while "Translating…" stays as
  long as the job runs.
- **Notification handler:** `hs.urlevent.bind("llmtr", fn)` receives `params` (`action`, `id`,
  `summary`, `body`, `urgency`). `action=notify`: withdraw the bubble stored for `id`, create
  `hs.notify.new({title=summary, informativeText=body, withdrawAfter=0})`, `:send()`, store it
  under `id`. `action=withdraw`: withdraw `id`. Unknown actions are ignored.
- `llmtr`'s stdout/stderr are not shown (the log file is the diagnosis path: `llmtr log`).
- The installer adds one line `require("llmtr")` to `~/.hammerspoon/init.lua` (17). The user's own
  Hammerspoon config is never rewritten.

## 17. Installer split

`install.sh` stays the single entry point and keeps all flags (`--dry-run`, `--uninstall`).
Its first action (before the Linux code) is a dispatch: `case "${LLMTR_UNAME:-$(uname -s)}" in
Darwin) exec "$SCRIPT_DIR/scripts/install-macos.sh" "$@" ;; Linux) ;; *) error ;; esac` — the Linux
part below it is **unchanged**. (`LLMTR_UNAME` exists so tests can force the branch; the existing
`install.sh` tests restrict `PATH`, so M11 must make sure `uname` stays reachable there.)

`scripts/install-macos.sh` (macOS only, user-level, no `sudo`), safe to re-run:

1. Preconditions: `uv` present (else print `brew install uv`), `Hammerspoon.app` present in
   `/Applications` or `~/Applications` (else print `brew install --cask hammerspoon`).
2. `uv tool install --reinstall .` (as on Linux); resolve the absolute path of `llmtr`.
3. Write `~/.hammerspoon/llmtr.lua` from `macos/llmtr.lua.in` (replace `@LLMTR_BIN@`); create
   `~/.hammerspoon/` if needed.
4. Idempotently ensure `require("llmtr")` in `~/.hammerspoon/init.lua` (append if the line is
   absent; create the file if there is none; keep everything else).
5. Start Hammerspoon (`open -a Hammerspoon`). If it was already running, tell the user to use
   *Reload Config* in its menu (the script cannot do it without the `hs` CLI).
6. Open the three Settings panes from the proposal (`open "x-apple.systempreferences:…"`):
   Privacy & Security -> Accessibility, -> Automation, and Notifications, and print the steps
   (Accessibility: Hammerspoon on; Automation: Hammerspoon -> System Events on, the dialog appears
   at the first ⌘C; Notifications: Allow, then restart Hammerspoon). It cannot grant anything.
7. `--uninstall`: remove `~/.hammerspoon/llmtr.lua`, remove the `require("llmtr")` line from
   `init.lua` (the file is kept even if empty), `uv tool uninstall llmtr`; keep config, state and
   Hammerspoon itself.

Karabiner (Caps Lock -> ⌃⌥) is **not** installed by the script; the README documents it.

## 18. Call sequence — `llmtr translate` on macOS

Differences to 3.1 are marked `*`.

```
 0*. Hammerspoon: ⌃⌥T released -> hs.task(LLMTR, {"translate"}, env LLMTR_RUN_ID=n)
 1.  main: platform = detect_platform(); notifier = make_notifier(platform);
     config = load_config(path, platform="macos")        # cmd+c / cmd+v / start_delay 0
     notifier = make_notifier(platform, config.notify.backend)
     desktop = make_desktop("macos", keys_config=config.keys)
 2.  lock = RunLock(default_lock_path())  -> ~/.cache/llmtr/run.lock *;  second press: cancel, exit 0
 3.  with lock: install_cancel_handler()
 4.  cb = desktop.make_clipboard()  # PbClipboard; pair = resolve_key_pair(config.keys, desktop.focused_app_id())
 5.  captured = capture_selection(cb, desktop.keys, pair, config.keys)
        desktop.keys.available() true (osascript exists) -> saved = get_text(); clear();
        sleep(0); send("cmd+c") ; poll until text or copy_timeout
        a) text arrived -> continue
        b) send raises MacKeySendError(accessibility|automation|timeout)  -> path P below
        c) nothing arrived -> EmptySelection(True) -> path S below
 6.  plan_job; notifier.notify("Translating PL → EN…")   # hammerspoon://llmtr?action=notify&id=n…
 7.  run_job; save_last_result
 8.  deliver_result: set_text(result); send("cmd+v"); sleep(paste_delay); restore saved clipboard
        send raises (permission revoked in between) -> result stays on the clipboard,
        notifier.notify(desktop.paste_hint)    # "Result copied. Press ⌘V to paste."
 9.  return 0; Lua schedules the bubble withdrawal.

 P (permission, step 5b): restore_clipboard; notifier.notify(exc.user_message, "critical") with
    the Hammerspoon-specific text (14.3); detail (osascript stderr) to the log; exit 1.
 S (nothing copied, step 5c): restore_clipboard(captured, cb)   # first, the probe takes ~0.4 s
    app = desktop.empty_selection_hint()                          # secure_input_app(), only now
    exc = SecureInputActive(app) if app else the EmptySelection
    notify(exc.user_message, "critical"); exit 1.
 Clipboard-only fallback: if `keys.available()` is false (no /usr/bin/osascript — never on a
    stock Mac) the existing fallback of 3.1 runs with `desktop.paste_hint`.
```

Why a copy-time permission failure is an error and **not** a silent switch to clipboard-only
(a deviation from the proposal's wording, see the result file): without Accessibility the selection
cannot be captured, so the fallback would process whatever happens to be on the clipboard — a
surprise. The user gets the exact fix instead. Clipboard-only still applies to a failed paste
(step 8) and to the unavailable case.

## 19. Error table (v2 additions to section 7)

| Situation | Detected in | Notification (summary) | Urgency | Clipboard |
| --- | --- | --- | --- | --- |
| No Accessibility (osascript 1002) | `OsascriptKeySender.send` (copy) | `Keystrokes blocked. Turn on Hammerspoon in System Settings > Privacy & Security > Device Control and Data Access (Accessibility).` | critical | restored |
| Automation denied (−1743) | `OsascriptKeySender.send` (copy) | `Keystrokes blocked. In System Settings > Privacy & Security > Automation, allow Hammerspoon to control System Events.` | critical | restored |
| Automation dialog unanswered | `OsascriptKeySender.send` (timeout) | `Keystrokes timed out. Answer the Hammerspoon permission prompt, then retry.` | critical | restored |
| osascript failed otherwise | `OsascriptKeySender.send` | `Could not send keystrokes. See: llmtr log` | critical | restored |
| Nothing copied, Secure Input on | `empty_selection_hint` | `Nothing copied: secure input is active in Google Chrome.` | critical | restored |
| Nothing copied, no Secure Input | `capture_selection` | `No text selected. Select some text first.` | critical | restored |
| Paste fails | `deliver_result` | `Result copied. Press ⌘V to paste.` | normal | holds result |
| pbcopy/pbpaste fail | `PbClipboard` | `No working clipboard tool.` (M10 wording, 21) | critical | — |
| Bad `notify.backend` | `parse_config` | `Config error in …/config.toml: 'notify.backend' must be one of auto, hammerspoon, osascript` | critical | — |
| Second press | `RunLock.acquire` false | `Cancelled.` | normal | restored |

Ollama, model, timeout, length and config errors are the same as in section 7.

## 20. Testing strategy (v2)

- Nothing calls real `osascript`, `pbcopy`, `pbpaste`, `open`, `ioreg` or `ps`. Backends take
  `run=` and tests pass a recording fake `Runner` (new `fakes.FakeRunner(responses)`: queued
  `CompletedProcess` results or exceptions, records `argv`, `env`, `input`). The suite runs on
  Linux and on the CI `macos-latest` job without a difference.
- **Forcing the platform:** pure functions take it as an argument (`detect_platform("darwin")`,
  `make_desktop("macos", env={…})`, `make_notifier("macos", "osascript")`,
  `parse_config(data, platform="macos")`). No test patches `sys.platform`; the only test that reads
  the real one asserts `detect_platform()` equals `detect_platform(sys.platform)`.
- **Locale (required):** `PbClipboard` tests assert that the `env` given to the fake runner has
  `LC_CTYPE == "UTF-8"` for `get_text`, `set_text` and `clear` when the constructor `env` is `{}`,
  when it has `LC_ALL=pl_PL.ISO8859-2`, and that `LC_ALL` is gone; and that the caller's mapping is
  not mutated. Plus `child_env` directly.
- Absolute paths: every argv[0] in the fake runner is one of the constants in `macos_exec.py`.
- Keys: table-driven `parse_mac_combo`/`build_applescript` (`cmd+c`, `cmd+shift+v`, `ctrl+alt+t`,
  `enter`, errors); `classify_osascript_error` with the real M8 stderr strings; `send` with fakes
  for 1002, −1743, timeout, `OSError`, success; `available()` with a patched `os.access`.
- Notify: `build_notify_url` exact strings (Polish diacritics, `&`, `=`, newline, 500-char cut);
  one `run_id` per instance; `LLMTR_RUN_ID` honoured; `open` failure and timeout never raise;
  osascript fallback passes text as argv.
- Probes: `parse_secure_input_pid` on a captured `ioreg` excerpt (fixture string in the test),
  `secure_input_app` with fakes (found, none, `ps` fails), `focused_bundle_id` (ok, empty, fail).
- Config: `key_defaults` per platform; `parse_config(…, platform="macos")` gives `cmd+c`/`cmd+v`/
  `0.0`; user values win; default call unchanged; `notify.backend` valid/invalid.
- CLI: `run_shortcut` with a hand-built `Desktop` of fakes: Secure Input message after an empty
  capture (and no `secure_input_app` call on success), `paste_hint` used, `MacKeySendError`
  notified with its message.
- Installer/Lua (M11): `tests/test_install_macos.py` runs `scripts/install-macos.sh` with fake
  `uv`, `open`, `uname` in a temp `PATH` and a temp `HOME` (idempotent `require`, created/existing
  `init.lua`, `--dry-run`, `--uninstall`); the Lua template is checked as text (five bindings,
  `@LLMTR_BIN@` placeholder, release binding form).
- Real checks (M12) happen on the test Mac.

## 21. Work split (v2)

No file is in both lists. Neither worker edits a file of the other, `docs/architecture.md`, or
`docs/proposal.md`. Both keep `tests/test_interfaces.py` green. Neither needs `uv add`.

**M10 — macOS desktop backends** (sandbox, Linux):

- Implement (replace `NotImplementedError`): `src/llmtr/platforms.py`, `macos_exec.py`,
  `macos_clipboard.py`, `macos_keys.py`, `macos_notify.py`, `macos_probes.py`, `backends.py`.
- Edit: `src/llmtr/config.py` (`parse_config`/`load_config` `platform=` argument, `notify.backend`
  parsing and validation; dataclass defaults unchanged), `src/llmtr/cli.py` (use `backends`,
  `Desktop`, `desktop=` parameter, paste hint, Secure Input message), `src/llmtr/errors.py`
  (only: `ClipboardUnavailable` and `EmptySelection(False)` messages get an optional parameter so
  the macOS wording drops "wl-clipboard"/"ydotool"; defaults unchanged), `src/llmtr/fakes.py`
  (additive: `FakeRunner`), `config.example.toml` (`notify.backend`, macOS defaults).
- Tests: `tests/test_platforms.py`, `test_macos_exec.py`, `test_macos_clipboard.py`,
  `test_macos_keys.py`, `test_macos_notify.py`, `test_macos_probes.py`, `test_backends.py`; additive
  cases in `tests/test_config.py`, `tests/test_cli.py`, `tests/test_lock.py` (macOS fallback path),
  `tests/test_interfaces.py`.
- Must not change: `lock.py`, `selection.py`, `keys.py`, `clipboard.py`, `notify.py` (v1
  behaviour), prompts, `install.sh`, anything under `macos/`, `scripts/`, `.github/`.

**M11 — macOS install + docs** (sandbox, Linux; real run on the Mac later):

- `install.sh` (dispatch only), `scripts/install-macos.sh` (new), `macos/llmtr.lua.in` (new),
  `README.md` (macOS section: requirements, install, the three permissions with the exact names
  and the dialog text from M8, notifications and `notify.backend`, Caps Lock via Karabiner with the
  rule and setup steps from the proposal, troubleshooting: `llmtr log`, Secure Input, locale),
  `.github/workflows/ci.yml` (a `test-macos` job on `macos-latest`: `uv sync --locked`, pytest,
  ruff; Python 3.13 and 3.14 as in the proposal), `tests/test_install_macos.py` (new) and, only if
  the dispatch needs it, `tests/test_install.py`.
- Must not change: anything in `src/llmtr/`, other tests, `config.example.toml`.

The two lists meet only at two documented contracts: the URL protocol and `LLMTR_RUN_ID` (14.4 and
16) and the `llmtr` absolute path substituted for `@LLMTR_BIN@`.

## 22. Open points (v2)

- Whether the `hammerspoon://` channel is fast enough (unmeasured in M8); M12 checks it. If not,
  `notify.backend = "osascript"` is the escape hatch.
- Accessibility cannot be probed cheaply, so a missing grant is reported on the first copy, not
  at install time (section 18).
- `hs.task` environment handling (merge vs replace) is checked in M11 on the Mac; the Python side
  does not depend on it.

## 23. Cursor engine (v3)

Opt-in engine (`engine = "cursor"`) for a user who may use only Cursor. Source of every API fact:
`docs/tasks/M14-cursor-spike.result.md`. The selected text leaves the machine (README "Cursor
engine (optional)"). With no `engine` key nothing changes: Ollama, its prompts and its tests are
untouched.

### 23.1 Modules

| Module | Job |
| --- | --- |
| `config.py` | `CursorConfig` (`[cursor]`), `Config.engine`, `Config.cursor`, `ENGINES` |
| `cursor_key.py` | `load_key(platform, env=None, *, run=subprocess.run)`, `key_path(env=None)` |
| `cursor_client.py` | `CursorTransport` (protocol), `UrllibCursorTransport(key)` (the only Cursor network code), `CursorClient` (a `ChatClient`), `spawn_cleanup`, `delete_agents`, `sweep`, `parse_sse`, `map_error` |
| `prompts.py` | `CURSOR_PROMPT_TEMPLATE`, `CURSOR_TASKS`, `build_cursor_messages(mode, text, *, source, target, tone)` |
| `engine.py` | `plan_job(..., engine=None)`; `Job.engine`; `progress_text` body `"{model} (Cursor)"` |
| `cli.py` | `--engine {ollama,cursor}`, `make_chat_client(config, engine, platform)`, `llmtr cursor-cleanup [AGENT_ID ...]` |
| `errors.py` | the `Cursor*` classes of 23.5 (all subclass `CursorError`) |
| `fakes.py` | `FakeCursorTransport` (scripted `(method, path)` responses and SSE lists, records calls) |

### 23.2 Config

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `engine` (top level) | `"ollama"`\|`"cursor"` | `"ollama"` | anything else → `ConfigError`; `--engine` overrides it |
| `cursor.model` | string | `"gpt-5.4-nano"` | `"auto"` → no `model` in the create request (account default); `--model` overrides it |
| `cursor.timeout` | float, s, > 0 | `60.0` | create → final text, overall |
| `cursor.request_timeout` | float, s, > 0 | `10.0` | create, get-run, list |
| `cursor.cancel_timeout` | float, s, > 0 | `5.0` | the cancel `POST` |
| `cursor.delete_timeout` | float, s, > 0 | `60.0` | one `DELETE` in the cleanup child |
| `cursor.max_chars` | int, > 0 | `8000` | replaces `ollama.max_chars` for this engine |
| `cursor.base_url` | string | `"https://api.cursor.com"` | `https` only; trailing `/` removed |

`models.*`, `ollama.*` and `--quality` apply only to Ollama. The key is never in `config.toml`:
`CURSOR_API_KEY` env → macOS Keychain (`security find-generic-password -s llmtr-cursor -w`, 5 s,
exit ≠ 0 means "not there") → `$XDG_CONFIG_HOME/llmtr/cursor-api-key`, which is refused unread if
`st_mode & 0o077`. The key is never in argv, a log line, an exception or a `repr`.

### 23.3 Sequence

```
run_shortcut (cursor)
  lock → capture → plan_job(engine="cursor"): one user message, cursor.model, cursor.max_chars
  → notify("Translating PL → EN…", "gpt-5.4-nano (Cursor)")
  → make_chat_client: cursor_key.load_key(platform)          # after the lock: a second press still cancels
  → run_job → CursorClient.chat
       POST /v1/agents {"prompt": {"text"}, "name": "llmtr-<8 hex>", "mode": "agent", "model"?: {"id"}}
                                                              # request_timeout; no repos, no env
       GET  /v1/agents/{id}/runs/{runId}/stream               # until `result`; deadline = cursor.timeout
            `result` {"status", "text"} → FINISHED: text; other status → "Cursor agent failed."
            `status`, `interaction_update`, unknown events ignored (C9: status FINISHED + result CANCELLED)
            stream ends/breaks without `result` → one GET /v1/agents/{id}/runs/{runId}
                FINISHED → `result` string; ERROR/EXPIRED/CANCELLED → agent failed;
                not terminal → CursorTimeout if past the deadline, else CursorError
       finally (agent exists): spawn_cleanup(agent_id)        # detached, never waited for
  → strip_preamble → save_last_result → paste → restore clipboard

spawn_cleanup: Popen([sys.executable, "-m", "llmtr", "cursor-cleanup", id],
                     start_new_session=True, stdin/stdout/stderr=DEVNULL, close_fds=True)
llmtr cursor-cleanup [ID ...]   (child; loads config and key itself, never notifies, exit 0)
  DELETE /v1/agents/{id} for each id (delete_timeout), failures logged
  sweep: skip if $XDG_CACHE_HOME/llmtr/cursor-sweep is < 3600 s old; else write it,
         GET /v1/agents?includeArchived=true&limit=100, DELETE agents named `llmtr-…`,
         not ACTIVE, and older than 10 min when `createdAt` is present; max 10 DELETEs

Cancel (second press → SIGTERM → Cancelled raised in the stream read):
  POST /v1/agents/{id}/runs/{runId}/cancel (cancel_timeout, every error ignored, incl. 409
  run_not_cancellable) → spawn_cleanup → re-raise Cancelled → "Cancelled.", clipboard restored
  Cancelled during the create: no agent id yet, so no cancel and no cleanup (the sweep catches it).
```

The run log line gains `engine=<name>` and, for Cursor, `agent=<first 6 chars>`; never the text,
the key or the whole id. One call is 3 requests (create, stream, delete), so ≤ 6 calls a minute
under the 20 rpm limit.

### 23.4 Prompt

`CURSOR_PROMPT_TEMPLATE` is the M14 contract prompt word for word (line breaks included), with
`{task}` and `{text}` (stripped). Task lines: translate *"Task: translate the text from {src} to
{dst}. Translate every line; keep lines that are already in {dst} unchanged."* (C8 fix), fix as in
M14, tone *"Task: rewrite the text in this tone: {instruction} Keep its language and meaning."*;
each followed by the "Reply with … only" line. The translategemma template and the Ollama
fix/tone prompts are unchanged.

### 23.5 Errors

All through `notify`, urgency critical, clipboard restored (like section 7).

| Situation | Class | Notification |
| --- | --- | --- |
| No key anywhere | `CursorKeyMissing(path)` | `No Cursor API key. Put it in ~/.config/llmtr/cursor-api-key (mode 600).` (macOS: `… (mode 600) or in the Keychain as llmtr-cursor.`) |
| Key file group/other-readable | `CursorKeyInsecure(path)` | `Cursor API key file is readable by others. Run: chmod 600 …/cursor-api-key` |
| 401 | `CursorAuthError` | `Cursor rejected the API key. Create a new one in Cursor Dashboard → API Keys.` |
| 403 `feature_unavailable` | `CursorStorageDisabled` | `Cursor agents need storage: set Cursor Privacy to "Privacy Mode" (not Legacy).` |
| 400 `invalid_model` | `CursorModelInvalid(model)` | `Cursor model {m} is not available. Check cursor.model in config.toml.` |
| 429 | `CursorRateLimited(retry_after)` | `Cursor rate limit reached. Try again in {n} s.` / `… Try again in a minute.` |
| Connection error, 5xx | `CursorUnavailable` | `Can't reach the Cursor API. Check your connection.` |
| No final text in time (or a request timed out) | `CursorTimeout(t)` | `Cursor did not answer within {t} s. Try again.` |
| Other 4xx, bad JSON | `CursorError` | `Cursor refused the request.` |
| Run `ERROR`/`EXPIRED`/`CANCELLED` | `CursorError` | `Cursor agent failed.` |
| Empty text after `strip_preamble` | `OllamaError` (unchanged path in `run_job`) | `The model returned no text.` |
| Cancel `409 run_not_cancellable` | — | not shown |

### 23.6 Testing

- No test reaches `api.cursor.com` (the `sbx` policy blocks it, and no key goes into a sandbox).
  `CursorClient`, `delete_agents` and `sweep` run against `FakeCursorTransport`; deadlines use an
  injected `monotonic`; `spawn_cleanup` is a recording callable, or `subprocess.Popen` is patched.
- `UrllibCursorTransport` runs against a local `http.server` thread on `127.0.0.1`: JSON
  round trip with the Bearer header, an SSE stream split across reads (multi-line `data:`,
  comments, blank-line terminator), a 4xx with `Retry-After`, read timeouts, connection refused.
- `cursor_key` uses `FakeRunner` for the Keychain and `tmp_path` files with real modes.
- `cli` tests patch `cli.UrllibCursorTransport`/`cli.CursorClient` and set `CURSOR_API_KEY`.
- One real-API test, `@pytest.mark.cursor`, skipped unless `LLMTR_CURSOR_TESTS=1`; the
  orchestrator runs it on the host: `LLMTR_CURSOR_TESTS=1 uv run pytest -m cursor`.
