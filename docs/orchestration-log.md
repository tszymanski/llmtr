# Orchestration log

One row per task. Times in local time (Europe/Warsaw).

| Task | Agent | Where | Started | Finished | Review rounds | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M0-setup | Orchestrator | host | 2026-10-03 16:05 | 16:20 | – | done | sbx clone mode OK; uv sync + pytest + ruff pass in sandbox (Python 3.14); Ollama reachable via host.docker.internal; other hosts 403 |
| M1-architecture | Architect (subagent) | host worktree | 2026-10-03 16:22 | 16:30 | 0 (user sign-off 2026-10-04) | merged | 8 min, ~110k tokens, 33 tool calls; 21 tests; added engine.py, selection.py, errors.py, fakes.py |
| M2-core | Core worker (claude in sbx) | sbx llmtr-m2-core | 2026-10-04 11:15 | 11:24 | 0 (PASS, 2 minor) | merged | 105 new tests; real-Ollama test blocked in sbx by policy, passes on host |
| M3-desktop | Desktop worker (claude in sbx) | sbx llmtr-m3-desktop | 2026-10-04 11:15 | 11:24 | 0 (PASS, 2 minor) | merged | 76 new tests; added Super/Alt key-up before combos; ydotool keycode syntax assumes ydotool >= 1.0 |
| M4-integration | Integration worker (claude in sbx) | sbx llmtr-m4-integration | 2026-10-04 11:55 | 12:50 | 2 (FIX, FIX, then FIX on an M3 bug) | merged | 17 min build + 2 fix rounds; host-only bugs: ydotool --version, non-hermetic PATH in tests; real --stdin translate/fix/tone OK |
| M3-fix1 | Desktop worker (claude in sbx) | sbx llmtr-m3-fix1 | 2026-10-04 12:52 | 12:58 | 0 (orchestrator review PASS) | merged | restore clipboard on any exception in capture_selection; +4 tests. Worker is Sonnet 5 (sbx default model) |
| M3-fix2 | Desktop worker (claude in sbx) | sbx llmtr-m3-fix2 | 2026-10-04 17:10 | 17:20 | 0 (orchestrator review PASS) | merged | wl-copy fork holds pipes -> set_text timeout (found in user desktop test) ; host round trip: set_text 2.00s timeout -> 0.12s |
| M3-fix3 | Desktop worker (claude in sbx) | sbx llmtr-m3-fix3 | 2026-10-04 17:25 | 17:33 | 0 (orchestrator review PASS) | merged | wl-paste 2.2.1 "Nothing is copied" not treated as empty (race in capture poll) ; host: empty clipboard now returns "" |
| M4-show | Integration worker (claude in sbx) | sbx llmtr-m4-show | 2026-10-04 | ~10 min | 0 (orchestrator review PASS) | merged | tone --show + 5th shortcut (user request) ; 264 tests |
| M5-evaluation | Evaluator (claude in sbx, Ollama access) | sbx llmtr-m5-eval | 2026-10-04 17:45 | 18:05 | 0 (orchestrator review PASS, 1 caveat) | merged | 58 samples, 3 modes, 5 models, tone prompt A/B ; 208 model calls; defaults unchanged; tone prompt V3 adopted (drift 4/54 -> 1/54). Caveat: V3 outputs not hand-scored; host spot check shows formal EN barely formalised ("Hey guys, so basically..." kept) |
| M5b-tone-model | Evaluator (claude in sbx, Ollama access) | sbx llmtr-m5b | 2026-10-04 18:21 | 18:41 | 0 (orchestrator spot-check PASS) | merged | gemma3 4b vs 12b, hand-scored, switch cost ; tone 12b 4.87 vs 4b 4.36, PL formal register 100% vs 77%; 12b+translategemma:12b exceed 16 GB -> ~6 s reload on every alternating call |
| M5c-tone-default | Core worker (claude in sbx) | sbx llmtr-m5c | 2026-10-04 | ~5 min | 0 (orchestrator review PASS) | merged | tone default gemma3 -> gemma3:12b (user decision)  |
| M3-fix4 | Desktop worker (claude in sbx) | sbx llmtr-m3-fix4 | 2026-10-05 | ~10 min | 0 (orchestrator review PASS) | merged | stale ydotoold socket defeats clipboard fallback (user desktop test) ; host: running -> available True, stopped + stale socket -> False |
| M6-logging | Integration worker (claude in sbx) | sbx llmtr-m6-logging | 2026-10-05 | 2026-10-06 | 1 (FIX: tone --next/--show unlogged, case-sensitive level, missing test) | merged | error + run log file, llmtr log --tail (user request) ; 299 tests; host: errors + run lines logged, no user text in log |
| M7-security | Integration worker (claude in sbx) | sbx llmtr-m7-security | 2026-10-22 15:20 | 15:22 | 0 (reviewer PASS, 3 minor) | merged | actions pinned by SHA + persist-credentials false (zizmor 9 -> 0, now blocking), non-http(s) Ollama URL -> ConfigError (ruff S310); CI security job (pip-audit, zizmor) added by orchestrator; 309 tests. SHAs checked with git ls-remote on host; zizmor online mode not run (needs a GitHub token) |

## Lessons

- `sbx` removes the host's `sandbox-<name>` git remote when a sandbox stops, and the git-daemon port
  changes on restart. Fetch worker branches by port: start the sandbox (`sbx exec <name> true`),
  read the port from `sbx ls`, then `git fetch git://127.0.0.1:<port>/llm_translator task/<id>:task/<id>`.
- Reviewer = fresh `claude -p` session in the worker's sandbox, read-only prompt, verdict on line 1.
- Pass prompts to sandboxed `claude -p` as a file (`sbx cp prompt <sandbox>:/tmp/x` then
  `claude -p "$(cat /tmp/x)"`), never inline: backticks and `$` would be expanded by the shell.
- Run every branch's tests **and** its installer on the host before merging. Sandboxes lack the
  real desktop tools, so bugs that depend on them (tool versions, PATH leaks) appear only on the host.
- Stopping the host-side `sbx exec` does not stop `claude` inside the sandbox.
- Unit tests that monkeypatch `subprocess.run` cannot catch process-lifetime bugs (forked
  `wl-copy` holding our pipes). Desktop-tool wrappers need at least one real-subprocess test
  against a fake script that behaves like the real tool.
- Headless `claude -p` workers must run long jobs in the **foreground**: the M5 evaluator started its
  eval run in the background and ended its session, which killed the run (no results). Resumed with
  `claude -p --continue` plus an explicit "foreground only, don't stop until committed" prompt.
- An A/B judged only by automatic metrics (language, length) can hide quality regressions: the M5
  tone prompt fixed language drift but weakened "formal" on English. Hand-score both arms.
- The `sbx` daemon hung after ~2.5 days with 13 accumulated sandboxes (health checks timing out
  for every runtime; `sbx ls`/`create` hung). `sbx daemon restart` + removing finished sandboxes
  fixed it. Remove a worker's sandbox right after its branch is merged.
- Never `pkill -f` a pattern that also appears in the orchestrator's own shell command line: it
  killed that shell.

## Host acceptance (user, 2026-10-05)

All desktop checks passed after M3-fix4: translate/fix/tone in Slack, gedit and Firefox; tone
cycling and `--show`; cancel on second press; clipboard-only fallback with ydotoold stopped;
idempotent `install.sh`.
- `sbx` sandboxes return 403 for github.com, so tools that query GitHub (zizmor online audits,
  `git ls-remote` for action SHAs) must run on the host. Put such values in the contract.
