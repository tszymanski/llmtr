# Task M4-integration — CLI, installer, README

Role: **Integration worker**. Runs in a Docker sandbox (clone mode). Branch: `task/M4-integration`.

Read first: `CLAUDE.md`, `docs/proposal.md` (incl. the 2026-10-04 decisions: text-only clipboard,
GUI apps only, default keys `ctrl+c`/`ctrl+v`, no Window Calls dependency), `docs/architecture.md`
(sections 2 `cli.py`, 3, 7, 8 M4 bullet, 9), and `scripts/install-ydotool.sh`.

M2 (model side) and M3 (desktop side) are merged and tested. Wire them together; do not change
them. If you find a bug in an M2/M3 module, report it in the hand-back with a failing test idea —
do not fix it.

## Deliverables

1. `src/llmtr/cli.py` — implement `main` and `run_shortcut` (and anything else stubbed there)
   exactly per architecture section 3: shortcut flow, `tone --next`, `--stdin`, cancel on second
   press, clipboard-only fallback, notifications, exit codes. `build_parser` is final; keep it.
2. `tests/test_cli.py` — end-to-end tests of `main()` with all fakes injected (architecture
   section 8, M4 bullet): each mode, `--quality`, `--model`, `tone --next` cycling, `--stdin`,
   errors from section 7 (Ollama down, model missing, timeout, empty selection, ydotool missing →
   clipboard fallback), cancel path restores the clipboard.
3. `install.sh` (repo root, bash, idempotent, run as the normal user):
   - checks `uv`, `ollama`, `wl-copy`/`wl-paste`, `notify-send`; prints what is missing.
   - installs the CLI with `uv tool install --force --reinstall .` (never pip).
   - if `ydotool` ≥ 1.0 or the `ydotoold` user service is missing, tells the user to run
     `scripts/install-ydotool.sh` (or runs it with `--with-ydotool`); never calls sudo itself
     otherwise.
   - registers four GNOME custom shortcuts with `gsettings`
     (`org.gnome.settings-daemon.plugins.media-keys custom-keybindings`), **appending** to the
     existing list and replacing only its own entries on re-run:
     `<Super><Alt>t` → `llmtr translate`, `<Super><Alt>g` → `llmtr fix`,
     `<Super><Alt>r` → `llmtr tone`, `<Shift><Super><Alt>r` → `llmtr tone --next`.
     Use the **absolute path** of the installed `llmtr` (GNOME may not have `~/.local/bin` on
     PATH).
   - `install.sh --uninstall` removes its shortcuts and the uv tool, leaves config and ydotool.
   - `install.sh --dry-run` prints every command instead of running it.
4. `tests/test_install.py` — runs `install.sh --dry-run` (and a normal run with a temp `PATH` of
   fake `gsettings`/`uv`/`systemctl`/… scripts that log their argv) and asserts the commands,
   the appended keybinding list, and idempotent re-run. No real gsettings/uv tool install.
5. `config.example.toml` (repo root) — every key from architecture section 4.1 with its default and
   a one-line comment; the `team` tone preset included.
6. `README.md` — what it does, requirements, install (`scripts/install-ydotool.sh`, then
   `./install.sh`), shortcuts table, config, `--stdin` usage for manual checks, troubleshooting
   (ydotool socket, Ollama not running, model not pulled), uninstall.

## Files you may change

`src/llmtr/cli.py`, `tests/test_cli.py`, `install.sh`, `tests/test_install.py`,
`config.example.toml`, `README.md`, `docs/tasks/M4-integration.result.md`. Nothing else.

## Requirements

- Standard library only; no `uv add`. All Python through uv.
- No test touches a real desktop tool, Ollama, gsettings, systemctl or `uv tool install`.
- The sandbox has no desktop and no Ollama access; that is expected.

## Must pass

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
bash -n install.sh
```

## Hand-back

Commit on `task/M4-integration` (messages prefixed `M4-integration:`, each ending with the line
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push or merge. Write
`docs/tasks/M4-integration.result.md`: what was done, test count and check output, deviations,
bugs found in M2/M3 modules, and the exact manual host checklist (gedit, Firefox, cancel, tone
cycling, fallback without ydotoold) for the orchestrator.
