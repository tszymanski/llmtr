# Task M5c-tone-default — make gemma3:12b the default tone model

Role: **Core worker** (follow-up). Sandbox, clone mode. Branch: `task/M5c-tone-default`.
Read `CLAUDE.md`, `eval/report-m5b.md` (summary and switch-cost section).

## Decision (user, 2026-10-04)

The default model for `llmtr tone` changes from `gemma3` to **`gemma3:12b`** (M5b: mean score 4.87
vs 4.36, Polish formal register 100% vs 77%). `fix` stays on `gemma3` and `translate` stays on
`translategemma:12b`.

## Change

- `src/llmtr/config.py`: `ModelsConfig.tone` default → `"gemma3:12b"`. This is the only edit in
  this file, and the orchestrator approves it (the dataclasses were frozen in M1).
- `config.example.toml`: `tone = "gemma3:12b"` with a one-line comment: better formal Polish
  (M5b); about 6 s model reload when alternating with translate on a 16 GB GPU.
- `README.md`: models/requirements section lists `ollama pull gemma3:12b` and mentions the reload
  trade-off in one sentence.
- Tests that pin the old default (e.g. `tests/test_interfaces.py`, `tests/test_config.py`,
  `tests/test_engine.py`; search for them): update them to the new default. `fix` must still
  default to `gemma3`.
- `install.sh` only if it checks or pulls specific models; otherwise leave it.

## Files you may change

`src/llmtr/config.py` (that one default only), `config.example.toml`, `README.md`,
`tests/test_interfaces.py`, `tests/test_config.py`, `tests/test_engine.py`, `install.sh`,
`tests/test_install.py`, `docs/tasks/M5c-tone-default.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `bash -n install.sh`

## Hand-back

Commit on `task/M5c-tone-default` (prefix `M5c:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file.
