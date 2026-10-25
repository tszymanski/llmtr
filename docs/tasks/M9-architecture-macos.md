# Task M9-architecture-macos — platform layer and macOS interfaces

Role: **Architect**. Sandbox, clone mode. Branch: `task/M9-architecture-macos`.
Read `CLAUDE.md`, `docs/proposal.md` (section "macOS support (v2)", approved), `docs/architecture.md`
and `docs/tasks/M8-spike.result.md` (evidence from the real Mac; `spike/macos/` shows working calls).

## Goal

Extend the v1 design so that M10 (macOS desktop backends, sandbox) and M11 (macOS installer, README,
CI) can be built **in parallel without touching each other's files**, and so that Linux behaviour
does not change. The macOS decisions are fixed in the proposal; this task turns them into
interfaces, not new decisions. If evidence forces a deviation, argue it in the result file.

## Deliverables

1. **`docs/architecture.md`** updated (keep v1 content; mark new parts "v2"):
   - **Platform selection:** one place that picks the backends from `sys.platform` (injectable for
     tests), and how `cli.py` gets them. Today `cli.py` builds `NotifySendNotifier` and
     `YdotoolKeySender` directly; specify the factory/bundle that replaces this.
   - **macOS backends** behind the existing Protocols (`Clipboard`, `KeySender`, `Notifier`), with
     full signatures, errors and where they live (existing modules or new ones — your call, one job
     per module):
     - clipboard: `/usr/bin/pbcopy` / `/usr/bin/pbpaste` by absolute path, **always** with
       `LC_CTYPE=UTF-8` in the child env even if `os.environ` has none (M8 bug); empty/non-text → `""`.
     - keys: `/usr/bin/osascript` → System Events keystroke; how `"cmd+c"`-style combos map to
       `keystroke "c" using {command down}`; error mapping for osascript failures: 1002 (no
       Accessibility) and Automation denied (−1743) → `KeySendError` with a user message naming the
       System Settings entry for **Hammerspoon**. What `available()` means on macOS.
     - notify: `HammerspoonNotifier` (URL event `hammerspoon://llmtr?…` via `open -g`; one bubble per
       run, "Translating…" withdrawn/replaced) and an `osascript` fallback; how the fallback is
       chosen (config key and/or detection), and that notifying never raises.
     - focused app: bundle ID via `osascript` (only for logging/overrides; may return `None`).
     - Secure Input hint: a function that reads `ioreg -l -w 0` (`kCGSSessionSecureInputPID`) and
       returns the app name, called **only** after "nothing copied", to make the message specific.
   - **Platform-dependent defaults:** `[keys] copy/paste` (`ctrl+c`/`ctrl+v` on Linux,
     `cmd+c`/`cmd+v` on macOS) and `start_delay` (0.25 on Linux, 0 on macOS: release binding). Say
     how the config schema expresses this without breaking existing configs and tests.
   - **Lock path on macOS:** `default_lock_path` uses `$XDG_RUNTIME_DIR`, which macOS does not set;
     specify the fallback (cancel on second press must work there).
   - **Hammerspoon side:** the interface of `llmtr.lua`: five bindings on key **release**
     (`hs.hotkey.bind(mods, key, nil, fn)`), `hs.task` with the **absolute** `llmtr` path (filled in
     by the installer), the env it passes, the `hs.urlevent` handler for notifications, and where the
     Lua template lives in the repo. No logic beyond launching `llmtr` and showing notifications.
   - **Installer split:** how `install.sh` dispatches on `uname -s` (Linux part unchanged), what the
     macOS part does (uv tool install, Hammerspoon present?, Lua file + idempotent `require` line,
     open the three Settings panes from the proposal, `--uninstall`), and which file holds it.
   - **Call sequence** for `llmtr translate` on macOS (like §3.1), including the permission-failure
     and Secure Input paths and the clipboard-only fallback.
   - **Error table** additions (§7) with the exact short user messages.
   - **Testing strategy:** fakes for each macOS backend; a test that the clipboard backend sets
     `LC_CTYPE`; how tests force the platform; nothing calls real `osascript`/`pbcopy`/`open`.
   - **Work split:** exact file lists for **M10** (backends, factory, config defaults, lock
     fallback, their tests) and **M11** (installer, Lua template, README macOS section with
     permissions and the optional Karabiner setup from the proposal, CI `macos-latest` job, installer
     tests). No file in both lists.
2. **Typed stubs** for every new public class/function: signatures, docstrings, bodies
   `raise NotImplementedError` (constants and dataclasses may be real). Existing code keeps working:
   do not change behaviour on Linux.
3. **`tests/test_interfaces.py`**: the new public names exist.

## Constraints

- Standard library only. Python ≥ 3.13, type hints, small modules with one job.
- Keep every existing public signature and the translategemma prompt untouched.
- All Python through uv.

## Files you may change

`docs/architecture.md`, `src/llmtr/**` (stubs and new modules only; no behaviour change),
`tests/test_interfaces.py`, `docs/tasks/M9-architecture-macos.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Done when

All of these hold; stop as soon as they do, and do not start M10/M11 work:

1. `docs/architecture.md` covers every bullet under Deliverables 1, including the M10/M11 work
   split with no file in both lists.
2. Every new public name in the architecture has a typed stub in `src/llmtr/` and is checked in
   `tests/test_interfaces.py`.
3. Linux behaviour is unchanged: no existing test was edited except `tests/test_interfaces.py`, and
   `git diff main -- src/` contains only additions (new stubs, new modules, new names), no changed
   bodies of existing functions.
4. The three "Must pass" commands exit 0 in a final run after the last edit.
5. `docs/tasks/M9-architecture-macos.result.md` is written (sections below) and everything is
   committed on `task/M9-architecture-macos`; `git status` is clean.

If a condition cannot be met (e.g. a decision in the proposal turns out impossible), stop, write
why in the result file under "Open points", commit what is done, and finish.

## Reruns

Record every rerun in the result file under **"Reruns"**, one line each: what was rerun (a "Must
pass" command, a whole step, or the session itself after a restart/`--continue`), why (the failure
or error text, shortened), and what changed before the rerun. A first run that passes needs no
line. Write "Reruns: none" if there were none. The orchestrator copies the count and reasons to
`docs/orchestration-log.md`.

## Out of scope

Implementing the backends (M10), the installer, Lua file, README and CI (M11), Services,
Shortcuts.app, model changes.

## Hand-back

Commit on `task/M9-architecture-macos` (prefix `M9-architecture-macos:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Result file sections:
**Summary** of the design, **Deviations** from the proposal (with reasons), **Reruns**, **Open
points** for the user to decide before approval, and the final output of the three "Must pass"
commands.
