# Task M5b-tone-model — gemma3 4b vs 12b for tone and fix

Role: **Evaluator** (follow-up). Sandbox with Ollama access
(`OLLAMA_HOST=http://host.docker.internal:11434`). Branch: `task/M5b-tone-model`.
Read `CLAUDE.md`, `docs/proposal.md`, `eval/report.md` (M5), `eval/run_eval.py`,
`eval/samples/*.jsonl`.

## Why

M5 kept `gemma3` (4b) for fix and tone and adopted tone prompt V3. The orchestrator then checked
outputs by hand and found that **formal** barely formalises casual text. English "Hey guys, so
basically…" stayed almost unchanged. With a stronger formal instruction, English improved, but
Polish still kept "Hej"/"Siema" and once introduced an error ("zmerge"). M5 judged the V3 outputs
only by automatic metrics. This task hand-scores everything.

The user pulled `gemma3:12b` (8.1 GB) to test whether a bigger model fixes Polish formal and
concise quality.

## Do

1. Update `eval/eval-config.toml` so the three presets match the user's current config **exactly**
   (the formal instruction changed):
   - team: `Informal team message: casual and friendly, short sentences, first names, no stiff formulas or corporate phrases.`
   - formal: `Formal business tone: polite, complete sentences, no slang, no casual words (replace 'hey guys', 'hej', 'siema', 'basically', 'gonna', 'tho' and similar with neutral, professional wording). Keep the input's language. Do not add a subject line or signature.`
   - concise: `Concise: rewrite noticeably shorter, keeping only the essential message and every fact, name, number, date and link. Remove filler words, apologies and pleasantries. Write in the SAME language as the input text.`
2. Add about 8 more tone samples (4 PL, 4 EN) that are **very casual** chat messages (greetings
   like hej/siema/hey guys, slang, filler). These test whether formal really formalises.
3. Run tone (all samples × 3 presets) and fix (the 20 M5 samples) with **`gemma3` and
   `gemma3:12b`**, current prompts (V3), through the real engine with `--models` overrides. Write
   to new result files (`eval/results/m5b-*.jsonl`); do not overwrite M5's files.
4. **Hand-score every output 1–5**, same rubric as M5, plus per output a `register_ok` flag (did
   the style really change as the preset asks?) and `errors_introduced` (new grammar or spelling
   mistakes). Be strict about Polish grammar.
5. Latency: median and p90 per model. Also measure the **realistic switch cost**: run
   translate (`translategemma:12b`) → tone (`gemma3:12b`) → translate → tone, 5 times, timing each
   call. Both models together are ~16 GB on a 16 GB GPU, so Ollama may evict one each time.
   Do the same with `gemma3` (4b) for comparison. Also record `ollama ps` (use the HTTP
   `/api/ps` endpoint) after each step.
6. Write `eval/report-m5b.md`: summary first (recommended tone model and fix model, one sentence
   why). Then tables per mode × model: mean score, % register_ok, % errors_introduced, % language
   kept, median/p90 latency. Add the switch-cost table, the 5 worst outputs per model, and a clear
   recommendation for `formal` Polish.

## Rules

- Run every model call in the **foreground**, one mode at a time, with long Bash timeouts. Never
  background a run and never end the session before everything is committed. (In M5 a background
  run was killed when the session ended.)
- Do not change `src/` or the default models. Recommend only.
- Stdlib only; all Python through uv; `eval/run_eval.py` may be extended (new flags, new sample
  files) but must keep working for M5's commands.

## Files you may change

`eval/**`, `docs/tasks/M5b-tone-model.result.md`.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` (with `OLLAMA_HOST` unset
for the tests).

## Hand-back

Commit on `task/M5b-tone-model` (prefix `M5b:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file
pointing into the report.
