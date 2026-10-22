# M3-fix2 result — wl-copy / xclip must not block llmtr

## What was done

`clipboard.py`: `_run` gained a `detached: bool = False` keyword. `WlClipboard.set_text` and
`XclipClipboard.set_text` now call it with `detached=True`: `stdout=subprocess.DEVNULL`, stderr to
a `tempfile.TemporaryFile()` read back only on a non-zero exit, instead of `capture_output=True`.
A forked background server (`wl-copy`'s clipboard-serving child, `xclip`'s equivalent) inherits
these descriptors; since neither is a pipe, our wait for the foreground process no longer blocks
on the child keeping them open. `get_text` and `clear` (including `WlClipboard.clear`, which does
not go through `set_text`) are unchanged — only `set_text` forks a server.

The existing argv-assertion tests (`subprocess.run` monkeypatched) needed no changes: they only
assert `argv`/`input`, which are unaffected by the extra `stdout`/`stderr` kwargs.

## Regression tests (`tests/test_clipboard.py`)

Added a `fake_clipboard_path` fixture that writes fake `wl-copy`/`xclip` shell scripts to a temp
dir, puts that dir first on `PATH` (hermetic: that dir plus the dirs providing `sh`/`sleep`/`cat`),
and kills any background sleepers (PIDs recorded by the script) in teardown. The fake script reads
stdin to a file, then — unless told to fail via `LLMTR_TEST_EXIT` — forks `( sleep 30 ) &`
inheriting stdout/stderr, and exits 0.

Four new tests: `set_text` for both backends returns in well under 1 s (vs. the old
`SUBPROCESS_TIMEOUT = 2.0 s` hang) and the fake tool's file holds the written text; and for both
backends, a fake exiting 1 with a stderr message raises `ClipboardUnavailable` with that message in
`.detail`.

Verified these two timing tests fail (`TimeoutExpired` → `ClipboardUnavailable`) against the
pre-fix `_run`, confirming they reproduce the reported bug.

## Checks

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all pass.

## Deviations / new dependencies

None. No files touched beyond the three listed in the contract.

## Open issues

None.
