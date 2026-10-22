No `shell=True` usage anywhere — all subprocess calls use argv lists, consistent with the "never start a real desktop tool from tests" requirement and avoiding injection risk.

VERDICT: PASS

No blocker or major findings. Minor observations (non-blocking):

1. minor, `src/llmtr/keys.py:163-182` — `YdotoolKeySender.send` unconditionally prepends `RELEASE_SUPER_ALT` (`125:0 56:0`) to every combo, including combos that themselves use `alt` or `super` as a modifier (e.g. a hypothetical `[[keys.override]]` using `alt+c`). The release-then-press ordering is still correct in that case, but it's worth the orchestrator confirming on the host that no per-app override ever needs Alt/Super as part of the copy/paste combo, since this makes that combination effectively unusable with a real "already held" Alt/Super.
2. minor, `docs/tasks/M3-desktop.md` vs commit message — the task file asks for `Co-Authored-By: Claude Opus 5.5`, which the commit correctly uses (this is a different attribution line than the session-level reminder for *this* review, which is expected and not a problem — just noting the two are intentionally different authors for different roles).

Everything required by the contract is present: all five modules implemented per the architecture, tests cover the M3 bullet in section 8 (argv assertions via monkeypatched `subprocess.run`/`shutil.which`, `FakeClipboard`/`FakeKeySender`/`FakeClock`, `RunLock` dual-fd test, injected `kill`, self-signaled `SIGTERM`/`Cancelled` test), no files outside the allowed list were touched, `uv run pytest` (97 passed), `ruff check` and `ruff format --check` all pass, the commit message is correctly prefixed and attributed, and the hand-back document accurately describes the work, the one architecture-invited deviation (explicit Super/Alt release), and concrete host-side manual checks.
