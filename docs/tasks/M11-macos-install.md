# Task M11-macos-install — macOS installer, Hammerspoon file, README, CI

Role: **Integration worker**. Sandbox, clone mode. Branch: `task/M11-macos-install`.
Runs **in parallel with M10** (backends); the file lists do not overlap.
Read `CLAUDE.md`, `docs/proposal.md` ("macOS support (v2)", incl. Permissions and Karabiner setup),
`docs/architecture.md` (v2 part, §11–22, binding; mainly §16, §17, §19, §21) and
`docs/tasks/M8-spike.result.md` (exact dialog texts and Settings names).

## Goal

A macOS user runs `./install.sh` and gets the five Hammerspoon shortcuts, the permission steps and
docs; Linux install is unchanged; CI also runs the tests on macOS. The real install on the Mac is
checked later (M12) — here everything is tested with fakes on Linux.

## Change

Exactly the M11 list in `docs/architecture.md` §21:

- `install.sh`: only the dispatch at the top (§17), with `LLMTR_UNAME` to force the branch in tests.
  The Linux part below it is unchanged. The existing `tests/test_install.py` restricts `PATH`:
  make sure `uname` is still reachable there (or the tests set `LLMTR_UNAME=Linux`).
- `scripts/install-macos.sh` (new): steps 1–7 of §17, user-level, no `sudo`, idempotent,
  `--dry-run` and `--uninstall` as on Linux.
- `macos/llmtr.lua.in` (new): exactly §16 (release bindings, `hs.task` with `@LLMTR_BIN@`,
  `LLMTR_RUN_ID` + `LC_CTYPE=UTF-8`, `hs.urlevent` handler, 8 s / 15 s withdrawal — user approved).
- `README.md`: macOS section per §21: requirements, install, the three permissions with the exact
  names and dialog text from M8 (macOS 27 calls Accessibility "Device Control and Data Access"),
  notifications and `notify.backend`, the optional Caps Lock setup via Karabiner (rule + the five
  setup steps from the proposal), troubleshooting (`llmtr log`, Secure Input, locale). Keep the
  Linux sections as they are; the intro may say "GNOME/Wayland and macOS".
- `.github/workflows/ci.yml`: a `test-macos` job on `macos-latest` (`uv sync --locked`, pytest,
  ruff), Python 3.13 and 3.14. Copy the existing jobs' pattern: actions **pinned by the same commit
  SHAs** with the tag comment, `persist-credentials: false`. zizmor must stay at 0 findings.
- `tests/test_install_macos.py` (new): runs `scripts/install-macos.sh` against a temp `HOME` with
  fake `uv`, `open` and an `Applications/Hammerspoon.app` dir on a restricted `PATH`: writes
  `llmtr.lua` with the absolute path substituted; adds `require("llmtr")` exactly once over two
  runs; keeps existing `init.lua` content; creates `init.lua` if missing; `--uninstall` removes
  only llmtr's line and file; missing `uv` / Hammerspoon → clear message and non-zero exit;
  `install.sh` with `LLMTR_UNAME=Darwin` reaches the macOS script. Never call the real `open`,
  `uv tool install` or Hammerspoon.

## Files you may change

Only the M11 list in `docs/architecture.md` §21 (`install.sh`, `scripts/install-macos.sh`,
`macos/llmtr.lua.in`, `README.md`, `.github/workflows/ci.yml`, `tests/test_install_macos.py`, and
`tests/test_install.py` only if the dispatch needs it), plus
`docs/tasks/M11-macos-install.result.md`. Nothing in `src/llmtr/`, other tests,
`config.example.toml`, `docs/architecture.md`, `docs/proposal.md`.

## Must pass

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`
- `bash -n install.sh scripts/install-macos.sh scripts/install-ydotool.sh`
- `uv tool run zizmor@1.31.1 --offline .github/` → no findings (the sandbox cannot reach GitHub;
  `uvx` may be missing, `uv tool run` is the same).
- YAML check: `uv tool run --from pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- If a tool cannot be downloaded in the sandbox, say so in the result file; the orchestrator runs
  it on the host.

## Done when

All of these hold; stop as soon as they do, and do not start M10 work:

1. Every file under "Change" exists and does what its bullet says; the Lua file matches §16.
2. Every case listed for `tests/test_install_macos.py` exists and passes; `tests/test_install.py`
   still passes (Linux install unchanged).
3. The `ci.yml` change adds only the `test-macos` job, with pinned SHAs, and zizmor reports 0.
4. All "Must pass" commands exit 0 in a final run after the last edit.
5. The result file is written (sections below) and everything is committed on
   `task/M11-macos-install`; `git status` is clean.

If a condition cannot be met (the architecture is wrong, or the rerun limit is hit), stop, explain
it in the result file under "Open issues", commit what is done, and finish.

## Reruns

You may fix and rerun a failing "Must pass" command **at most 3 times**; restart or `--continue`
the session **at most once**. Rerunning after an intended code change is normal work, not a
rerun. Record every rerun in the result file under **"Reruns"**, one line each: what was rerun, why
(shortened error text), what changed. Write "Reruns: none" if there were none. At the limit: stop
as described under "Done when".

## Out of scope

Python code in `src/llmtr/` (M10), the real install on the Mac (M12), Karabiner automation,
Services, Shortcuts.app.

## Hand-back

Commit on `task/M11-macos-install` (prefix `M11-macos-install:`; end each message with a
`Co-Authored-By` line naming the model you actually run as). Do not push. Result file sections:
**Summary**, **Deviations**, **Reruns**, **New dependencies** (expected: none), **Open issues**, the
final output of the "Must pass" commands, and a short **Mac checklist for M12** (what the user
should try after a real install).
