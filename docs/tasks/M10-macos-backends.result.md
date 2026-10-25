# M10-macos-backends — result

## Summary

Every `NotImplementedError` from M9 is replaced (`grep -rn NotImplementedError src/` is empty) and
`cli.py` is wired to the platform layer. Linux behaviour and messages are unchanged.

- `platforms.py` (`detect_platform`, `key_defaults`), `macos_exec.py` (`child_env`: `LC_CTYPE=UTF-8`
  always, `LC_ALL` removed, input never mutated), `macos_clipboard.py` (`PbClipboard`),
  `macos_keys.py` (combo parser, AppleScript builder, error classification, `OsascriptKeySender`),
  `macos_notify.py` (`build_notify_url`, `HammerspoonNotifier`, `OsascriptNotifier`, both never
  raise), `macos_probes.py` (`focused_bundle_id`, `parse_secure_input_pid`, `secure_input_app`),
  `backends.py` (`make_notifier`, `make_desktop`). Every tool is called by absolute path.
- `config.py`: `parse_config`/`load_config` take `platform=` (default `"linux"`); macOS key defaults
  apply only to keys the user did not set; `notify.backend` is parsed and validated against the new
  `NOTIFY_BACKENDS`. Dataclass defaults unchanged.
- `cli.py`: `main` uses `detect_platform()`, passes `platform=` to `load_config`, builds notifier
  and `Desktop`; `run_shortcut` has `desktop=`, uses `desktop.focused_app_id()`,
  `desktop.paste_hint`, and after a plain "nothing copied" (clipboard already restored) asks
  `desktop.empty_selection_hint()` and reports `SecureInputActive(app)`. A failing probe keeps the
  plain message. The `clipboard=`/`keys=` overrides still win over the bundle.
- `errors.py`: optional `message` for `ClipboardUnavailable`, optional `empty_clipboard_message`
  for `EmptySelection(False)`; defaults unchanged. `PbClipboard` uses "No working clipboard tool.".
- `fakes.py`: `FakeRunner` (+ `RunnerCall`), checked in `tests/test_interfaces.py`.
- `config.example.toml`: `notify.backend`, comment on the macOS key defaults.
- Tests: new `test_platforms.py`, `test_macos_exec.py`, `test_macos_clipboard.py`,
  `test_macos_keys.py`, `test_macos_notify.py`, `test_macos_probes.py`, `test_backends.py`;
  additive cases in `test_config.py`, `test_cli.py`, `test_lock.py`, `test_interfaces.py`. They cover
  everything listed in the contract (locale with an empty env, absolute paths, 1002 / −1743 /
  timeout, URL encoding, `notify.backend`, macOS lock path, macOS key defaults vs explicit keys).
  No test starts a real `osascript`, `pbcopy`, `pbpaste`, `open`, `ioreg` or `ps`. No existing
  test line was changed (the diff of `tests/` has only added lines).

## Deviations

- **Linux wiring stays visible in `cli.py`.** The existing v1 tests patch `cli.NotifySendNotifier`,
  `cli.make_clipboard` and `cli.YdotoolKeySender`, and "Done when" 3 forbids editing them. So
  `cli._make_notifier` / `cli._make_desktop` build the Linux objects from the names imported in
  `cli.py` and delegate only macOS to `backends.make_notifier` / `make_desktop`. The Linux branches of
  `backends` are implemented and tested, but `cli` does not call them. If you want `cli.py` to
  go through `backends` for Linux as well (architecture 12), those v1 tests must be changed to patch
  `backends`; that is a decision for you.
- **`test_cli.py` gets an autouse fixture** that forces `cli.detect_platform` to `"linux"`, so the
  v1 tests that go through `main()` also pass on the macOS CI runner (without it `main` would pick
  the macOS backends there). The new macOS tests re-patch it.
- `NOTIFY_BACKENDS` constant added to `config.py` (and `__all__`); `Desktop` default
  `empty_selection_hint` on Linux is a private `_no_app` helper.
- `PbClipboard`, `OsascriptKeySender` and the notifiers pass `child_env()` / the constructor env to
  the runner; `OsascriptKeySender` has no `env` argument (as in the M9 stub), so it uses `os.environ`.

## Reruns

Counted strictly, I fixed and re-ran failing "Must pass" commands during development before the
first clean full run. I record them so you can judge against the limit of 3:

1. `ruff check .` — E501 in the `run_shortcut` docstring; reflowed it.
2. `ruff check .` — E501 again (my first reflow joined two lines); rewrote the paragraph.
3. `uv run pytest` — 16 v1 `test_cli.py` tests failed with `cli has no attribute
   NotifySendNotifier/make_clipboard` after I removed the imports; restored them in `cli.py` and
   added `_make_notifier`/`_make_desktop` (see Deviations).
4. `ruff check .` — I001 import order in `cli.py`; `ruff check --fix`.
5. `ruff check .` — E501 in the new `tests/test_backends.py`; split the assert.

I consider 1–5 normal fix-after-edit iterations (each followed an intended code change, none
needed a design change), but strictly counted this is above 3. No session restart. The final run
below is clean.

## New dependencies

None.

## Open issues

- See the first two Deviations (Linux wiring in `cli.py`; autouse platform fixture).
- Not run on a real Mac: the `osascript`/`open`/`ioreg` command lines are checked against the M8
  spike scripts and with fakes only (M12 does the real check).
- `OsascriptKeySender.send` uses `child_env()` from `os.environ`; Hammerspoon children have a
  minimal environment, which is fine because the call uses absolute paths.

## Must-pass output (final run)

```
........................................................................ [ 97%]
.............                                                            [100%]
444 passed, 1 skipped in 10.25s
All checks passed!
96 files already formatted
```
