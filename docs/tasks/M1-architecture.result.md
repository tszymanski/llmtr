# M1-architecture — result

Branch `task/M1-architecture`. Status: done, awaiting user approval of `docs/architecture.md`.

## Summary

- `docs/architecture.md`: modules with signatures, errors and owners; call sequences for
  translate/fix/tone, `tone --next`, `--stdin` and cancel-on-second-press; full config/state/cache
  schema; prompts for every mode and the post-filter; PL/EN detection; error→notification table;
  testing strategy; work split.
- Typed stubs in `src/llmtr/`: `config.py`, `langdetect.py`, `prompts.py`, `ollama_client.py`,
  `engine.py` (M2); `clipboard.py`, `keys.py`, `notify.py`, `lock.py`, `selection.py` (M3);
  `cli.py` (M4). Bodies raise `NotImplementedError`.
- Real code, final in M1: `errors.py` (all user-facing errors with messages), `fakes.py` (fakes for
  every Protocol + `FakeClock`), config dataclasses/constants, prompt constants (template verbatim),
  `cli.build_parser`, `__init__.py`/`__main__.py`.
- `tests/test_interfaces.py`: public names per module, fakes satisfy the Protocols, config
  defaults, error messages, parser, and the translategemma template compared with
  `docs/proposal.md` text.

## Decisions the proposal left open

1. New `engine.py` (mode → `Job` → result) and `selection.py` (capture/deliver with clipboard
   save/restore) so `cli.py` stays thin wiring and both are testable with fakes.
2. Shared `errors.py` and `fakes.py` written now and frozen, so M2 and M3 never edit a common file.
3. Copy detection: clear the clipboard, send the copy key, poll up to `keys.copy_timeout`; still
   empty → "No text selected" (old clipboard restored).
4. No ydotool: read the current clipboard as the input (user copies by hand), leave the result on
   the clipboard, notify "Press Ctrl+V". Clipboard is text-only; images are not preserved.
5. Any press while a job runs only cancels it (SIGTERM via a PID in an `flock`ed file under
   `$XDG_RUNTIME_DIR`); it never starts a new job. `tone --next` takes no lock.
6. `--stdin` mode (no desktop, prints result) for manual checks and M5 evaluation; `--model`
   override.
7. Config additions: `ollama.max_chars` (8000, avoids silent truncation at `num_ctx` 4096),
   `ollama.num_ctx` (4096), `keys.start_delay`/`copy_timeout`/`paste_delay`, `languages.native` /
   `languages.other`. `OLLAMA_HOST` is normalized (scheme, port, `0.0.0.0` → `127.0.0.1`).
8. fix/tone wrap the text in `<text>…</text>` so the model does not answer the text; post-filter
   strips preambles, tags, wrapping quotes/fences and restores outer whitespace.
9. Language detection ties go to "not Polish" → translated into Polish (proposal rule).
10. `notify.enabled = false` hides only progress notifications; errors and hints are always shown.

## Checks

- `uv run pytest`: 21 passed.
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: 24 files already formatted.

No new dependencies. No files outside the contract were touched.

## Open questions for the user

- Does GNOME pass the sent Ctrl+C while Super+Alt are still held? v1 waits `keys.start_delay`
  (0.25 s); M3 should verify on the host and may add explicit modifier key-ups.
- Is a per-app key override worth requiring the Window Calls extension, or keep defaults only?
- OK to lose non-text clipboard content (images) during a run in v1?
