# Task M5-evaluation — model comparison and prompt tuning

Role: **Evaluator**. Runs in a Docker sandbox (clone mode) **with Ollama access**:
`OLLAMA_HOST=http://host.docker.internal:11434` (network rule `localhost:11434` is enabled for
this sandbox). Branch: `task/M5-evaluation`.

Read first: `CLAUDE.md`, `docs/proposal.md` (Model notes, Tone section incl. the 2026-10-04
"Finding for M5"), `docs/architecture.md` §5 (prompts) and §2 `engine.py`.

## Goal

Measure quality and latency per mode × model on realistic PL/EN text, fix the tone prompt's
language drift, and recommend default models. The user uses llmtr mostly for **Slack/Teams team
messages**, emails and short notes, in Polish and English.

## Models (all on the host's Ollama; run sequentially — one 16 GB GPU)

| Mode | Candidates |
| --- | --- |
| translate | `translategemma:12b` (current default), `translategemma:27b` (`--quality`), `Bielik-tansleter:latest` (user's custom model, prompt format unknown — include it as is, report honestly if the output is unusable) |
| fix | `gemma3` (current default), `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` |
| tone | `gemma3` (current default), `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` |

## Deliverables

1. **Samples** in `eval/samples/` (JSONL, UTF-8, one object per line, hand-written by you,
   realistic, varied length 1–6 sentences, no real personal data):
   - `translate.jsonl` — 20: 10 PL→EN, 10 EN→PL (`id`, `text`, `src`, `reference` optional).
   - `fix.jsonl` — 20: 12 PL, 8 EN, each with deliberate errors (case endings, ortografia,
     interpunkcja, typos, agreement) and `expected` (corrected text).
   - `tone.jsonl` — 18: 9 PL, 9 EN messages of mixed register, each run with all three presets
     from `eval/eval-config.toml`.
2. **`eval/eval-config.toml`** — llmtr config used by the run: the three presets exactly as the
   user has them (copy below), Ollama URL from `OLLAMA_HOST`.
3. **`eval/run_eval.py`** — runs every sample × candidate model through the real llmtr engine
   (`plan_job(..., model=...)` + `run_job` with `OllamaClient`; never re-implement prompts), warms
   each model with one untimed call first, records output + latency (s) to
   `eval/results/<mode>.jsonl`. Automatic checks per output: output language ==
   expected language (`llmtr.langdetect`; for fix/tone == input language), leftover preamble or
   `<text>` tags, empty output, length ratio (tone/concise should be clearly shorter). Run with
   `uv run python eval/run_eval.py [--mode M] [--models ...]`.
4. **Judging** — you read every output and score it 1–5 (translate: adequacy + fluency;
   fix: all errors fixed, nothing else changed, no translation; tone: preset style met, meaning and
   facts kept, same language). Store scores next to outputs (`eval/results/<mode>.scored.jsonl`).
   Be strict and consistent; quote the worst cases in the report.
5. **Prompt tuning** — `TONE_SYSTEM_PROMPT_TEMPLATE` (and `FIX_SYSTEM_PROMPT` if fix shows
   language drift or over-editing) in `src/llmtr/prompts.py`: propose an improved wording, A/B it
   against the current one on the same samples with the default model, keep the change only if it
   is clearly better (language kept, no added subject/greeting/signature, no regression).
   `TRANSLATEGEMMA_TEMPLATE` must not change. Update `tests/test_prompts.py` if it pins the old
   wording.
6. **`eval/report.md`** — summary first (recommended default per mode, one sentence why); then per
   mode a table: model · mean score · % language kept · % preamble/tag leftovers · median and p90
   latency; the prompt A/B table; the 5 worst outputs with short notes; and open issues.

User's current presets (copy into `eval/eval-config.toml`):

```toml
[[tone.preset]]
name = "team"
instruction = "Informal team message: casual and friendly, short sentences, first names, no stiff formulas or corporate phrases."

[[tone.preset]]
name = "formal"
instruction = "Formal business tone: polite, complete sentences, no slang. Write in the SAME language as the input text (Polish stays Polish, English stays English). Do not add a subject line, greeting or signature that the input does not have."

[[tone.preset]]
name = "concise"
instruction = "Concise: rewrite noticeably shorter, keeping only the essential message and every fact, name, number, date and link. Remove filler words, apologies and pleasantries. Write in the SAME language as the input text."
```

## Files you may change

`eval/**` (new), `src/llmtr/prompts.py` (only `TONE_SYSTEM_PROMPT_TEMPLATE`, `FIX_SYSTEM_PROMPT`,
`PREAMBLE_PATTERNS` constants), `tests/test_prompts.py`, `docs/tasks/M5-evaluation.result.md`.
Do **not** change default models in `config.py` or `config.example.toml` — recommend them in the
report; the orchestrator applies them after the user agrees.

## Requirements

- Standard library only; all Python through uv. `eval/run_eval.py` is not imported by tests and
  is excluded from nothing — it must pass ruff.
- Keep total GPU time reasonable: temperature 0, one run per sample × model (no repeats).
- If Ollama is unreachable, stop and report — do not fake results.

## Must pass

`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`

## Hand-back

Commit on `task/M5-evaluation` (prefix `M5-evaluation:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), including `eval/results/*`. Do not
push. `docs/tasks/M5-evaluation.result.md`: short summary + pointers into the report.
