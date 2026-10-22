# M3-desktop — hand-back

## What was done

Implemented the five desktop-side modules against the stubs in `docs/architecture.md` (sections
2, 3, 4.1 `[keys]`, 7), replacing every `NotImplementedError`:

- **`clipboard.py`**: `WlClipboard` (`wl-paste --no-newline --type text` / `wl-copy` /
  `wl-copy --clear`), `XclipClipboard` (`xclip -selection clipboard [-o]`), `make_clipboard`
  (Wayland tools preferred when `WAYLAND_DISPLAY` is set and both are on PATH, else `xclip`,
  else `ClipboardUnavailable`). Non-zero `wl-paste` with "No selection"/"No suitable type" in
  stderr maps to `""`; `xclip` maps any non-zero exit to `""` (no owner holds the selection).
  Subprocess hangs/missing binaries raise `ClipboardUnavailable`.
- **`keys.py`**: `parse_combo` with a full QWERTY-row keycode table (letters are *not*
  alphabetically contiguous in `linux/input-event-codes.h`, e.g. `KEY_A=30` but `KEY_C=46`, so
  the table is spelled out rather than computed); `YdotoolKeySender` (`available()` checks the
  binary and the resolved socket path; `send()` shells out to `ydotool key`); `focused_app_id`
  via the Window Calls extension `gdbus` call, tolerant of the tuple/quoting `gdbus` wraps its
  JSON output in; `resolve_key_pair` as a pure case-insensitive lookup.
- **`notify.py`**: `NotifySendNotifier` chains `--print-id`/`--replace-id` across calls so one
  run shows one bubble, falls back to a plain `notify-send` call if those flags are rejected,
  and swallows every failure (printed to stderr) so a broken notifier can never break a job.
- **`lock.py`**: `RunLock` on `fcntl.flock(LOCK_EX | LOCK_NB)`, PID written into the file;
  `default_lock_path` prefers `$XDG_RUNTIME_DIR`, falls back to `$XDG_CACHE_HOME`;
  `cancel_running` signals the holder PID via an injectable `kill`; `install_cancel_handler`
  installs a `SIGTERM` -> `Cancelled` handler.
- **`selection.py`**: `capture_selection` (keystroke path with save/clear/send/poll-with-timeout,
  fallback path reading the existing clipboard), `deliver_result` (paste-and-restore, or leave on
  clipboard for the fallback/`KeySendError` case), `restore_clipboard` (never raises).

**Addition beyond the stub** (architecture section 10, "may add explicit modifier key-up events
in `YdotoolKeySender.send`"): `send()` now always prefixes the `ydotool key` argv with `125:0
56:0` (Super, Alt release) before the combo's own press/release events. This is a small,
testable change — releasing a key that isn't actually down is a no-op for `ydotool`/the kernel —
and guards against GNOME still considering the triggering shortcut's Super+Alt held when the
copy/paste combo is sent a few hundred ms later. See `keys.RELEASE_SUPER_ALT` and
`test_ydotool_send_releases_super_and_alt_first`.

## Tests and checks

New tests: `tests/test_clipboard.py` (16), `tests/test_keys.py` (26), `tests/test_notify.py` (7),
`tests/test_lock.py` (14), `tests/test_selection.py` (13) — 76 new tests, all built on
`FakeClipboard`/`FakeKeySender`/`FakeClock` from `llmtr.fakes` or on a monkeypatched
`subprocess.run`/`shutil.which` with exact-argv assertions. No test starts a real desktop tool or
signals a real other process (`cancel_running` takes an injected `kill`; the SIGTERM-handler test
signals its own PID).

```
uv run pytest                 -> 97 passed (21 pre-existing M0/M1 + 76 new)
uv run ruff check .           -> All checks passed!
uv run ruff format --check .  -> 31 files already formatted
```

`tests/test_interfaces.py` and `tests/test_smoke.py` (21 tests total) were already green and
untouched.

## Deviations from the architecture

None in the five owned modules' public signatures. The one addition (explicit Super/Alt release
in `YdotoolKeySender.send`) was explicitly invited by architecture section 10 as something M3
"may add if it is a small, testable change" — done, noted above, not a deviation.

`keys.py` exposes one extra name not listed in the architecture's public-name table: `KEY_CODES`
(the letter/digit/function-key keycode table, parallel to the already-specified
`MODIFIER_KEYCODES`). It is additive to `__all__`, does not change any existing name, and
`tests/test_interfaces.py`'s subset check still passes.

## Manual host checks for the orchestrator

These cannot run in this sandbox (no desktop, no Wayland, no `ydotoold`, no `notify-send`). On
the host, with `ydotoold` running and the udev rule in place (M4):

1. **gedit**: select text, trigger the configured shortcut's equivalent of the copy/paste flow
   (once `cli.py`/M4 wires it up) — confirm the selection is replaced and the original clipboard
   contents are restored afterwards.
2. **Firefox**: same, in a text field (e.g. the URL bar or a web form) — confirm it works with a
   browser's own clipboard handling, and that Ctrl+C/Ctrl+V sent via `ydotool` land correctly
   while the physical Super+Alt shortcut keys are still being released.
3. **No ydotoold / ydotool missing**: confirm the fallback path — `make_clipboard` +
   `capture_selection` read whatever the user already copied by hand, and after processing the
   result stays on the clipboard with a "Press Ctrl+V to paste" notification (M4 wires the
   notification text; M3 only guarantees `deliver_result` returns `False` in that case).
4. **Window Calls extension present/absent**: with the extension installed, confirm
   `focused_app_id()` returns the right `wm_class` for a terminal vs. a browser so
   `resolve_key_pair` picks up `[[keys.override]]`; without it, confirm it returns `None` quickly
   (no hang) and the default key pair is used.
5. **Second-press cancel**: start a (slow) job, press the shortcut again, confirm the first
   process receives `SIGTERM`, restores the clipboard, and the second process exits 0 without
   starting its own job (this exercises `lock.py` end-to-end; wiring is M4's `run_shortcut`).
6. **notify-send bubble replacement**: confirm "Translating…" is replaced in place by the
   final result/error bubble rather than stacking a second notification (depends on the host's
   notification daemon supporting `--print-id`/`--replace-id`; `NotifySendNotifier` falls back to
   a plain call if not, which will show two bubbles instead of replacing one — acceptable
   degradation, not a bug).

## Open issues

- `focused_app_id()`'s `gdbus` output parsing (find the outermost `[...]` and `json.loads` it) is
  tolerant of the exact quoting GNOME's `gdbus call` wraps the Window Calls JSON string in, but
  was only exercised against hand-built fixtures in this sandbox (no real `gdbus`/Shell
  extension here). Worth a quick sanity check against real `gdbus call` output on the host before
  relying on per-app key overrides.
- `NotifySendNotifier` and `YdotoolKeySender` both use a 2.0 s subprocess timeout
  (`notify.SUBPROCESS_TIMEOUT`, hardcoded `2.0` in `keys.py`); `clipboard.py` uses 2.0 s too
  (`clipboard.SUBPROCESS_TIMEOUT`). None of these are configurable and none are specified by the
  architecture doc — flagging in case the host turns out to need a different value (e.g. a slow
  `ydotoold` under load).
- No change was needed to `config.py`, so M3 stayed fully inside its file list; `KeysConfig`
  (frozen dataclass, M1/M2-owned) was used as-is via import.
