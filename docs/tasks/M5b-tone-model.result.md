# M5b-tone-model — result

Done. Full detail, tables, switch-cost numbers and worst cases: `eval/report-m5b.md`.

## Summary

- **tone**: recommend switching the default to `gemma3:12b`. Mean 4.87 vs 4.36 for `gemma3` (4b);
  on Polish `formal` specifically (the finding that triggered this task) `gemma3:12b` is 100%
  register_ok / 100% language-kept vs 4b's 76.9% / 92.3%, and it avoids all three concrete 4b
  failure modes found on the new very-casual samples (English drift, ignoring an explicitly-named
  word to replace, spelling/grammar breakdown under slang input). Caveat: see switch cost below.
- **fix**: keep `gemma3` (4b). Both models are near-perfect (4.75 vs 4.95 mean, zero language drift
  or new errors either way); the one gap (`gemma3` still misses the `f-pl-12` gender-agreement
  error, now on a second independent run) does not justify `gemma3:12b`'s latency and switch-cost
  cost on fix, the highest-frequency mode.
- **Switch cost (new finding, not in M5):** `translategemma:12b` (8.11 GB) + `gemma3:12b` (8.15 GB)
  together exceed the 16 GB GPU — `ollama ps` shows only one of the two resident after every single
  call in a realistic translate→tone→translate→tone sequence, so each call pays a ~6s reload with
  no warm steady state at all. `translategemma:12b` + `gemma3` (4b, 3.34 GB) fit together (≈11.5 GB);
  after one swap-in both stay resident and calls return to sub-1.5s warm latency. If the user
  interleaves translate and tone in the same session, putting `gemma3:12b` on tone turns *every*
  shortcut press into a ~6s wait, not just tone's own. Flagged to the user as the deciding factor,
  not resolved in code (out of scope: "recommend only", per the contract).

## What changed

- `eval/eval-config.toml`: `formal` preset instruction updated to match the user's current config
  exactly (now lists specific words to replace: 'hey guys', 'hej', 'siema', 'basically', 'gonna',
  'tho'; also no longer forbids an added greeting, only a subject line/signature — a visible
  behavior change flagged in the report's Open issues).
- `eval/samples/tone.jsonl`: +8 very casual chat samples (`n-pl-10..13`, `n-en-10..13`) with
  greetings/slang/filler, to stress-test whether `formal` really formalizes.
- `eval/run_eval.py`: added `--out-prefix` so this task's runs write to
  `eval/results/m5b-{tone,fix}.jsonl` instead of overwriting M5's `eval/results/{tone,fix}.jsonl`.
  M5's own commands (no `--out-prefix`) are unaffected.
- `eval/switch_cost.py` (new): runs the realistic translate↔tone sequence 5× per tone model,
  timing each call and polling `/api/ps`, writing `eval/results/m5b-switch-cost.jsonl`.
- `eval/score_m5b.py` (new): the hand-scoring judgment tables for every one of the 196 tone/fix
  outputs, merged into the `.scored.jsonl` files; kept for traceability, not part of the eval CLI.
- `src/llmtr/**`: untouched, per the contract ("do not change `src/` or the default models").

## Deliverables

- `eval/eval-config.toml` — updated `formal` preset wording.
- `eval/samples/tone.jsonl` — 26 samples (18 from M5 + 8 new very-casual).
- `eval/run_eval.py` — `--out-prefix` flag added, M5's commands still work unchanged.
- `eval/switch_cost.py` — new switch-cost measurement script.
- `eval/results/m5b-{tone,fix}.jsonl` — raw outputs (156 + 40 = 196 calls, `gemma3` and
  `gemma3:12b`).
- `eval/results/m5b-{tone,fix}.scored.jsonl` — every output hand-scored 1-5 with `register_ok`,
  `errors_introduced`, and a note.
- `eval/results/m5b-switch-cost.jsonl` — 40 timed calls (2 tone models × 5 reps × 4 steps) with an
  `/api/ps` snapshot after each.
- `eval/score_m5b.py` — the hand-scoring tables (provenance for the `.scored.jsonl` files).
- `eval/report-m5b.md` — full tables, the switch-cost table, the 5 worst outputs per model, open
  issues, and the formal-Polish recommendation.

## Checks

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all pass (`OLLAMA_HOST`
unset for these).

## Open issues (see report for detail)

- Temperature-0 outputs are not fully reproducible run-to-run on this GPU: some M5 drift samples no
  longer drift here with the identical prompt/model/input, and a new one appears. Aggregate
  rates are the trustworthy signal, not individual sample IDs across runs.
- `detect_language`'s automatic check has a false positive on `n-en-08` concise (`gemma3:12b`):
  flags correct English as Polish because "PO" collides with the Polish stopword "po". Caught and
  corrected by hand; noted so the automatic percentages aren't over-trusted.
- `gemma3:12b`'s two worst tone misses (a "piątek"/"piąty" date confusion, a "build"→"budowa"
  mistranslation) are factual/jargon errors, not register or language failures — worth a larger
  Polish business-jargon sample before trusting `gemma3:12b` fully unattended on formal Polish.
- Switch cost is a measurement, not a fix: nothing in `src/` changed to mitigate it (e.g. no
  `keep_alive` tuning was explored), per the contract's "recommend only" scope.
