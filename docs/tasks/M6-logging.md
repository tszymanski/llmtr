# Task M6-logging — error and run log in a file

Role: **Integration worker**. Sandbox, clone mode. Branch: `task/M6-logging`.
Read `CLAUDE.md`, `docs/architecture.md` (§2 `cli.py`, `config.py`, §4, §7), `src/llmtr/cli.py`,
`src/llmtr/errors.py`, `src/llmtr/config.py`.

## Why

When GNOME runs a shortcut, stderr is lost and the notification shows only a short
`user_message`. Diagnosing the 2026-10-04 tone bug needed a temporary debug wrapper to see the
hidden `detail` ("Nothing is copied"). The user wants a permanent error log.

## Behaviour

- **Log file:** `$XDG_STATE_HOME/llmtr/llmtr.log` (default `~/.local/state/llmtr/llmtr.log`).
  Create the directory if needed. Use stdlib `logging` with
  `logging.handlers.RotatingFileHandler` (1 MB, 1 backup). Format:
  `2026-10-05 23:41:07,123 ERROR [12345] message` (ISO-like time, level, PID).
- **What is logged:**
  - Every run, one INFO line at the end: mode (and `--next`/`--show`/`--stdin`/`--quality`),
    model, outcome (`ok`, `cancelled`, `error:<ErrorClass>`), total duration in seconds,
    input/output **lengths only**, and whether keystrokes or the clipboard-only fallback were
    used.
  - Every `LlmtrError`: ERROR line with class, `user_message` and `detail`, plus the traceback.
  - Every **unexpected** exception (not `LlmtrError`, not `SystemExit`/`KeyboardInterrupt`):
    `main` must catch it, log it at ERROR with the traceback, restore the clipboard if a capture
    happened (reuse the existing restore path), notify `Unexpected error — see <log path>` (or
    print it to stderr with `--stdin`), and return `EXIT_ERROR`. Today such an exception escapes
    with only a stderr traceback that GNOME discards.
  - Cancel (second press) is INFO, not ERROR.
- **Privacy:** never log the selected text, the model output, or clipboard contents. Lengths
  only. Error `detail` strings are fine (they come from tool stderr and HTTP errors). Add a test
  that the sample text does not appear in the log.
- **Config** (`config.py`, the orchestrator approves extending the frozen dataclasses): new
  `LogConfig` with `enabled: bool = True` and `level: str = "info"` (`"debug" | "info" |
  "error"`), plus a `[log]` section in `parse_config` with validation (`ConfigError` on a bad
  level), `Config.log`, and `config.example.toml`. `enabled = false` → no file is created.
  `LLMTR_LOG_LEVEL` env overrides `level`.
- If the log file cannot be opened (read-only dir, etc.), llmtr must still work: fall back to no
  file logging and never crash because of logging.
- A config error must also be logged, so set up logging with defaults first and reconfigure after
  the config loads.
- **`llmtr log`** subcommand (small): prints the log path, and with `--tail N` (default 20) the
  last N lines. No lock or notifications. This needs a `build_parser` change; the orchestrator
  approves it.

## New module

`src/llmtr/log.py`: `log_path(env) -> Path`, `setup_logging(config: LogConfig | None, env) ->
logging.Logger | None`, and a small `RunRecord` dataclass (or similar) that `cli.py` fills and
logs once at the end. Keep `cli.py` changes focused.

## Files you may change

`src/llmtr/log.py` (new), `src/llmtr/cli.py`, `src/llmtr/config.py` (`LogConfig`, `Config.log`,
`[log]` parsing only), `config.example.toml`, `README.md` (Troubleshooting: where the log is,
`llmtr log --tail`, privacy note), `tests/test_log.py` (new), `tests/test_cli.py`,
`tests/test_config.py`, `tests/test_interfaces.py` (only if it lists modules/public names),
`docs/tasks/M6-logging.result.md`.

## Tests

`tests/test_log.py`: path resolution with `XDG_STATE_HOME`, rotation settings, an unwritable dir
falls back silently, levels, `enabled=false` writes nothing. `tests/test_cli.py`: a
`ClipboardUnavailable("Nothing is copied")` run writes ERROR with the detail; an unexpected
`RuntimeError` from a fake client is caught, logged with its traceback, the clipboard is
restored, the notification names the log path, exit 1; a successful run writes one INFO line
with lengths; the sample text is absent from the log; `llmtr log --tail 2` prints two lines. All
tests use `tmp_path` via `XDG_STATE_HOME`, never the real home.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `bash -n install.sh`.
Run everything in the foreground.

## Hand-back

Commit on `task/M6-logging` (prefix `M6-logging:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file with a
sample of the log output.
