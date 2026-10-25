# M11-macos-install — result

## Summary

- `install.sh`: platform dispatch at the top (`LLMTR_UNAME` or `uname -s`): Darwin `exec`s
  `scripts/install-macos.sh "$@"`, Linux continues unchanged, anything else exits 1.
- `scripts/install-macos.sh` (new, bash 3.2 compatible, no sudo, idempotent, `--dry-run`,
  `--uninstall`): checks `uv` and `Hammerspoon.app` (clear `brew` hints), `uv tool install --force
  --reinstall`, writes `~/.hammerspoon/llmtr.lua` with the absolute `llmtr` path, ensures one
  `require("llmtr")` in `init.lua` (creates it, keeps other content), starts Hammerspoon (or says
  *Reload Config* if running), opens the Accessibility, Automation and Notifications panes and prints
  the steps. `--uninstall` removes the file, the line (the `init.lua` stays, even empty) and the uv tool.
- `macos/llmtr.lua.in` (new): architecture §16 (five release bindings, `hs.task` with
  `LLMTR_RUN_ID` + `LC_CTYPE=UTF-8`, `hs.urlevent` handler, withdrawal 8 s / 15 s after exit code 1).
- `README.md`: macOS section (requirements, install, the three permissions with the M8 names and
  dialog text, notifications and `notify.backend`, Karabiner rule and steps, troubleshooting).
  Linux sections unchanged apart from the intro and a pointer.
- `.github/workflows/ci.yml`: new `test-macos` job (`macos-latest`, Python 3.13 and 3.14,
  `uv sync --locked`, pytest, ruff check and format), same pinned SHAs, `persist-credentials: false`.
- `tests/test_install_macos.py` (new, 20 tests): all cases from the contract plus dry-run, running
  Hammerspoon, unknown option, Lua template checked as text.
- `tests/test_install.py`: added `uname` to `MINIMAL_TOOLS` (the dispatch needs it on the restricted PATH).

## Deviations

- `bash -n` for `scripts/install-macos.sh` is not added to the CI lint job (the contract allows only
  the `test-macos` job in `ci.yml`). Suggest the orchestrator adds it.
- `llmtr` is resolved from `uv tool dir --bin` (fallback `~/.local/bin`), not `command -v`, so a stale
  `llmtr` elsewhere on PATH is never written into the Lua file.
- The installer rejects an `llmtr` path containing `"` or `\` (it would break the Lua string).
- `hs.task` environment: the Lua file merges `LLMTR_RUN_ID` and `LC_CTYPE` into `task:environment()`
  and calls `setEnvironment`; whether this merges or replaces is the §22 open point, checked on the Mac.

## Reruns

Reruns: none. (One ruff F401 for an unused import in the new test file was fixed during
writing, before the first full "Must pass" run.)

## New dependencies

None.

## Open issues

- Nothing was run on a Mac: the Lua file, `open`, Settings URLs and Hammerspoon behaviour are untested.
- The Settings URLs (`x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility`,
  `…Privacy_Automation`, `com.apple.Notifications-Settings.extension`) are from memory; M12 must verify
  that each opens the right pane on macOS 27.

## Must pass (final run, after the last edit)

- `uv run pytest`: all passed (1 skipped: the Ollama test).
- `uv run ruff check .`: All checks passed!
- `uv run ruff format --check .`: 89 files already formatted
- `bash -n install.sh scripts/install-macos.sh scripts/install-ydotool.sh`: OK
- `uv tool run zizmor@1.31.1 --offline .github/`: No findings to report.
- YAML check with `uv tool run --from pyyaml`: ok

## Mac checklist for M12

1. `./install.sh --dry-run`, then `./install.sh` on a clean `~/.hammerspoon` and on an existing one:
   `llmtr.lua` has the real path, `init.lua` has `require("llmtr")` once (run it twice).
2. Do the three Settings panes open on macOS 27? Do the steps printed match the screens?
3. Reload Hammerspoon; press each of the five shortcuts (⌃⌥T/G/R, ⇧⌃⌥R/T); release binding works.
4. Without Accessibility: the message names Hammerspoon > Accessibility. Without Automation: the
   Automation message; the first-⌘C dialog text matches the README.
5. "Translating…" bubble appears, is replaced by the result/error, disappears after ~8 s (15 s on error).
   Check latency of the `hammerspoon://` channel; if slow, try `notify.backend = "osascript"`.
6. Polish text round trip (ąęłóżź) from a Hammerspoon-started run.
7. Second press cancels a long translate. Secure Input message in a password field.
8. `hs.task` environment: `LLMTR_RUN_ID` reaches `llmtr` and `HOME` is still set.
9. `./install.sh --uninstall`: file and line gone, `init.lua` and other config kept.
10. Optional: the Karabiner rule from the README.

## Fix round 1

Reviewer verdict: FIX (1 blocker, 1 major, 1 minor). All three fixed.

1. **blocker** `scripts/install-macos.sh` `write_module`: replaced `${content//@LLMTR_BIN@/"$bin"}`
   (bash ≤ 4.2 keeps the quotes, giving `""/path""` and a Lua syntax error) with
   `printf '%s%s%s\n' "${content%%@LLMTR_BIN@*}" "$bin" "${content#*@LLMTR_BIN@}"`. Also safe from
   bash ≥ 5.2's `patsub_replacement` (`&`). New test
   `test_install_writes_exact_path_with_space_and_ampersand`, parametrized over `BASH_COMPAT=31`,
   `BASH_COMPAT=42` and the default bash; the sandbox root is `…/Jan Kowalski & Co`, so the llmtr
   path contains a space and `&`, and the test asserts the exact line `local LLMTR = "<path>"`.
   Before the fix the 31 and 42 cases failed; after it all three pass.
2. **major** `macos/llmtr.lua.in`: the withdraw timer is now kept in `timers[id]` and released when
   it fires (`timers[id] = nil; withdraw(id)`), like `tasks` for `hs.task`. New text test
   `test_lua_template_keeps_withdraw_timers_referenced`.
3. **minor** `scripts/install-macos.sh` `remove_require`: now
   `grep -vxF … >"$HS_INIT.tmp" || true; cat "$HS_INIT.tmp" >"$HS_INIT"; rm -f "$HS_INIT.tmp"`,
   which keeps trailing blank lines byte for byte, writes through a symlink and still leaves an
   empty file. New tests `test_uninstall_keeps_trailing_blank_lines` (failed before the fix) and
   `test_uninstall_writes_through_symlinked_init_lua`; `test_uninstall_keeps_init_lua_even_if_empty`
   still passes.

Files changed: `scripts/install-macos.sh`, `macos/llmtr.lua.in`, `tests/test_install_macos.py`, this
file. All are on the contract's list.

Must pass (final run, after the last edit):

- `uv run pytest`: 346 passed, 1 skipped (the Ollama test).
- `uv run ruff check .`: All checks passed!
- `uv run ruff format --check .`: 90 files already formatted
- `bash -n install.sh scripts/install-macos.sh scripts/install-ydotool.sh`: OK
- `uv tool run zizmor@1.31.1 --offline .github/`: No findings to report.
- YAML check with `uv tool run --from pyyaml`: ok

Reruns this round: none. The only failing run was the planned one with the new tests against the old
script, to show they catch the bug. That was a check, not a rerun of a Must pass command.

Still not run on a Mac: real bash 3.2 and Hammerspoon behaviour are left for M12 (checklist item 1
and item 5 cover this).
