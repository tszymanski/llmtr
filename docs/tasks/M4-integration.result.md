# M4-integration — hand-back

## What was done

- **`src/llmtr/cli.py`**: implemented `main`, `run_shortcut` and the private `_run_tone_next`/
  `_run_stdin` helpers per `docs/architecture.md` sections 3.1–3.4, wiring the model side
  (`config`, `engine`, `ollama_client`) and the desktop side (`clipboard`, `keys`, `notify`,
  `lock`, `selection`) together. `build_parser` is untouched.
  - `main`: parses args (argparse `SystemExit` is converted into a plain return code rather than
    propagating, so it always *returns* an exit code as its docstring promises); rejects
    `tone --next --stdin` (exit 2); loads config (a `ConfigError` is notified via desktop
    notification and exits 1, per the architecture's "Common start" — this happens even for
    `--stdin` runs, since the doc places it before the `--stdin`/shortcut/`tone --next` branch);
    then dispatches to `tone --next` (state only, no lock), `--stdin` (engine only, errors to
    stderr), or `run_shortcut`.
  - `run_shortcut`: lock → (on contention) `cancel_running` + return 0 without starting a job →
    install the cancel handler → clipboard/keys → `capture_selection` → `plan_job` → progress
    notification (skipped when `notify.enabled` is false) → `run_job` → `save_last_result` →
    `deliver_result` → fallback-hint notification if not pasted. Any `LlmtrError` after the point
    a selection was actually captured restores the clipboard (errors raised *during* capture
    already restore it themselves, so `cli.py` doesn't double-restore); `Cancelled` gets normal
    urgency and exit 0, everything else critical urgency and exit 1 — matching the table in
    architecture section 7 exactly, including which rows get a progress notification first (it is
    only sent after `plan_job` succeeds, so `EmptySelection`/`KeySendError`-on-copy/`TextTooLong`
    never see one, but `OllamaUnavailable`/`ModelMissing`/`OllamaTimeout`/empty-output/`Cancelled`
    do).
  - Beyond the stub's documented parameters, `run_shortcut` takes keyword-only `clipboard`,
    `keys`, `client`, `lock` (explicitly invited by its docstring in the architecture) plus
    `sleep`/`monotonic` (forwarded to `capture_selection`/`deliver_result` so tests run instantly)
    and `kill` (forwarded to `cancel_running`, so a second-press test never signals a real
    process). `main`'s own signature is unchanged; its tests instead monkeypatch the module-level
    factories it calls (`make_clipboard`, `YdotoolKeySender`, `OllamaClient`,
    `NotifySendNotifier`) — see Deviations below.
- **`tests/test_cli.py`** (27 tests): `run_shortcut` exercised directly with fakes for every mode,
  `--quality`, explicit `--model`, the clipboard-only fallback, a paste-time `KeySendError`, the
  disabled-notification case, every error row in architecture section 7 reachable from the
  shortcut flow (Ollama down, model missing, timeout, empty selection, copy-time `KeySendError`,
  text too long, empty model output, no clipboard tool), the `Cancelled` restore path, and the
  second-press-cancels-first-without-starting-a-job path (using a real `RunLock` file and an
  injected `kill`, so no real signal is sent and no real second process is needed).
  `main` exercised end to end for `--stdin` (plain run, `--quality` model selection, an
  `EmptySelection` error to stderr), `tone --next` (single built-in preset and cycling between two
  configured presets, state persisted and re-read via `load_state`), `tone --next --stdin` and an
  unknown flag (both usage errors), a bad config file (notified, exit 1), and one full dispatch
  test of `main(["fix"])` with every factory monkeypatched.
- **`install.sh`** (repo root): idempotent, dry-run-capable, uninstallable, never calls `sudo`
  itself.
  - Checks `uv` (hard requirement, exits 1 if missing), `ollama`, `wl-copy`/`wl-paste` or `xclip`,
    `notify-send` (soft — prints a `note:` line to stderr and continues).
  - Installs with `uv tool install --force --reinstall "$SCRIPT_DIR"` (absolute path to the repo,
    so it works regardless of CWD) — never `pip`.
  - Checks `ydotool --version` ≥ 1 and a `systemctl --user is-enabled ydotoold.service`; if either
    is missing, either runs `scripts/install-ydotool.sh` (with `--with-ydotool`) or prints a note
    telling the user to run it themselves.
  - Registers four fixed, descriptively-named custom-keybinding dconf paths
    (`.../custom-keybindings/llmtr-{translate,fix,tone,tone-next}/`) rather than GNOME's usual
    auto-numbered `customN` slots. This makes idempotency simple and robust: re-running always
    writes to the *same* four paths (updating name/command/binding in place — "replacing only its
    own entries"), and the top-level `custom-keybindings` list is rebuilt as *other apps' existing
    paths* (anything not one of llmtr's four) *plus* llmtr's four, so nothing needs to be queried
    by name to detect "is this already one of mine" — path identity is enough. The installed
    `llmtr`'s absolute path is resolved via `command -v llmtr`, falling back to
    `uv tool dir --bin` and then `~/.local/bin`, and is embedded directly in each shortcut's
    `command` value (GNOME's shortcut-triggering environment may not have `~/.local/bin` on PATH).
  - `--uninstall`: rebuilds `custom-keybindings` without llmtr's four paths (preserving everything
    else), `gsettings reset-recursively`s each of llmtr's relocatable-schema instances, and runs
    `uv tool uninstall llmtr`. Does not touch config/state/cache or anything ydotool-related.
  - `--dry-run`: a `run()` helper prints (`+ cmd arg1 arg2 ...`, shell-quoted) instead of executing
    every *mutating* command (`gsettings set`/`reset-recursively`, `uv tool install/uninstall`,
    invoking `scripts/install-ydotool.sh`); read-only lookups (`gsettings get`, `command -v`,
    `uv tool dir --bin`, the ydotool/systemctl checks) still run for real, since dry-run needs
    their output to decide what to print. `resolve_llmtr_bin` relaxes its "must actually exist"
    check in dry-run mode, since a first-time dry run is printing what `uv tool install` *would*
    do, not something that already happened.
- **`tests/test_install.py`** (10 tests): `bash -n install.sh`; `--dry-run` prints the `uv tool
  install` and `gsettings set` commands while only read-only `gsettings get` calls actually reach
  the (fake) script; a real run against fake `uv`/`gsettings`/`llmtr` scripts on a temp `PATH`
  (logging argv, and for `gsettings`, keeping just enough `get`/`set` state to answer realistically)
  asserts the final `custom-keybindings` array contains a pre-existing "other app" path plus all
  four llmtr paths, each llmtr path's `name`/`command`/`binding` are set correctly with the fake
  `llmtr`'s absolute path, and `uv tool install --force --reinstall` (never `pip`) was called;
  re-running is idempotent (identical final array, no path duplicated); `--uninstall` removes only
  llmtr's four paths and calls `uv tool uninstall llmtr`, leaving the other app's shortcut and
  never mentioning config or ydotool; a missing-`uv` PATH fails fast with a clear stderr message;
  an unknown flag is a usage error (exit 2). No test calls a real `gsettings`, `uv tool install`,
  or `systemctl`.
- **`config.example.toml`** (repo root): every key from architecture section 4.1 with its default
  value and a one-line comment, the built-in `team` tone preset spelled out (plus a commented-out
  second preset and a commented-out `[[keys.override]]` example). Verified it parses byte-for-byte
  into the same `Config()` as the dataclass defaults via `llmtr.config.parse_config`.
- **`README.md`** (repo root, previously empty): what llmtr does and its shortcut table, install
  steps (`scripts/install-ydotool.sh` then `./install.sh`, plus `--with-ydotool`/`--dry-run`/
  `--uninstall`), requirements, config pointer, `--stdin` usage examples, a troubleshooting section
  (ydotoold socket, Ollama not running, model not pulled, fallback-is-not-an-error, shortcuts not
  registered), and uninstall.

## Checks

```
uv run pytest                -> 238 passed, 1 skipped (the ollama-marked test from M2)
uv run ruff check .          -> All checks passed!
uv run ruff format --check . -> 43 files already formatted
bash -n install.sh           -> OK (no output)
```

(201 pre-existing M0–M3 tests + 27 new in `tests/test_cli.py` + 10 new in `tests/test_install.py`
= 238; the skip is M2's `@pytest.mark.ollama` real-model test, unaffected by this task and already
documented as blocked by the sandbox's network policy.)

## Deviations from the architecture

- `main`'s signature (`main(argv: Sequence[str] | None = None) -> int`) and `build_parser` are
  unchanged. Architecture section 8's M4 bullet says tests exercise `main()` "end to end with all
  fakes injected... through `run_shortcut`'s keyword-only parameters" — taken together with
  `run_shortcut`'s own docstring (which explicitly invites exactly those parameters), I read this
  as: give `run_shortcut` the injection points (done), and reach `main()`'s dispatch logic in
  tests either by calling `run_shortcut` directly for the shortcut-flow-heavy cases, or by calling
  `main()` with the module-level factories (`make_clipboard`, `YdotoolKeySender`, `OllamaClient`,
  `NotifySendNotifier`) monkeypatched for the thinner dispatch/CLI-level cases (`--stdin`,
  `tone --next`, usage/config errors, one full `main(["fix"])` round trip). I did not add
  injection kwargs to `main` itself, since neither the stub nor its docstring invited that and
  monkeypatching the factories it calls gives equivalent coverage without changing a signature
  that wasn't explicitly marked as mine to extend. Flagging this reading in case the orchestrator
  intended something more literal.
- `run_shortcut` also gained a `kill` keyword-only parameter (forwarded to `lock.cancel_running`),
  not listed among the architecture's example names (`clipboard`, `keys`, `client`, `lock`). It
  was necessary to test the second-press-cancels-first path without sending a real `SIGTERM` to
  the test process itself (the only alternative was multi-process orchestration, which the
  architecture's own M3 test strategy avoids for the same handler). `cancel_running` already took
  an injectable `kill` for exactly this reason; `run_shortcut` just had to pass it through.
- `install.sh` uses four fixed, descriptively-named dconf paths for its shortcuts
  (`.../llmtr-translate/` etc.) instead of GNOME's usual auto-incrementing `customN` convention.
  The architecture/task contract don't specify a naming scheme, only the behavior ("appending...,
  replacing only its own entries on re-run"); fixed paths make that behavior simple and exactly
  correct without needing to query each existing entry's `name` property to recognize "this is
  mine" on re-run. GNOME's Settings UI and `gsettings`/dconf don't care about the path's spelling,
  only that it's a valid, unique dconf path, so this is not expected to behave differently from
  `customN` in practice.

## Bugs found in M2/M3 modules

None. `plan_job`/`run_job`/`capture_selection`/`deliver_result`/`restore_clipboard`/`RunLock`/
`cancel_running`/`install_cancel_handler`/`resolve_key_pair`/`focused_app_id` all matched their
documented signatures and behavior exactly; wiring them together in `cli.py` needed no workarounds
beyond the ones already described above as deviations in `cli.py` itself.

## Manual host checklist for the orchestrator

None of this can run in this sandbox (no desktop, no Wayland, no real `ydotoold`/`gsettings`/
`notify-send`, no Ollama reachable). On the host, after `./scripts/install-ydotool.sh` (or
`./install.sh --with-ydotool`) and `./install.sh`:

1. **gedit**: open it, select some Polish text, press `Super+Alt+T`. Confirm a "Translating PL →
   EN…" notification appears, the selection is replaced with an English translation after a few
   seconds, and the clipboard afterward holds whatever it held *before* the shortcut (not the
   translated text) — paste with a manual Ctrl+V somewhere else to check.
2. **Firefox**: same translate/fix/tone flow in a text field (URL bar or a web form). Confirms the
   `ydotool`-sent Ctrl+C/Ctrl+V land correctly in a browser's own clipboard handling, and that the
   explicit Super/Alt key-up events `keys.py` sends don't cause Firefox to see a
   Ctrl+Super+Alt-modified keystroke instead of plain Ctrl+C/V.
3. **Cancel**: select a long paragraph, press `Super+Alt+T` (or `--quality` via a custom binding
   if you add one temporarily), then press the same shortcut again within a couple of seconds.
   Confirm: no second translation starts, the first one's clipboard is restored to what it was
   before the shortcut, and a "Cancelled." notification appears (not an error-looking one).
4. **Tone cycling**: press `Super+Alt+R` on some text (uses the current tone, "team" by default),
   then `Shift+Super+Alt+R` (should notify "Tone: team (only preset)" unless you've added a second
   preset in `config.toml`, in which case it should name the next one and no text should be
   touched), then `Super+Alt+R` again and confirm the rewrite now uses the *new* tone's voice.
5. **Fallback without ydotoold**: stop the daemon (`systemctl --user stop ydotoold.service`),
   manually copy some text (Ctrl+C by hand), press `Super+Alt+G`. Confirm: no keystrokes are sent
   (nothing visibly happens to the selection), a notification says "Fixing grammar…" then "Result
   copied. Press Ctrl+V to paste.", and a manual Ctrl+V pastes the fixed text. Restart the daemon
   afterward and confirm the automatic flow resumes working.
6. **`install.sh` itself**: run `./install.sh` a second time and confirm GNOME Settings → Keyboard
   → Custom Shortcuts still shows exactly four `llmtr ...` entries (not eight); run
   `./install.sh --uninstall` and confirm those four disappear while any other custom shortcut you
   had stays, and `uv tool list` no longer shows `llmtr`.

## Open issues

- None beyond the two already-flagged items from M2 (`strip_preamble`'s judgment calls on
  fence/quote unwrapping — worth revisiting once M5 sees real model output shapes) and M3
  (`focused_app_id`'s `gdbus` output parsing was only exercised against hand-built fixtures; worth
  a sanity check against real `gdbus call` output on the host, item 4 in M3's own checklist above
  covers this in practice once `install.sh`/`cli.py` are wired up).
- `install.sh`'s ydotool-version check parses the first `X.Y[.Z]`-shaped token out of
  `ydotool --version`'s combined stdout+stderr; I haven't been able to verify this against the
  real `ReimuNotMoe/ydotool` 1.0.4 binary's actual `--version` output format in this sandbox (no
  `ydotool` binary here). Worth a quick check on the host; if the real output doesn't contain a
  bare `X.Y` version number, this check will treat ydotool as not-ready even when it is (falling
  back to the clipboard-only mode, which is a safe default, not a hard failure).

## Fix round 1

Addressed four review findings (the ydotool one is exactly what the "Open issues" note above
flagged as unverified — confirmed wrong on the real host):

- **A (major, orchestrator, real host)**: `ydotool_ready` in `install.sh` called `ydotool
  --version`, but real ydotool 1.0.4 has no `--version`/`-V` of its own (it prints "Unknown
  command" and exits non-zero); only the daemon reports a version, via `ydotoold -V` ->
  `v1.0.4-0-g57ba7d0`. This made `install.sh` warn that ydotool wasn't set up even when it was.
  Fixed `ydotool_ready` to require `ydotoold` on PATH (Ubuntu's old 0.1.8 package ships no
  `ydotoold` at all, so this also correctly rejects that package) and parse the leading `v<major>`
  from `ydotoold -V`.
- **B (major, reviewer)**: `main()` always sent a `ConfigError` to a desktop notification, even
  under `--stdin`, contradicting architecture §2's "`--stdin`: no lock, clipboard, keys or
  notifications; errors go to stderr". Fixed: with `--stdin`, the config error is printed to
  stderr and no `NotifySendNotifier` is constructed; without `--stdin`, behavior is unchanged.
  Added `test_main_stdin_bad_config_prints_to_stderr_not_notification` to `tests/test_cli.py`.
- **C (major, reviewer)**: `tests/test_install.py` had no fakes for `ydotool`/`ydotoold`/
  `systemctl`, so `ydotool_ready`/`check_ydotool` were untested. Added `YDOTOOL_FAKE` (logs argv),
  `YDOTOOLD_FAKE` (answers `-V` with `$FAKE_YDOTOOLD_VERSION`, default `v1.0.4-0-g57ba7d0`) and
  `SYSTEMCTL_FAKE` (answers `is-active ydotoold.service` from `$FAKE_YDOTOOLD_ACTIVE`, default
  active) to the `fake_bin` fixture, which now defaults to a "ydotool 1.x, daemon active" setup.
  Added five tests: ydotool missing, old ydotool without `ydotoold` (0.1.x shape), 1.x with the
  service active (no warning), 1.x with the service inactive (warning), and `--with-ydotool
  --dry-run` runs `scripts/install-ydotool.sh` (printed, never executed for real).
- **D (minor, reviewer)**: `ydotool_ready` used `systemctl --user is-enabled`, which is true for an
  enabled-but-stopped service. Switched to `is-active`, with a fallback check for
  `$XDG_RUNTIME_DIR/.ydotool_socket` existing (covers setups without systemd user units).

## Checks (fix round 1)

```
uv run pytest                -> 244 passed, 1 skipped (same pre-existing ollama-marked skip)
uv run ruff check .          -> All checks passed!
uv run ruff format --check . -> 44 files already formatted
bash -n install.sh           -> OK (no output)
```

(238 from the original hand-back + 1 new `test_cli.py` test (B) + 5 new `test_install.py` tests
(C) = 244; no tests were removed.)

## Fix round 2

Addressed one review finding (major, orchestrator, real host):

- **`tests/test_install.py` was not hermetic**: `_run()` built each subprocess's PATH as
  `fake_bin` followed by the *inherited* PATH (the test process's own `os.environ["PATH"]`).
  Deleting a fake binary from `fake_bin` to simulate "tool X is missing" therefore only meant X
  was missing from that one directory — if a real X also lived somewhere else on the inherited
  PATH (as real `ydotool`/`ydotoold` 1.0.4 do, in `/usr/local/bin` on the target Ubuntu desktop),
  install.sh found that real one instead and behaved as if the tool *were* present. This made
  `test_ydotool_missing_warns`, `test_old_ydotool_without_ydotoold_warns`, and
  `test_with_ydotool_flag_runs_install_ydotool_script` pass in the sandbox (no real ydotool
  there) but fail on the host.
  - Added a `_minimal_tool_paths` session fixture that resolves the handful of real coreutils
    install.sh's own code and the fake scripts need (`bash`, `grep`, `sed`, `tr`, `head`, `tail`,
    `dirname`, `mv`, `touch`) via `shutil.which` once, and symlinks them into every `fake_bin`
    directory.
  - `fake_bin` now populates those symlinks alongside its existing fake
    `uv`/`llmtr`/`gsettings`/`ydotool`/`ydotoold`/`systemctl` scripts.
  - `_run()` now sets `env["PATH"] = str(fake_bin)` only — never the inherited PATH — so deleting
    a binary from `fake_bin` means install.sh truly cannot find it anywhere, and no real
    `uv`/`llmtr`/`gsettings`/`systemctl`/`ydotool`/`ydotoold`/`notify-send`/`wl-copy`/`wl-paste`/
    `ollama` on the host (or sandbox) running the tests can ever be reached.
  - Rewrote `test_install_missing_uv_fails_fast` to use the (now hermetic) `fake_bin` fixture and
    just `unlink()` its fake `uv`, matching the pattern of the other "missing tool" tests, instead
    of hand-subtracting `uv`'s directory from the inherited PATH.
  - Added `test_path_does_not_leak_host_directories`: puts a decoy `ydotool`/`ydotoold` (printing
    `v1.0.4`, like the real binary) in a directory prepended to the *ambient* PATH via
    `monkeypatch.setenv`, deletes both from `fake_bin`, and asserts install.sh still reports
    ydotool as not set up — proving the decoy, and the ambient PATH generally, is unreachable.
    Verified this test actually catches the original bug: temporarily reverting `_run()` to
    append the inherited PATH made this new test fail with the decoy's `v1.0.4` being picked up
    (ydotool "ready" instead of "not set up"); restoring the fix made it pass again.

### Checks (fix round 2)

```
uv run pytest                -> 245 passed, 1 skipped (same pre-existing ollama-marked skip)
uv run ruff check .          -> All checks passed!
uv run ruff format --check . -> 44 files already formatted
bash -n install.sh           -> OK (no output)
```

(244 from fix round 1 + 1 new `test_install.py` test
(`test_path_does_not_leak_host_directories`) = 245; no tests were removed, and
`test_install_missing_uv_fails_fast` was rewritten in place rather than added/removed.)
