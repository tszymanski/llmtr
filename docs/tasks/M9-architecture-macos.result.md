# M9-architecture-macos — result

## Summary

`docs/architecture.md` gets a v2 part (sections 11-22); Linux behaviour is unchanged.

- **Platform layer:** `platforms.py` (`detect_platform`, `key_defaults`) and `backends.py`
  (`make_notifier`, `make_desktop` -> `Desktop` bundle) are the one place that maps `sys.platform`
  to backends. `cli.py` will use them (M10); every function takes the platform/env as an argument,
  so tests never patch `sys.platform`.
- **macOS backends** behind the existing Protocols, one job per module: `macos_exec.py` (absolute
  paths, `child_env` with `LC_CTYPE=UTF-8` always, `Runner`), `macos_clipboard.py` (`PbClipboard`),
  `macos_keys.py` (`OsascriptKeySender`, combo -> AppleScript, error classification),
  `macos_notify.py` (`HammerspoonNotifier` via `open -g hammerspoon://llmtr?…`, one bubble per
  run through a run id; `OsascriptNotifier` fallback chosen by `notify.backend`),
  `macos_probes.py` (focused bundle id, Secure Input app).
- **Errors:** two additive classes in `errors.py`: `MacKeySendError(reason)` (messages name
  Hammerspoon) and `SecureInputActive(app)`.
- **Defaults:** `KeysConfig` keeps its Linux defaults; `parse_config`/`load_config` get
  `platform=` (default `"linux"`), so existing configs and tests do not change (and the suite stays
  green on the macOS runner). `NotifyConfig.backend` added (default `"auto"`).
- **Lock:** `default_lock_path` already falls back to `~/.cache/llmtr/run.lock`; no change needed.
- **Hammerspoon/installer/work split:** `macos/llmtr.lua.in` (5 release bindings, `hs.task` with
  absolute path, `hs.urlevent` handler), `scripts/install-macos.sh` behind a dispatch in
  `install.sh`; M10 and M11 file lists are disjoint (section 21).
- Stubs: 7 new modules (all bodies `NotImplementedError`; constants real), `tests/test_interfaces.py`
  checks every new name plus the real constants (Linux key defaults equal the dataclass defaults).

## Deviations

- **Copy-time permission failure is an error, not a silent clipboard-only fallback.** The proposal
  says that without Accessibility/Automation `llmtr` falls back to clipboard-only. Accessibility
  cannot be probed cheaply (a probe triggers the Automation dialog, +0.2 s), so `available()` only
  checks that `/usr/bin/osascript` exists. A denied permission then shows at the first copy, where
  a clipboard-only fallback would process unrelated clipboard text; the user gets the exact
  Settings entry instead (risk list: "a missed one must give a clear message"). Clipboard-only
  still applies to a failed paste and to a missing `osascript`.
- `notify.backend` has no auto-detection (macOS has no API for the Notifications setting).
- Additive edits outside `keys.py`-style stubs: `errors.py` (2 classes) and `config.py`
  (`NotifyConfig.backend`), both only additions.

## Reruns

Reruns: none

## Open points

1. Accept the deviation above (copy-time permission error instead of silent fallback)?
2. `llmtr.lua` closes the "Translating…" bubble 8 s (15 s on error) after the process exits.
   Are those times right?
3. The `hammerspoon://` channel latency is unmeasured; `notify.backend = "osascript"` is the
   escape hatch.
4. M10 touches `errors.py` message wording (`ClipboardUnavailable`, `EmptySelection(False)`) so
   macOS text does not mention wl-clipboard/ydotool; acceptable?

## Must-pass output (final run)

```
.................................                                        [100%]
320 passed, 1 skipped in 10.08s
All checks passed!
85 files already formatted
```
