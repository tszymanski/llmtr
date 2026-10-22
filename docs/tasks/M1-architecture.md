# Task M1-architecture — module boundaries, interfaces, config schema

Role: **Architect**. Branch: `task/M1-architecture`. Read `CLAUDE.md` and `docs/proposal.md` first.

## Goal

Turn the approved proposal into a buildable design that two workers can implement **in parallel
without touching each other's files**: the core worker (M2: model side) and the desktop worker (M3:
clipboard/keys/notifications/lock). The integration worker (M4) later wires them in `cli.py`.

## Deliverables

1. `docs/architecture.md` containing:
   - Module list: for each module its single responsibility, public functions/classes with full
     signatures, the errors it raises, and which milestone/worker owns it (M2, M3 or M4).
   - The end-to-end call sequence for `llmtr translate`, `llmtr fix`, `llmtr tone`,
     `llmtr tone --next`, including clipboard save/restore, copy/paste keystrokes, the clipboard-only
     fallback, the single-run lock and cancel-on-second-press.
   - Config schema for `~/.config/llmtr/config.toml` (every key, type, default) covering: Ollama URL
     (`OLLAMA_HOST` env overrides it), timeouts, `keep_alive`, model per mode, `--quality` model,
     temperature, language pair, `[keys]` + `[[keys.override]]`, tone presets (name + instruction,
     default preset `team` = informal team message), notification on/off. Plus the state file
     `~/.local/state/llmtr/state.toml` (current tone) and cache `~/.cache/llmtr/last.txt`.
   - Prompt design per mode: the exact translategemma template (copy it verbatim from the proposal,
     two blank lines before the text), and system/user prompts for `fix` and the `team` tone, plus
     the post-filter that strips preambles.
   - PL/EN language detection approach (stdlib only, heuristic is fine) and how direction is chosen.
   - Error handling: what the user sees (notification text) for Ollama down, model missing, timeout,
     empty selection, ydotool missing.
   - Testing strategy: which fakes/protocols let M2 and M3 test without Ollama or a desktop.
   - "Work split" section: exact file list for M2, M3, M4.
2. Typed stubs in `src/llmtr/` for every module: signatures, docstrings, dataclasses/Protocols and
   constants, bodies `raise NotImplementedError` (config dataclasses and constants may be real).
   `llmtr:main` must stay importable.
3. `tests/test_interfaces.py`: imports every module and checks the public names exist.

## Constraints

- Standard library only for runtime (use `tomllib` to read TOML, `urllib.request` for HTTP, a tiny
  writer for the one-key state file). If you think a dependency is truly needed, argue it in the
  result file instead of adding it.
- Python ≥ 3.13, type hints everywhere, small modules with one job.
- Desktop side must hide tools behind Protocols (e.g. `Clipboard`, `KeySender`, `Notifier`) so tests
  use fakes; the model side must hide HTTP behind an injectable transport.
- All Python through uv (`uv run …`). Do not pip install anything.

## Files you may change

`docs/architecture.md`, `src/llmtr/**`, `tests/test_interfaces.py`,
`docs/tasks/M1-architecture.result.md`. Nothing else.

## Must pass

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Out of scope

Implementing behaviour, install script, GNOME shortcuts, evaluation samples.

## Hand-back

Commit on `task/M1-architecture` with messages prefixed `M1-architecture:`. Write
`docs/tasks/M1-architecture.result.md`: summary, decisions you made that the proposal left open,
test/lint output summary, open questions for the user.
