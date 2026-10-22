# CLAUDE.md — llmtr

`llmtr` is a Python CLI that GNOME shortcuts call to translate (PL↔EN), fix grammar, or rewrite the
tone of the selected text using a local Ollama server, then paste the result over the selection.

Scope, decisions and benchmarks: **`docs/proposal.md`** (approved 2026-10-03). Read it before any
task. Module boundaries and interfaces: `docs/architecture.md` (created in M1).

## Hard rules

- **Python only through uv.** Every dependency, run and test goes through the project venv:
  `uv add <pkg>`, `uv add --dev <pkg>`, `uv run …`, `uv sync`. Never `pip install` into the system
  or user site, and never run code with the system `python3`.
- Python 3.13, `src/` layout, package `llmtr`, entry point `llmtr = "llmtr:main"`.
- Prefer the standard library. A new runtime dependency needs a one-line reason in the task's
  hand-back.
- Never call the real Ollama server, clipboard, `ydotool` or `notify-send` from unit tests. Use fakes
  or mocks. Tests that need Ollama carry `@pytest.mark.ollama` and are skipped unless
  `LLMTR_OLLAMA_TESTS=1`.
- Do not change the translategemma prompt template (see `docs/proposal.md`): the model needs it
  word for word, followed by two blank lines before the text.
- Stay inside the files your task contract lists. If you need to touch another file, stop and
  report it in the hand-back.

## Commands

```bash
uv sync                      # create/refresh .venv
uv run pytest                # unit tests (Ollama tests skipped)
LLMTR_OLLAMA_TESTS=1 uv run pytest -m ollama   # real-model tests, host or evaluator only
uv run ruff check .          # lint
uv run ruff format .         # format
uv run llmtr --help          # the CLI
```

A task is done only when `uv run pytest`, `uv run ruff check .` and `uv run ruff format --check .`
all pass.

## Environment facts

- Host: Ubuntu 25.10, GNOME on **Wayland**, RTX 5060 Ti 16 GB, Ollama 0.30.11 on
  `localhost:11434`.
- Desktop tools on the host: `wl-copy`/`wl-paste`, `xclip`, `notify-send`, `zenity`. `ydotool` is
  not installed yet (M3/M4). `wl-paste --primary` hangs here — do not use it.
- Models: `translategemma:12b` (default translate), `translategemma:27b` (`--quality`), `gemma3`
  (fix/tone default), Bielik 4.5b (candidate for Polish fix/tone).
- Ollama URL: `http://localhost:11434` on the host, `http://host.docker.internal:11434` inside a
  Docker sandbox. Read it from config / `OLLAMA_HOST`; never hard-code one of them.

## Orchestration workflow

This project tests a multi-agent build. Roles and milestones are in `docs/proposal.md`.

- The **orchestrator** (main session on the host) writes task contracts in `docs/tasks/`, starts
  workers, reviews, and merges into `main`. It does not write feature code.
- **Workers** run in Docker Sandboxes (`sbx`) in clone mode, one sandbox per task, on a branch named
  `task/<id>`. Each worker reads `CLAUDE.md`, `docs/proposal.md`, and its task file, then commits on
  its branch.
- **Task contract** (`docs/tasks/<id>.md`): goal, files allowed to change, interface to match,
  commands that must pass, out of scope, hand-back format.
- **Hand-back:** the worker ends with a short report in `docs/tasks/<id>.result.md`: what was done,
  test output summary, deviations, new dependencies, open issues.
- **Review loop:** at most two fix rounds per task, then back to the orchestrator. Nothing merges
  with red tests.
- Log every task in `docs/orchestration-log.md` (start/end time, review rounds, notes).

## Code conventions

- Type hints on all public functions; small modules with one job each (see the architecture).
- Errors the user should see go through the notification module with a short, plain message.
- Config: `~/.config/llmtr/config.toml`; state: `~/.local/state/llmtr/state.toml`;
  cache: `~/.cache/llmtr/`. Respect `XDG_*` variables.
- Commit messages: imperative, prefixed with the task id, e.g. `M2-core: add Ollama client`.
