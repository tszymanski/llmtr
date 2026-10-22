# Task M2-core — model side

Role: **Core worker**. Runs in a Docker sandbox (clone mode). Branch: `task/M2-core`.
Runs in parallel with M3-desktop; the file split below guarantees no overlap.

Read first: `CLAUDE.md`, `docs/proposal.md`, `docs/architecture.md` (the design is approved —
implement it, do not redesign it).

## Goal

Replace every `NotImplementedError` in the model-side modules with working code that matches the
signatures, docstrings and behaviour in `docs/architecture.md` (sections 2, 4, 5, 6, 7), with unit
tests as described in section 8 (M2 bullet).

## Files you may change

- `src/llmtr/config.py` — function bodies only (dataclasses and constants are final)
- `src/llmtr/langdetect.py`
- `src/llmtr/prompts.py` — function bodies only (`TRANSLATEGEMMA_TEMPLATE` and other prompt
  constants are final)
- `src/llmtr/ollama_client.py`
- `src/llmtr/engine.py`
- New tests: `tests/test_config.py`, `tests/test_langdetect.py`, `tests/test_prompts.py`,
  `tests/test_ollama_client.py`, `tests/test_engine.py`
- `docs/tasks/M2-core.result.md` (your hand-back)

Anything else (including `errors.py`, `fakes.py`, `tests/test_interfaces.py`, the M3 modules,
`cli.py`) is off limits. If you need a change there, describe it in the hand-back instead.

## Requirements

- Standard library only; no `uv add`. All Python through uv (`uv sync`, `uv run …`).
- Unit tests use `FakeTransport` / `FakeChatClient` from `llmtr.fakes`, `tmp_path`, and a local
  `http.server` thread on 127.0.0.1 for `UrllibTransport`. No unit test calls Ollama.
- Optional: one test marked `@pytest.mark.ollama` that translates a short PL sentence with
  `translategemma:12b` through the real client (skipped unless `LLMTR_OLLAMA_TESTS=1`). In this
  sandbox Ollama is at `http://host.docker.internal:11434` (set `OLLAMA_HOST` accordingly); the
  network rule for it may not be enabled, so a skip/failure there is not a blocker — report it.
- Cover the error cases in architecture section 7 that belong to the model side.

## Must pass

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Hand-back

Commit on `task/M2-core` (messages prefixed `M2-core:`, each ending with the line
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push or merge. Write
`docs/tasks/M2-core.result.md`: what was done, test count and check output summary, any deviation
from the architecture and why, open issues.
