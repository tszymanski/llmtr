# Task M10-macos-backends — implement the macOS desktop backends

Role: **Desktop worker**. Sandbox, clone mode. Branch: `task/M10-macos-backends`.
Runs **in parallel with M11** (installer/docs); the file lists do not overlap.
Read `CLAUDE.md`, `docs/proposal.md` ("macOS support (v2)"), `docs/architecture.md` (v2 part,
§11–22, binding) and `docs/tasks/M8-spike.result.md`. `spike/macos/` has calls that worked on the
real Mac.

## Goal

Replace every `NotImplementedError` from M9 with working code, wire `cli.py` to the platform layer,
and test all of it with fakes, so `llmtr` works on macOS through Hammerspoon and is unchanged on
Linux. The design is fixed in `docs/architecture.md`; follow it. If something in it cannot work,
stop and report (see "Done when").

## Change

Exactly the M10 list in `docs/architecture.md` §21, including:

- `platforms.py`, `macos_exec.py`, `macos_clipboard.py`, `macos_keys.py`, `macos_notify.py`,
  `macos_probes.py`, `backends.py`: full implementations per §12–14.
- `config.py`: the `platform=` argument of `parse_config`/`load_config` (macOS key defaults only
  for keys the user did not set, §13) and `notify.backend` parsing/validation. Dataclass defaults
  unchanged. *(Reviewer note from M9: these signature changes were left to you on purpose.)*
- `cli.py`: use `backends`/`Desktop` instead of building `NotifySendNotifier`/`YdotoolKeySender`
  directly; `desktop=` parameter for tests; the macOS paste hint (⌘V); the Secure Input message
  (§18, §19). Linux flows keep their exact behaviour and messages.
- `errors.py`: only the optional message parameters for `ClipboardUnavailable` and
  `EmptySelection(False)` (defaults unchanged), approved by the user.
- `fakes.py`: add `FakeRunner` (§20) — *M9 reviewer note: it has no stub yet; add it and its
  `tests/test_interfaces.py` check.*
- `config.example.toml`: `notify.backend` and a comment on the macOS key defaults.
- Tests: the new test files and additive cases listed in §21, including:
  - the clipboard backend sets `LC_CTYPE=UTF-8` even when the given env has no locale (M8 bug);
  - every tool is called by absolute path (`/usr/bin/pbcopy`, `/usr/bin/pbpaste`,
    `/usr/bin/osascript`, `/usr/bin/open`, `/usr/sbin/ioreg`);
  - osascript errors 1002 and −1743 and a timeout map to the `MacKeySendError` reasons;
  - the Hammerspoon URL is built and encoded correctly (Polish text, `&`, `=`, spaces, newlines);
  - `notify.backend` selection and that notifying never raises;
  - `default_lock_path` on macOS without `XDG_RUNTIME_DIR` (§15);
  - an existing config without `[keys]` on `platform="darwin"` gets `cmd+c`/`cmd+v`/0, and one
    with explicit keys keeps them.
  No test may call real `osascript`, `pbcopy`, `pbpaste`, `open` or `ioreg`.

## Files you may change

Only the M10 list in `docs/architecture.md` §21, plus `docs/tasks/M10-macos-backends.result.md`.
Not: `lock.py`, `selection.py`, `keys.py`, `clipboard.py`, `notify.py`, prompts, `install.sh`,
`scripts/`, `macos/`, `.github/`, `README.md`, `docs/architecture.md`, `docs/proposal.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Done when

All of these hold; stop as soon as they do, and do not start M11 work:

1. No `NotImplementedError` is left in `src/llmtr/` (`grep -rn NotImplementedError src/` is empty).
2. Every test listed under "Change" exists and passes; `tests/test_interfaces.py` is green.
3. Linux behaviour is unchanged: no existing test was edited except additive cases in the files
   §21 names, and every existing test still passes unmodified.
4. The three "Must pass" commands exit 0 in a final run after the last edit.
5. The result file is written (sections below) and everything is committed on
   `task/M10-macos-backends`; `git status` is clean.

If a condition cannot be met (the architecture is wrong, or the rerun limit is hit), stop, explain
it in the result file under "Open issues", commit what is done, and finish.

## Reruns

You may fix and rerun a failing "Must pass" command **at most 3 times**; restart or `--continue`
the session **at most once**. Rerunning after an intended code change is normal work, not a
rerun. Record every rerun in the result file under **"Reruns"**, one line each: what was rerun, why
(shortened error text), what changed. Write "Reruns: none" if there were none. At the limit: stop
as described under "Done when".

## Out of scope

Installer, Hammerspoon Lua file, README, CI (M11); model or prompt changes; Services.

## Hand-back

Commit on `task/M10-macos-backends` (prefix `M10-macos-backends:`; end each message with a
`Co-Authored-By` line naming the model you actually run as). Do not push. Result file sections:
**Summary**, **Deviations**, **Reruns**, **New dependencies** (expected: none), **Open issues**,
and the final output of the three "Must pass" commands.
