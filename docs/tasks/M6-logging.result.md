# M6-logging — result

## What was done

- **`src/llmtr/log.py`** (new): `log_path(env)`, `setup_logging(config: LogConfig | None, env)`,
  and `RunRecord` (a frozen dataclass with `__str__` producing the one-line summary). Uses
  stdlib `logging` with a `RotatingFileHandler` (1 MB, 1 backup) on the `"llmtr"` logger, format
  `%(asctime)s %(levelname)s [%(process)d] %(message)s`. `setup_logging` always clears any
  previously attached handler first (safe to call twice — defaults, then the loaded config), and
  returns `None` without creating anything if `enabled` is false or the log file can't be opened
  (caught as a broad `OSError`, e.g. a read-only `XDG_STATE_HOME`).
- **`src/llmtr/config.py`**: new frozen `LogConfig(enabled: bool = True, level: str = "info")`,
  `Config.log` field, `LOG_LEVEL_ENV = "LLMTR_LOG_LEVEL"` constant, and `[log]` parsing in
  `parse_config` (same override pattern as `OLLAMA_HOST`: a non-empty `LLMTR_LOG_LEVEL` replaces
  the table value before validation; `ConfigError` if the final level isn't `debug`/`info`/
  `error`).
- **`src/llmtr/cli.py`**:
  - `main()` calls `log.setup_logging(None)` before loading the config (so a bad config file is
    still logged with a traceback), then `log.setup_logging(config.log)` once the config is in,
    and threads the resulting `Logger | None` into `run_shortcut`/`_run_stdin`.
  - `run_shortcut` and `_run_stdin` now build a `RunRecord` (mode, model, outcome, duration,
    input/output **lengths**, keystrokes-used flag) in a `finally` block, so exactly one INFO
    line is written per run regardless of which branch returns. `Cancelled` logs that INFO line
    with `outcome=cancelled` and **no** ERROR line. Any other `LlmtrError` logs an ERROR line
    with the class, `user_message` and `detail`, plus traceback (`exc_info=True`). A new broad
    `except Exception` (added alongside the existing `except LlmtrError`) catches anything
    unexpected, restores the clipboard via the existing `restore_clipboard` path if a capture had
    happened, logs it at ERROR with traceback, notifies/prints `Unexpected error — see <log
    path>`, and returns `EXIT_ERROR` — this previously escaped with only a stderr traceback that
    GNOME discards.
  - New `llmtr log [--tail N]` subcommand (`build_parser` change, `_run_log` helper): prints
    `log.log_path()`, then the file's last `N` lines (default 20) if it exists. No lock, config
    load or notifications.
- **`config.example.toml`** / **`README.md`**: documented the new `[log]` section and a
  Troubleshooting entry explaining where the log lives, `llmtr log --tail`, the privacy
  guarantee (lengths only, never selected text/model output/clipboard contents), and what
  "Unexpected error — see ..." means.
- Tests: new `tests/test_log.py` (path resolution, rotation settings, levels, `enabled=false`
  writes nothing, an unwritable directory falls back to `None` silently, format, no duplicate
  handlers on a second `setup_logging` call, `RunRecord.__str__`). Additions to
  `tests/test_cli.py` (an `LlmtrError` with `detail` writes an ERROR line with that detail; an
  unexpected `RuntimeError` from a fake client is caught/logged/restores the clipboard/notifies
  the log path/exit 1; a successful run writes exactly one INFO line with lengths and never the
  sample text; `llmtr log --tail N` / `llmtr log` without a file). Additions to
  `tests/test_config.py` (`[log]` defaults/overrides, bad level `ConfigError`, `LLMTR_LOG_LEVEL`
  override and its own validation, empty env var doesn't override). `tests/test_interfaces.py`
  updated with `LogConfig`/`LOG_LEVEL_ENV` in `llmtr.config`'s public-name list and a
  `cfg.log` defaults check.

## Checks

```
uv run pytest            -> 292 passed, 1 skipped (the @pytest.mark.ollama test)
uv run ruff check .      -> All checks passed!
uv run ruff format --check .  -> 69 files already formatted
bash -n install.sh       -> OK (no output, exit 0)
```

## Sample log output

(generated via `log.setup_logging` + `RunRecord`, representative of a real run/error sequence)

```
2026-10-05 21:51:13,134 INFO [5365] mode=translate model=translategemma:12b outcome=ok duration=1.842s input_len=27 output_len=24 keystrokes=True
2026-10-05 21:51:13,134 ERROR [5365] Unexpected error: simulated: client.chat() blew up
Traceback (most recent call last):
  File "<string>", line 9, in <module>
    raise RuntimeError('simulated: client.chat() blew up')
RuntimeError: simulated: client.chat() blew up
2026-10-05 21:51:13,134 ERROR [5365] ClipboardUnavailable: No working clipboard tool. Install wl-clipboard. (Nothing is copied)
2026-10-05 21:51:13,134 INFO [5365] mode=fix outcome=cancelled duration=0.003s input_len=0 output_len=0
```

`llmtr log --tail 1` against a log file prints the path, then just the last line, e.g.:

```
/home/you/.local/state/llmtr/llmtr.log
2026-10-05 21:51:14,200 ERROR [5366] boom
```

## Deviations / notes

- The contract's hand-back line says to end commits with `Co-Authored-By: Claude Opus 5.5
  <noreply@anthropic.com>`, but this session's attribution instructions (which explicitly say
  they replace any earlier copy of this guidance) say `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` — this worker is in fact Sonnet 5, so commits use that line instead.
- `tests/test_interfaces.py` was touched only for the `llmtr.config` public-name list and the
  `Config` defaults assertion, per "only if it lists modules/public names" — no new `llmtr.log`
  entry was added there since `docs/architecture.md` (which I'm not allowed to edit under this
  contract) doesn't document `log.py`'s interface yet.
- No new runtime dependency: `logging`/`logging.handlers` are stdlib.

## Open issues

- None. `docs/architecture.md` doesn't yet document `log.py`/`[log]`/`llmtr log` — worth an
  orchestrator pass to add module/schema/CLI entries there since I couldn't edit that file under
  this task's file list.

## Fix round 1

Addressed all three reviewer findings:

1. **`tone --next`/`tone --show` had no logging instrumentation (major).** Both helpers
   (`_run_tone_next`, `_run_tone_show` in `src/llmtr/cli.py`) now take an optional `logger`
   parameter, threaded in from `main()`. Each wraps its body in the same
   `try`/`except Exception`/`finally` shape as `_run_stdin`/`run_shortcut`: on success or failure
   it logs one INFO `RunRecord` line (`flags=("next",)` or `("show",)`, mode `tone`, `outcome`
   `ok` or `error:<Class>`); an unexpected exception is logged at ERROR with `exc_info=True` and
   reported as `Unexpected error — see <log path>` — via the notifier for `--show`/`--next`, or
   printed to stderr for `--show --stdin` — then returns `EXIT_ERROR`. `--next` can never be
   combined with `--stdin` (rejected earlier in `main()` as a usage error), so its notifier is
   always real.
   - New tests in `tests/test_cli.py`: `test_main_tone_next_writes_info_line`,
     `test_main_tone_show_writes_info_line`,
     `test_main_tone_next_unexpected_exception_logged_and_notifies_log_path`,
     `test_main_tone_show_unexpected_exception_logged_and_notifies_log_path`,
     `test_main_tone_show_stdin_unexpected_exception_prints_to_stderr`.
2. **Case-sensitive `log.level`/`LLMTR_LOG_LEVEL` validation (minor).** `parse_config` in
   `src/llmtr/config.py` now does `level = level.strip().lower()` before the `_LOG_LEVELS`
   membership check, so `level = "INFO"` or `LLMTR_LOG_LEVEL=DEBUG` no longer raise `ConfigError`.
   Added `test_parse_config_log_level_accepts_mixed_case_from_config_and_env` in
   `tests/test_config.py`.
3. **No test that a `ConfigError` is written to the log (minor).** Added
   `test_main_bad_config_writes_error_to_log` in `tests/test_cli.py`, asserting the log file
   contains `ConfigError` and the bad-config message after a bad `--config` run.

### Checks (fix round 1)

```
uv run pytest                 -> 299 passed, 1 skipped (the @pytest.mark.ollama test)
uv run ruff check .            -> All checks passed!
uv run ruff format --check .   -> 70 files already formatted
bash -n install.sh             -> OK (no output, exit 0)
```
