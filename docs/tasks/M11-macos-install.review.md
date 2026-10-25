VERDICT: FIX

1. **blocker**, `scripts/install-macos.sh:113`. **Problem:** the line `printf '%s\n' "${content//@LLMTR_BIN@/"$bin"}"` writes literal quotes into the file under macOS's `/bin/bash` 3.2. Bash 4.2 and older don't strip the quotes inside the replacement string, and the script runs on 3.2 (`#!/usr/bin/env bash`, and its header says "Written for macOS's bash 3.2"). The installed `llmtr.lua` then contains `local LLMTR = ""/Users/x/.local/bin/llmtr""`, which is a Lua syntax error, so `require("llmtr")` fails and none of the five shortcuts work. I reproduced it with `BASH_COMPAT=31 bash` and `BASH_COMPAT=42 bash`; bash 5.3 gives the correct output, which is why the tests pass on Linux. **Fix:** don't use pattern substitution. The placeholder occurs exactly once (the existing test asserts that), so build the file from the parts before and after it: `printf '%s%s%s\n' "${content%%@LLMTR_BIN@*}" "$bin" "${content#*@LLMTR_BIN@}" >"$HS_MODULE"`. This also avoids bash ≥5.2's `patsub_replacement` problem: an unquoted `&` in the replacement would be replaced by the matched text. Then add a test in `tests/test_install_macos.py` that runs the installer with `BASH_COMPAT=3.2` (or 31) and a `HOME` whose path contains a space and a `&`. It should assert that the line `local LLMTR = "<path>"` is exact.

2. **major**, `macos/llmtr.lua.in:38`. **Problem:** the result of `hs.timer.doAfter(delay, …)` isn't kept anywhere. In Hammerspoon, a timer userdata with no reference can be garbage-collected, and its `__gc` stops the timer. If that happens in the 8 s or 15 s window, the run's last bubble is never withdrawn. That breaks the withdrawal behaviour §16 requires, and it would fail only sometimes, so the M12 check on the Mac might miss it. **Fix:** keep the timer in a table and release it when it fires, e.g. `timers[id] = hs.timer.doAfter(delay, function() timers[id] = nil; withdraw(id) end)`, the same way `tasks` keeps the `hs.task` objects alive.

3. **minor**, `scripts/install-macos.sh:173-175`. **Problem:** `--uninstall` reads the remaining lines through `$(…)`, which drops all trailing newlines. If the user's `init.lua` ended in blank lines, those are lost: a small change to the user's file beyond removing llmtr's line. **Fix:** `grep -vxF "$REQUIRE_LINE" "$HS_INIT" >"$HS_INIT.tmp" || true`, then `cat "$HS_INIT.tmp" >"$HS_INIT"; rm -f "$HS_INIT.tmp"`. This keeps the content byte-for-byte, still writes through a symlink, and still leaves an empty file.

Checked and fine:
- `install.sh` changes only the dispatch at the top; the Linux part is untouched.
- `uname` was added to the minimal tool list in `tests/test_install.py`.
- `install-macos.sh` is user-level with no `sudo`, and the require line is added idempotently.
- `--dry-run` changes nothing; it only runs the read-only `uv tool dir` and `pgrep`.
- `--uninstall` removes only llmtr's file and line.
- Paths with spaces are quoted throughout.
- The Lua file matches §16: release bindings, `LLMTR_RUN_ID` and `LC_CTYPE`, and the `hs.urlevent` handler.
- The README's permission names, dialog text and the five Karabiner steps match M8 and the proposal.
- `ci.yml` adds only `test-macos`, with the same pinned SHAs and `persist-credentials: false`.
- The tests use only fakes.
- `uv run pytest`, `ruff check`, `ruff format --check` and `bash -n` all pass. I did not run zizmor.
