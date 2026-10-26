# M12-fix2 — result

Worker: Mac fix worker, interactive Claude Code session (Claude Opus 5.5) on the test Mac with the
user present, branch `task/M12-fix2` from `main` `6e220aa`, 2026-10-26. No sandbox, no `sudo`.
Only `README.md` and this file change; no code change was needed.

## Reproduction

- The installed uv tool was older than `main` (no M13 cleanup, no D1 text). The installed
  `~/.hammerspoon/llmtr.lua` already matched the template. With the user's OK, `./install.sh` from
  `main`, exit 0, then Reload Config.
- First attempt (221-word `spike/macos/texts/en_long.txt` in Notes, ⌃⌥T, ⌃⌥T): the user saw **no
  bubbles at all**, but `llmtr log` showed the runs (`outcome=cancelled`, `outcome=ok`). Cause: a
  Focus mode was on. A direct test URL (`open -g hammerspoon://llmtr?action=notify&id=test1…`)
  confirmed it. After the user turned Focus off, it worked.
- Second attempt, same steps: **one bubble**. "Translating EN → PL…" was replaced by "Cancelled.",
  which went away by itself. The two-bubble result from M12 A8 **did not reproduce**.

## Evidence

Temporary instrumentation in the installed `llmtr.lua` only (never committed, removed afterwards):
it appended `start <id>`, `onExit <id> <code>`, `url <action> id=… summary=…` and
`withdraw <id> <had bubble>` to a scratch file. Below, times are seconds from the first line
(the file holds epoch seconds).

Cancel run 1 of 3 (runs 2 and 3, ids 3/4 and 5/6, are the same line for line):

```
 0.000 start 1 translate
 1.249 url notify id=1 summary=Translating EN → PL…
 1.249 withdraw 1 false
 5.281 start 2 translate                 <- second ⌃⌥T
 5.444 onExit 2 0                        <- second process: cancel_running, exit 0, no URL
 5.550 url notify id=1 summary=Cancelled.   <- from the FIRST process, its own id
 5.550 withdraw 1 true                   <- "Translating…" withdrawn, replaced
 5.575 onExit 1 0
13.446 withdraw 2 false                  <- nothing stored for id 2
13.576 withdraw 1 true                   <- "Cancelled." gone 8 s after exit
```

`llmtr log` for the three runs:

```
INFO [64345] mode=translate model=translategemma:12b outcome=cancelled duration=5.374s input_len=1326 output_len=0 keystrokes=True
INFO [64454] mode=translate model=translategemma:12b outcome=cancelled duration=4.067s input_len=1326 output_len=0 keystrokes=True
INFO [64531] mode=translate model=translategemma:12b outcome=cancelled duration=5.038s input_len=1326 output_len=0 keystrokes=True
```

Normal translate and error:

```
start 7 translate
url notify id=7 summary=Translating PL → EN…
onExit 7 0
withdraw 7 true                          <- 8 s after exit
start 8 translate
url notify id=8 summary=Nothing copied: secure input is active in Google Chrome.
onExit 8 1
withdraw 8 true                          <- 15 s after exit
```

Hypotheses from the contract, checked against the trace:

1. Different id: **no**. "Cancelled." carries `id=1`, the same as "Translating…".
2. Old bubble not withdrawn: **no**. `withdraw 1 true` happens just before the new bubble, and the
   user saw one bubble.
3. Second process notifies: **no**. Id 2 never sends a URL. It exits 0 about 0.16 s after start.
4. "Cancelled." from elsewhere: **no**. It arrives before `onExit 1`, from the first process.

## Cause

There is **no defect in the current code**. The design in architecture §16/§18 works on the real
Mac. The macOS cancel/notify path is the same as in M12: since `3353667` only `cli.py` changed,
in the M13 Linux wiring (`_make_notifier`/`_make_desktop`). `macos/llmtr.lua.in`,
`macos_notify.py` and `lock.py` are unchanged.

The M12 report was a misreading, made worse by a wrong explanation:

- Replacing a bubble on macOS means the old banner slides out and the new one slides in.
  "Translating…, then Cancelled." can therefore look like two bubbles. Today the user described it
  the same way ("First 'Translating…' and then Cancelled"), and when asked, confirmed it was one
  bubble that got replaced.
- The M12 result's note ("'Cancelled.' comes from the second run, so it is a separate bubble") and
  its D3 README wording were guesses. They were not taken from a trace, and the trace above shows
  they are wrong.

Confirmed by the user after the run: in M12 the two bubbles appeared **one after the other, not at
the same time**. That is the replacement seen today, not two separate bubbles.

## Fix

- `README.md` ("macOS notifications"): the contract asked to drop *"errors and 'Cancelled.' get
  their own bubble"*. The new text is *"an error or 'Cancelled.' replaces 'Translating…' in the
  same bubble"*. That holds for both: an error after the progress bubble also uses the run's id.
- `README.md` ("macOS troubleshooting", added at the user's request after the first hand-back):
  the "No bubbles" item now says to check Focus mode first, because a Focus hides the bubbles
  while the shortcuts keep working (seen in Reproduction).
- No code or test change. The behaviour is already covered by tests:
  - `tests/test_cli.py::test_run_shortcut_second_press_cancels_first_without_starting_job`: the
    second press shows nothing.
  - `test_run_shortcut_cancelled_mid_job_restores_clipboard_normal_urgency`: the cancelled run
    notifies "Cancelled." through its own notifier.
  - `tests/test_macos_notify.py`: the run id comes from `LLMTR_RUN_ID`.
  - `tests/test_install_macos.py`: the Lua template sets the id env and the notify/withdraw
    handler.
- Linux behaviour unchanged.

Must pass, final run after the last edit:

| Command | Result |
| --- | --- |
| `uv run pytest` | 470 passed, 2 skipped |
| `LLMTR_UNAME=Darwin uv run pytest` | 470 passed, 2 skipped |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 110 files already formatted |
| `bash -n install.sh scripts/install-macos.sh` | OK |

## Mac verification

The text was selected in Notes (cancel, normal translate) and in a Chrome password field (error).
A clipboard marker was set before the runs and checked with `pbpaste` afterwards.

| Run | Bubbles seen (user) | Trace | Gone by itself | Text / clipboard |
| --- | --- | --- | --- | --- |
| Cancel 1 | 1: "Translating EN → PL…" → "Cancelled." | ids 1/2, as above | yes (8 s) | unchanged / marker kept |
| Cancel 2 | 1, same | ids 3/4, same | yes | unchanged / marker kept |
| Cancel 3 | 1, same | ids 5/6, same | yes | unchanged / marker kept |
| Normal translate (PL sentence) | 1: "Translating PL → EN…" | id 7, exit 0 | yes (8 s) | replaced / marker kept |
| Error (Chrome password field) | 1: "Nothing copied: secure input is active in Google Chrome." | id 8, exit 1 | yes (15 s) | — / marker kept |

After the runs, the installed `~/.hammerspoon/llmtr.lua` was restored to the copy saved before the
instrumentation. It is byte-identical to `macos/llmtr.lua.in` with `@LLMTR_BIN@` replaced (checked
with `diff`, no `dbg` lines left). The user reloaded the config. The uv tool is the one built from
`main` by `./install.sh`, and this task changes no code.

## Reruns

Reruns: none. No "Must pass" command failed, and no Mac verification attempt failed.
Procedure note: the first reproduction attempt showed no bubbles because Focus was on (see
Reproduction). That was not a code problem and nothing was changed for it. Session restarts: none.

Deviation: the temporary instrumentation was inserted into the installed Lua file with a short
script run by the system `python3`. It only edited text outside the repo, but CLAUDE.md says to run
Python only through uv. Nothing in the repo was run that way.

## Open issues

- If a future test ever sees two llmtr bubbles stacked at once, capture the same trace (a `print`
  per URL event and per `onExit`) before changing code.
- The M12 result's note after D5 and its D3 explanation are wrong (see Cause). The orchestrator
  may want to annotate them.
