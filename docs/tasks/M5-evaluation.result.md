# M5-evaluation — result

Done. Full detail, tables and worst cases: `eval/report.md`.

## Summary

- **translate**: keep `translategemma:12b` as default. Tied with `translategemma:27b` on quality
  (mean 4.95 vs 5.00, both 100% correct language) but 3-5x faster. `Bielik-tansleter:latest` (the
  user's custom model) is not usable: mean 3.25, with outright content errors (a changed date, a
  mistranslated "Happy birthday" → "Happy New Year") and leaked reasoning text in ~20% of outputs.
- **fix**: keep `gemma3` as default. Mean 4.75 vs 3.20 for
  `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`, which translated Polish input to English in 6/20
  samples (30%) instead of just fixing it — disqualifying.
- **tone**: keep `gemma3` as default. Mean 4.61 vs 2.83 for the Bielik 4.5b model, which also
  drifted language (20% of calls, both directions) and produced truncated garbage output
  (`"awesom"`, `"Coudl"`) on ~7% of English samples.

## What changed in the code

- `src/llmtr/prompts.py`: reworded `TONE_SYSTEM_PROMPT_TEMPLATE` after an A/B test against the
  current wording (`eval/report.md` § Prompt A/B). The new wording refers to "the same language as
  the text between the tags" instead of the old "keep the original language", repeats that
  instruction once near the style sentence and once near the output-format instruction, and adds a
  "don't add a subject line, greeting or signature the input doesn't have" rule to the shared
  template (previously only in the `formal`/`concise` preset instructions, so `team` had no language
  guard at all). Cut `gemma3`'s own tone language-drift rate from 4/54 (7.4%) to 1/54 (1.9%) with no
  regression in conciseness. A second candidate wording that named "Polish or English" explicitly
  was tried and rejected — it made drift *worse* (42.6%), documented in the report as a dead end.
- `FIX_SYSTEM_PROMPT`: unchanged. `gemma3`, the default fix model, showed zero language drift and no
  over-editing in this eval, so the contract's conditions for touching it did not apply.
- `PREAMBLE_PATTERNS`: unchanged. `Bielik-tansleter` leaks multi-line trailing commentary that this
  single-leading-line filter cannot catch, but that model is already disqualified on other grounds
  (see Open issues in the report), so tuning the filter for it was not worth the risk of a regression
  elsewhere.
- `tests/test_prompts.py`: no change needed — its tone-prompt tests build the expected string from
  the live `TONE_SYSTEM_PROMPT_TEMPLATE` constant rather than pinning the old wording.

## Deliverables

- `eval/eval-config.toml` — the user's three tone presets verbatim, `OLLAMA_HOST` picked up via env.
- `eval/samples/{translate,fix,tone}.jsonl` — 20 + 20 + 18 hand-written PL/EN samples.
- `eval/run_eval.py` — runs every sample × candidate model through the real `plan_job`/`run_job`
  pipeline; `uv run python eval/run_eval.py [--mode M] [--models ...]`.
- `eval/results/{translate,fix,tone}.jsonl` — raw outputs + latency + automatic checks (208 calls
  total: 60 translate, 40 fix, 108 tone).
- `eval/results/{translate,fix,tone}.scored.jsonl` — every output hand-scored 1-5 with a short note.
- `eval/results/tone.newprompt.jsonl` — the A/B run of the new tone prompt (gemma3, all 54 calls).
- `eval/report.md` — full tables, the prompt A/B, the 5 worst outputs, and open issues.

## Checks

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` all pass.

## Open issues (see report for detail)

- `gemma3` tone `concise` can flip meaning on apology-framed input (one sample, `n-pl-04`); not
  prompt-tuned, sample too small to act on confidently.
- `gemma3` fix missed one PL gender-agreement error (`f-pl-12`) out of 20 samples; isolated miss.
- The automatic preamble/tag-leftover check under-reports (misses trailing, multi-line commentary);
  the percentages in the report's tables come from manual reading, not that automatic flag.
- `translategemma:27b` was only evaluated on short (1-6 sentence) messages, matching the user's
  stated use case; the proposal's own latency table suggests the 12b/27b gap widens further on long
  text, not re-confirmed here on quality.
