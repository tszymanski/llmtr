# M8-spike — result

Worker: Mac spike worker, interactive Claude Code session on the test Mac with the user present,
branch `task/M8-spike`, 2026-10-23 and 2026-10-25. No sandbox, no `sudo`.

All timings are in seconds. The spike scripts are in `spike/macos/` (see the end of this file).
Raw logs stayed in the session scratchpad and are not committed, because the env dump contains
session tokens.

## Environment (S1)

| Item | Value |
| --- | --- |
| Machine | MacBook Pro M1, 16 GB (`hw.memsize` 17179869184), `arm64` |
| macOS | 27.0.1 (build 26A434) |
| Homebrew | 7.0.10 |
| uv | 0.13.5 (**installed during the spike** with `brew install uv`, user approved) |
| Python used by uv | **3.14.7** (Homebrew); see deviations |
| Ollama | 0.40.9 (Ollama.app; the runner is `llama-server`, context 4096) |
| Models before | `translategemma:12b` |
| Models pulled (user approved) | `gemma3` (4b, 3.4 GB), `gemma3:12b` (8.2 GB) |
| Hammerspoon | 1.1.1 (already installed, never launched before; no `~/.hammerspoon/`) |
| Karabiner-Elements | 16.3.0, DriverKit VirtualHIDDevice 1.8.0 `[activated enabled]` |
| `iogpu.wired_limit_mb` | 0 (default, so about 2/3 of RAM for the GPU) |
| Apps tested | Teams (`com.microsoft.teams2`), Chrome, VS Code, Notes, Terminal, iTerm. **Slack is not installed**; the user agreed to use Teams as the Electron chat app (VS Code is Electron too) |

Existing test suite on macOS: `uv sync` OK; `uv run pytest`: **309 passed, 1 skipped** (the
Ollama-marked test); `uv run ruff check .`: all checks passed; `uv run ruff format --check .`:
75 files already formatted. No failures to list.

## Results S1–S10

| Step | Status | Note |
| --- | --- | --- |
| S1 Environment | PASS | Suite is green on macOS. uv had to be installed. uv picked Python 3.14.7, because the repo has no `.python-version` pin |
| S2 Clipboard | PASS | Round trips are exact (diacritics, multi-line, emoji, 8000 chars), 0.02 s each way. Empty clipboard or an image gives empty output, exit 0. `pbcopy` returns at once and leaves no process behind. **Needs a UTF-8 locale; see S4** |
| S3 Notifications | PASS | `osascript` works without a prompt but shows as **Script Editor**. `hs.notify` shows as Hammerspoon and can be **withdrawn and replaced**, but only after Settings → Notifications → Hammerspoon → Allow, plus a Hammerspoon restart (no prompt is shown) |
| S4 Hotkeys | PASS | All 5 combos fire in all 5 apps, with no app conflicts. Caps Lock (Karabiner) gives the same results, once Karabiner is set up properly. No permission is needed for the hotkeys. Child `PATH=/usr/bin:/bin:/usr/sbin:/sbin` and **no `LANG`**: Polish text in `pbcopy`/`pbpaste` comes out garbled unless `LC_CTYPE=UTF-8` is set |
| S5 osascript keys | PASS | Works in all 6 apps once **Hammerspoon alone** has Accessibility and Automation (System Events). Hotkey → paste 0.43–0.50 s. Release binding with no start delay is reliable. Press binding fails while T is held |
| S6 Hammerspoon keys | PASS | Works in all 6 apps, hotkey → paste 0.47–0.49 s, about the same as S5. Needs only Accessibility, but the flow logic moves into Lua |
| S7 Limits | PASS | Terminal Secure Keyboard Entry does **not** block the hotkey or ⌘C/⌘V on macOS 27. Chrome password field: ⌘C copies nothing, so the "Nothing copied" path triggers and the clipboard is restored. `ioreg` shows `kCGSSessionSecureInputPID` = the owning app (0.36 s) |
| S8 Focused app | PASS | Bundle ID correct for all 6 apps, 0.21–0.27 s per query. Per-app overrides stay unnecessary (⌘C/⌘V work in the terminals too) |
| S9 Models | PARTIAL | Measured everything. But 12b runs at only **7.7–7.8 tokens/s** (memory-bandwidth bound), and **4b does not stay loaded next to translategemma 12b**, so every switch reloads |
| S10 Cleanup | PASS | Spike files removed and Hammerspoon restarted; ⌃⌥T does nothing now. Clipboard not restored, by the user's choice (the saved text was this session's kick-off prompt). Hammerspoon, Karabiner and the models are left installed |

## S4 — app × combo (release binding)

All cells: **fires, app does not react** (checked by the user; one log line per press).

| App | ⌃⌥T | ⌃⌥G | ⌃⌥R | ⇧⌃⌥R | ⇧⌃⌥T |
| --- | --- | --- | --- | --- | --- |
| Teams | ✔ | ✔ | ✔ | ✔ | ✔ |
| Chrome | ✔ | ✔ | ✔ | ✔ | ✔ |
| VS Code | ✔ | ✔ | ✔ | ✔ | ✔ |
| Notes | ✔ | ✔ | ✔ | ✔ | ✔ |
| Terminal | ✔ | ✔ | ✔ | ✔ | ✔ |
| Caps Lock + T/G/R/⇧R/⇧T (Notes) | ✔ | ✔ | ✔ | ✔ | ✔ |

The hotkeys were bound and fired **before** Accessibility was granted, so `hs.hotkey` needs no
permission. A held combo fires once (no auto-repeat).

### S4 — environment of an `hs.task` child

This is with Hammerspoon started normally (Spotlight). When it is started with `open` from a
shell, it inherits that shell's whole environment, so a dump taken that way is misleading.

```
PATH=/usr/bin:/bin:/usr/sbin:/sbin      (no /opt/homebrew/bin, no ~/.local/bin)
HOME, USER, LOGNAME, SHELL, TMPDIR, SSH_AUTH_SOCK, __CF_USER_TEXT_ENCODING=0x1F5:0:0
no LANG / LC_*
uv, llmtr, ollama, brew: not found;  pbcopy, osascript: /usr/bin
```

Locale test (copy in a child without `LANG`, read in a UTF-8 shell, and the other way round):

| Env of `pbcopy`/`pbpaste` | copy | paste |
| --- | --- | --- |
| none (as Hammerspoon gives it) | **garbled** (`za≈º√≥≈Çƒá…`) | **garbled** (`za?�??…`) |
| `LANG=en_US.UTF-8` / `LC_ALL=en_US.UTF-8` / `LC_CTYPE=UTF-8` / `LC_CTYPE=en_US.UTF-8` | OK | OK |

A copy-then-paste round trip in the same child looks fine, because the garbling cancels out. Only
the cross-process check shows the bug.

### S4 — latency (hotkey callback → script start)

| Binding | n | Latency |
| --- | --- | --- |
| release | 75 | 0.02–0.07 (first call after load 0.46) |
| press | 4 | 0.03 |

The release binding also waits for the key-up. Karabiner-EventViewer showed T down → up in
0.10 s for a normal tap.

## S5 / S6 — app × flow

Pass means the selection is replaced by its upper-case version and the old clipboard is back (the
script checks the restore itself: `restored=yes` in every successful run). In Terminal and iTerm,
⌘V pastes at the cursor rather than over the selection; that is normal terminal behaviour and
counts as pass.

| App | S5 release | S5 press (tap) | S6 release |
| --- | --- | --- | --- |
| Teams | ✔ | ✔ | ✔ |
| Chrome | ✔ | — | ✔ |
| VS Code | ✔ (1st try "nothing copied", 2nd ✔) | ✔ | ✔ |
| Notes | ✔ | ✔ | ✔ |
| Terminal | ✔ (pasted at cursor) | — | ✔ (pasted at cursor) |
| iTerm | ✔ (pasted at cursor) | — | ✔ (1st try "nothing copied", 2nd ✔) |

Two single "nothing copied" runs: VS Code (S5) and iTerm (S6). Both worked on the retry a few
seconds later. Separately, the user confirmed that pressing again right after a paste, without
reselecting, fails because nothing is selected any more. The same cause is likely here, but not
confirmed.

Modifier tests in Notes (S5 flow):

| Case | Result |
| --- | --- |
| press binding, quick tap ×3 (one each in Notes, Teams, VS Code) | 3/3 ✔ |
| press binding, ⌃⌥T **held** 2 s | **0/2**, nothing copied (⌘C merged with the held keys) |
| release binding, release T but **hold ⌃⌥** 2 s | 2/2 ✔ |
| release binding, hold **Caps** 2 s after tapping T | 2/2 ✔ |
| release binding, quick tap, Caps+T ×3 and ⌃⌥T ×3 | 6/6 ✔ |
| S6, release binding, hold ⌃⌥ 2 s | 1/1 ✔ |

So the breakage comes from the **non-modifier key still being down** (press binding), not from
⌃⌥ alone. With the release binding no start delay was needed (all runs had `delay=0`).

### S5 / S6 timings (no model)

| Measure | S5 (osascript) | S6 (hs.eventtap) |
| --- | --- | --- |
| hotkey → script start | 0.03–0.04 | — (runs in Lua) |
| ⌘C → text in clipboard | 0.02–0.07 (Teams/Chrome 0.06–0.07) | included below |
| hotkey → ⌘V sent | **0.43–0.50** (n = 22); Terminal with Secure Keyboard Entry 0.83 | **0.47–0.49** (n = 7); first run in Teams 1.00 |
| frontmost bundle ID query (S8) | 0.21–0.27 | — |

Most of the S5 time is two `osascript` start-ups. Most of the S6 time is `hs.eventtap.keyStroke`'s
default 0.2 s hold per keystroke. The very first S5 run took 43 s, because `osascript` blocked
while the Automation dialog was open.

Spike bug: the copy poll loop is 50 × (`pbpaste` + 0.02 s) ≈ 2 s, not the intended 1 s. It doesn't
matter here, since the copied text arrived within 0.07 s in every successful run.

## Permissions — exact prompts and Settings entries

| When | What appeared (exact) | Names |
| --- | --- | --- |
| `osascript display notification` from iTerm and Terminal | no prompt; shown under **Script Editor** | Script Editor |
| First Hammerspoon launch | No system prompt. Hammerspoon Preferences window: *"Accessibility: WARNING! Accessibility is not enabled!"* with an **Enable Accessibility** button | Hammerspoon |
| `hs.notify` | **No prompt.** Hammerspoon was already in System Settings → Notifications with *Allow notifications* off; nothing was shown until the user turned it on **and Hammerspoon was restarted** | Hammerspoon |
| First S5 ⌘C (Hammerspoon → `osascript` → System Events) | Dialog: *"“Hammerspoon” wants access to control “System Events”. Allowing control will provide access to documents and data in “System Events”, and to perform actions within that app."* Subtext: *"Hammerspoon needs to send events to automate applications."* Buttons: [Don't Allow] [Allow] | **Hammerspoon** (not osascript) |
| S5 after Allow, without Accessibility | No dialog; `osascript` failed with *"System Events got an error: osascript is not allowed to send keystrokes. (1002)"*; the text was unchanged | osascript (error text only) |
| Enabling Accessibility | The Hammerspoon button redirected to System Settings. On macOS 27.0.1 the list is titled **"Device Control and Data Access"** (*"Apps with this access can view and send email, … control any app on your Mac, and more."*); entries: Hammerspoon (on), Karabiner-Core-Service (on). **No `osascript` entry was needed** | Hammerspoon |
| Spike tooling only (not part of the flow): `osascript` run from this iTerm session | *"“iTerm” wants access to control “System Events”. … An application in iTerm2 wants to use AppleScript."* (I advised Don't Allow; I removed the call and didn't need the answer) | iTerm |

Settings the llmtr flow needs on macOS 27.0.1, all granted to **Hammerspoon only**:

1. Privacy & Security → Accessibility (shown as "Device Control and Data Access"): **Hammerspoon on**.
2. Privacy & Security → Automation → Hammerspoon → **System Events on**. A dialog asks for this on the first ⌘C, so the installer can trigger it on purpose.
3. Notifications → Hammerspoon → Allow notifications on, then restart Hammerspoon. Only needed if `hs.notify` is used.

## S9 — models and latency

Conditions: Ollama 0.40.9, context 4096, temperature 0. Teams, Chrome and VS Code were open, and
the Mac was **under memory pressure** (swap 7.1–7.5 GB of 8 GB used, 13% memory free). Every time
includes `uv run` start-up (0.25 s for `llmtr --help`). Translate uses `translategemma:12b`, run
through `uv run llmtr <mode> --stdin --model <m>`.

### Translate (`translategemma:12b`) — Mac vs Linux table

| Case | M1 16 GB (s) | RTX 5060 Ti 12b (s), from proposal |
| --- | --- | --- |
| PL→EN sentence (12 w), cold | 17.65 | 4.6 |
| PL→EN sentence, loaded | 3.43–3.59 | 0.7 |
| PL→EN paragraph (56 w) | 11.71–13.89 | 2.3 |
| EN→PL paragraph (71 w) | 18.85–21.18 | 3.5 |
| EN→PL long text (221 w) | 51.29–55.13 | 7.0 |
| Output tokens/s | **7.7** | 49 |

7.7 tokens/s is close to the M1's limit for an 8 GB model: about 68 GB/s of memory bandwidth ÷
8 GB ≈ 8.5 tokens/s. Faster software won't change it much. The model runs 100% on the GPU.

### Tone / fix, 12b vs 4b

| Case | `gemma3:12b` (s) | `gemma3` 4b (s) |
| --- | --- | --- |
| tone EN paragraph (71 w), cold | 18.25 | 8.37 |
| tone EN paragraph, loaded | 8.90–8.92 | 4.01–4.04 |
| tone PL paragraph (56 w), loaded | 15.15 | 6.86 |
| fix PL paragraph, loaded | 18.96 | 6.78 |
| Output tokens/s | 7.8 | 22.7 |
| `ollama ps` size | 7.2–8.1 GB | 2.3–2.9 GB |

Quality, default tone preset: **12b really rewrites** (shorter, casual: "Hej! … Dajcie znać na
kanale projektu…"). **4b barely changes the text** (EN: a few contractions; PL: "chciałbym" →
"chciałem", otherwise the same). The fix test text had no errors, so fix quality was not judged.

### Switch cost (translate → tone → translate → tone, PL paragraph / EN paragraph)

| Step | with `gemma3:12b` (s) | `ollama ps` after | with `gemma3` 4b (s) | `ollama ps` after |
| --- | --- | --- | --- | --- |
| translate (cold) | 22.40 | translategemma only | 19.84 | translategemma only |
| tone | 18.30 | gemma3:12b only | 7.56 | gemma3 only |
| translate again | 19.93 | translategemma only | 19.84 | translategemma only |
| tone again | 18.27 | gemma3:12b only | 7.92 | gemma3 only |

**Only one model is loaded at a time, even with 4b.** Ollama evicts translategemma to load
gemma3 4b (8.1 + 2.3 GB plus overhead is more than the ~10.7 GB GPU limit). I checked this
separately: translate, then tone 4b, leaves only `gemma3:latest` in `ollama ps`. So the proposal
line "gemma3 4b fits next to translategemma 12b" does not hold on this Mac. Each switch costs
about +6–8 s for translate (reload) and +4 s for 4b tone or +9 s for 12b tone.

`translategemma:27b`: not pulled. At ~17 GB it is bigger than the whole 16 GB of RAM, so
`--quality` is not usable on this Mac.

## Recommendations for M9

1. **Keystroke method: S5 (`osascript` → System Events, called from `llmtr`).** Its reliability
   and speed match S6, and it keeps the whole flow (save, copy, poll, model, paste, restore,
   cancel, clipboard-only fallback) in the shared Python code. Hammerspoon then only launches
   `llmtr` by absolute path. Cost: one extra one-time Automation prompt, which is granted to
   Hammerspoon. Keep S6 (`hs.eventtap.keyStroke`, Accessibility only) as the documented fallback
   in case Automation becomes a problem.
2. **Binding: on key release, with no start delay.** The press binding fails while the letter key
   is held; with the release binding a still-held ⌃⌥ or Caps did no harm.
3. **Clipboard backend: always run `pbcopy`/`pbpaste` with `LC_CTYPE=UTF-8`** (or `LANG`) set in
   their environment. Hammerspoon children have no locale, and Polish text gets garbled both ways.
   M10 needs a test for this: the backend sets the variable even when `os.environ` lacks it.
4. **PATH:** `hs.task` children get `/usr/bin:/bin:/usr/sbin:/sbin`. The Lua file must use the
   absolute path of `llmtr` (e.g. `~/.local/bin/llmtr` from `uv tool install`). `llmtr` itself
   should not depend on `PATH` for `ollama` (it uses HTTP, fine) or for desktop tools: call
   `/usr/bin/pbcopy`, `/usr/bin/osascript` by absolute path.
5. **Notifications:** baseline `osascript display notification`. It needs no setup, but it shows
   as "Script Editor" and cannot replace "Translating…". The better user experience is
   `hs.notify`, which shows as Hammerspoon and can withdraw "Translating…" and replace it with
   "Done". It needs a channel from `llmtr` back into Hammerspoon, e.g. a `hammerspoon://llmtr?...`
   URL event (`open -g`), plus the Notifications setting and a restart. Its latency was not
   measured. Suggestion: `hs.notify` via a URL event when it is available, with `osascript` as the
   fallback. Since the 12b models take 10–50 s here, a visible, replaceable "Translating…" matters
   more on the Mac than on Linux.
6. **Secure Input:** keep the existing "clipboard still empty after ⌘C" check as the detection
   (it caught the password field). On that failure only, check
   `ioreg -l -w 0 | grep kCGSSessionSecureInputPID` (0.36 s) to say why, e.g. "Secure input is
   active in Google Chrome". Terminal's Secure Keyboard Entry did not block anything on macOS 27.
7. **Tone model for 16 GB:** the choice is between quality and speed, and it's the user's call.
   `gemma3:12b` is the only one that really changes the tone, at ~9 s loaded and ~18 s after a
   translate. `gemma3` 4b takes 4 s loaded and 8 s after a switch, but it barely rewrites. My
   recommendation: **keep `gemma3:12b` for tone on this Mac** (4b doesn't do the job), keep 4b for
   fix if M5's quality results hold, and accept the reload. Untested option: raise the GPU limit
   (`sudo sysctl iogpu.wired_limit_mb=12288`, not persistent) so that translategemma 12b + 4b fit
   together. That needs `sudo` and leaves less RAM for apps on an already swapping machine.
8. **Translate speed:** 12–21 s per paragraph is a real usability issue. Worth checking in M9 or
   M12: whether a smaller translategemma variant (e.g. 4b, if published) gives acceptable PL↔EN
   quality on the Mac, and making sure cancel (second press) works well on long jobs.

## Karabiner setup the user needed (for the README in M11)

On this Mac the rule existed and was enabled, but **silently did nothing** (Caps Lock kept
toggling). There was no warning in Karabiner-Elements. The steps that made it work:

1. **Driver extension:** already allowed (System Settings → General → Login Items & Extensions →
   Driver Extensions); `systemextensionsctl list` shows
   `org.pqrs.Karabiner-DriverKit-VirtualHIDDevice (1.8.0) [activated enabled]`.
2. **Input Monitoring:** only `Karabiner-EventViewer` was listed. The user had to add
   **`Karabiner-Core-Service`** by hand: Privacy & Security → Input Monitoring → **+** → ⌘⇧G →
   `/Library/Application Support/org.pqrs/Karabiner-Elements/Karabiner-Core-Service.app` → Open →
   switch on. Then Karabiner-Elements was restarted. Karabiner 16 uses `Karabiner-Core-Service`;
   the names `karabiner_grabber`/`karabiner_observer` in the proposal are from older versions.
   `Karabiner-Core-Service` is also listed (on) under "Device Control and Data Access".
3. **Devices → Apple Internal Keyboard → Modify events:** on (it was on by default).
4. **ISO keyboards:** the virtual keyboard is ISO (`keyboard_type_v2: "iso"`). The `` ` ``/`~` key
   produced `§`/`£`-layout characters until **Devices → "Swap ISO layout-specific keys"** was
   switched on (`swap_grave_accent_and_non_us_backslash: true`).
5. **Check** with Karabiner-EventViewer: holding Caps and tapping T must show `left_option` and
   `left_control` down, then `t` with flags `left_control, left_option`.

Rule used (Complex Modifications, "Caps Lock held → Ctrl+Option (tap = Caps Lock)"):

```json
{
  "from": { "key_code": "caps_lock", "modifiers": { "optional": ["any"] } },
  "to": [{ "key_code": "left_control", "modifiers": ["left_option"] }],
  "to_if_alone": [{ "key_code": "caps_lock" }],
  "type": "basic"
}
```

## Deviations

- **uv was missing** and was installed with `brew install uv` (user approved).
- **Python 3.14.7, not 3.13:** the repo has no `.python-version`, and `requires-python = ">=3.13"`
  lets uv pick Homebrew's 3.14. The suite passes on it. Not fixed (outside the allowed files);
  M11 may want a `.python-version` or `uv tool install --python 3.13`.
- **Slack was replaced by Teams** (Slack is not installed; user agreed). VS Code covers Electron
  as well.
- `~/.hammerspoon/` did not exist, so the spike **created** `init.lua` with just the `require`
  line. In S10 both `init.lua` and `llmtr_spike.lua` were deleted instead of removing one line.
  The `Spoons/` folder that Hammerspoon created was left.
- The user changed their own Karabiner and Settings configuration (Input Monitoring, ISO swap,
  Hammerspoon notifications, Accessibility, Automation). The spike made no Karabiner config
  changes itself.
- S8 was measured inside the S5 runs (after the paste), not as a separate hotkey.
- I once ran the system `/usr/bin/python3` by mistake, to read a plist. It failed and nothing
  depended on it; everything else used shell, Lua or `uv run`.

## New dependencies

None in the project. On the Mac: `uv` (Homebrew), the models `gemma3` and `gemma3:12b`.

## Open issues

- `llmtr tone --show` on macOS: `llmtr: notification failed: [Errno 2] No such file or directory:
  'notify-send'`. Expected for v1, but it confirms that M10 has to replace the notify backend.
- Latency of the `hammerspoon://` URL-event channel (for `hs.notify` and cancel) was not measured.
- Whether `hs.eventtap.keyStroke` works without the Automation grant was not checked by revoking
  it (by design it should only need Accessibility).
- The S9 timings were taken under memory pressure (swap nearly full). Token speed is bandwidth
  bound, so closing apps probably helps cold loads more than generation.

## Spike files (`spike/macos/`)

| File | Purpose |
| --- | --- |
| `common.sh` | shared helpers (timing, log, clipboard with `LC_CTYPE=UTF-8`, upper-case, frontmost app) |
| `s2_clipboard.sh` | S2 round trips and timings |
| `llmtr_spike.lua` | Hammerspoon module: 5 hotkeys, press/release, flows log/s5/s6, notification tests, driven by `hammerspoon://llmtr_spike?cmd=…` |
| `s4_hotkey.sh` | S4: logs combo and start latency |
| `env_dump.sh` | S4: child environment and locale check |
| `s5_flow.sh` | S5 flow (osascript keystrokes) plus S8 frontmost query |
| `s6_transform.sh` | S6 transform step (Lua sends the keys) |
| `s9_models.sh`, `texts/` | S9 latency, tone and switch-cost runs and their texts |

Logs go to `${XDG_STATE_HOME:-~/.local/state}/llmtr-spike/` (Hammerspoon children have no
`XDG_STATE_HOME`, so the Lua side uses `~/.local/state`). Before reuse, set `SPIKE` in
`llmtr_spike.lua` to the `spike/macos` folder of your clone.
