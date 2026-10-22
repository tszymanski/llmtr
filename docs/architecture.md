# llmtr architecture (M1)

Status: proposed by the Architect on 2026-10-03, awaiting user approval. Scope and decisions come
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
