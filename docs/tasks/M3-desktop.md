# Task M3-desktop — desktop side

Role: **Desktop worker**. Runs in a Docker sandbox (clone mode). Branch: `task/M3-desktop`.
Runs in parallel with M2-core; the file split below guarantees no overlap.

Read first: `CLAUDE.md`, `docs/proposal.md`, `docs/architecture.md` (the design is approved —
implement it, do not redesign it).

## Goal

Replace every `NotImplementedError` in the desktop-side modules with working code that matches the
signatures, docstrings and behaviour in `docs/architecture.md` (sections 2, 3, 4.1 `[keys]`, 7),
with unit tests as described in section 8 (M3 bullet).

## Files you may change

- `src/llmtr/clipboard.py`
- `src/llmtr/keys.py`
- `src/llmtr/notify.py`
- `src/llmtr/lock.py`
- `src/llmtr/selection.py`
- New tests: `tests/test_clipboard.py`, `tests/test_keys.py`, `tests/test_notify.py`,
  `tests/test_lock.py`, `tests/test_selection.py`
- `docs/tasks/M3-desktop.result.md` (your hand-back)

Anything else (including `config.py`, `errors.py`, `fakes.py`, `tests/test_interfaces.py`, the M2
modules, `cli.py`) is off limits. If you need a change there, describe it in the hand-back instead.

## Requirements

- Standard library only; no `uv add`. All Python through uv (`uv sync`, `uv run …`).
- This sandbox has **no desktop**: no Wayland, clipboard, `ydotool` or `notify-send`. Unit tests
  use `FakeClipboard`, `FakeKeySender`, `FakeNotifier`, `FakeClock` from `llmtr.fakes`, and
  monkeypatch `subprocess.run` / `shutil.which` to assert the exact argv each tool gets. Never
  start a real desktop tool and never signal another real process.
- ydotool on GNOME Wayland: key events by Linux input keycodes (`ydotool key 29:1 46:1 46:0 29:0`
  for Ctrl+C). Keep the keycode table in `keys.py` and test it. Consider explicit modifier key-up
  events for Super/Alt (architecture section 10) — implement if it is a small, testable change, and
  note it in the hand-back.
- Real desktop checks (gedit, Firefox) happen later on the host — list in the hand-back exactly
  what the orchestrator should check manually.

## Must pass

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Hand-back

Commit on `task/M3-desktop` (messages prefixed `M3-desktop:`, each ending with the line
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push or merge. Write
`docs/tasks/M3-desktop.result.md`: what was done, test count and check output summary, any
deviation from the architecture and why, manual host checks to run, open issues.
