# M5b evaluation report — gemma3 (4b) vs gemma3:12b for tone and fix

Follow-up to `eval/report.md` (M5). Ran on the host's Ollama (`http://host.docker.internal:11434`)
from a Docker sandbox, 2026-10-04. Every call went through the real
`llmtr.engine.plan_job`/`run_job` pipeline with `llmtr.ollama_client.OllamaClient` and
`--models` overrides, same as M5 — no prompts were re-implemented. Temperature 0. Raw outputs:
`eval/results/m5b-tone.jsonl`, `eval/results/m5b-fix.jsonl`, `eval/results/m5b-switch-cost.jsonl`;
scored outputs (1–5, `register_ok`, `errors_introduced`, every output read by hand):
`eval/results/m5b-{tone,fix}.scored.jsonl`. `eval/eval-config.toml`'s three tone presets were
updated to match the user's current config exactly (new `formal` wording, see below). 8 new very
casual samples (`n-pl-10..13`, `n-en-10..13`: "hej"/"siema"/"hey guys" greetings, slang, filler)
were added to `eval/samples/tone.jsonl`.

## Summary — recommendation

- **Tone: switch the default to `gemma3:12b`.** Mean score 4.87 vs 4.36 for `gemma3` (4b), and on
  the question this task exists to answer — Polish `formal` — `gemma3:12b` hits 100% `register_ok`
  / 100% language-kept vs 4b's 76.9% / 92.3%, including the one case that matters most: the new
  very-casual Polish greeting sample (`n-pl-10`, "Siema!...") that 4b drifted straight to English,
  `gemma3:12b` correctly formalizes and keeps in Polish.
- **Fix: keep `gemma3` (4b).** Both models are near-perfect on grammar fixing (4.75 vs 4.95, no
  language drift, no new errors either way) and `gemma3:12b` fixes one gender-agreement miss the
  4b model has now failed twice (M5 and here) — but the gap is small, fix latency matters more
  than tone latency (it is the most frequently used mode), and the **switch-cost finding below**
  means loading `gemma3:12b` for fix would make every fix call pay the ~6s model-swap tax, not just
  tone calls. 4b stays the default; `gemma3:12b` is not worth it here.
- **The switch-cost test changes the calculus for tone.** `translategemma:12b` (8.11 GB) +
  `gemma3:12b` (8.15 GB) together exceed the 16 GB GPU; Ollama evicts one model on every single
  call in the realistic translate→tone→translate→tone sequence, so **every** call pays a ~6s
  reload (`ollama ps` shows exactly one model resident at a time, the whole run). `translategemma:12b`
  + `gemma3` (4b, 3.34 GB) together fit in ~11.5 GB; after the first swap-in both models stay
  resident and subsequent calls are fast (~0.5–1.3s). **If the user alternates translate and tone
  in the same session** (the realistic GNOME-shortcut flow), `gemma3:12b` for tone turns a sub-
  second shortcut into a 6-second one on every press, not just tone's own latency. This is the
  strongest argument against making `gemma3:12b` the *only* default; see the per-use-case note
  below.

**For Polish `formal` specifically** (the finding that triggered this task): `gemma3:12b` is a
clear, substantial improvement — 100% register_ok/language-kept vs 76.9%/92.3% for 4b, and it
avoids the three concrete 4b failure modes seen below (English drift, keeping the literal "hej" the
instruction names, and a spelling/grammar breakdown on "ziomek"). If the switch cost did not exist,
`gemma3:12b` would be the unqualified recommendation for tone. Given the switch cost, this comes
down to how `llmtr` is used: if translate and tone are pressed in alternation in the same sitting
(likely, since both are everyday shortcuts), the 4b model's small quality gap is the cheaper trade;
if tone is used in bursts separate from translate (e.g., cleaning up a batch of messages before
translating none of them), `gemma3:12b` has no swap cost to pay and is strictly better. Recommend
**`gemma3:12b` for tone** as the primary recommendation (quality matters more for a "make this
formal" tool than ~5s), with the switch-cost caveat flagged to the user so they can pick based on
their actual usage pattern.

## tone

26 samples (13 PL, 13 EN: the 18 from M5 plus 8 new very-casual chat samples) × 3 presets
(team/formal/concise) = 78 calls per model, `eval/samples/tone.jsonl`, presets from
`eval/eval-config.toml` (updated `formal` wording, point 1 of the task contract):

> Formal business tone: polite, complete sentences, no slang, no casual words (replace 'hey guys',
> 'hej', 'siema', 'basically', 'gonna', 'tho' and similar with neutral, professional wording). Keep
> the input's language. Do not add a subject line or signature.

Note this wording **drops "greeting"** from the previous "no subject line, greeting or signature"
clause — adding an unprompted "Hello," is no longer a violation (see `n-en-08` below).

| Model | Mean score | % register_ok | % errors_introduced | % language kept | Median latency | p90 latency |
| --- | --- | --- | --- | --- | --- | --- |
| `gemma3` | 4.36 | 85.9% | 10.3% | 98.7% | 0.62s | 0.77s |
| `gemma3:12b` | 4.87 | 100.0% | 3.8% | 98.7% | 1.10s | 1.54s |

By preset:

| Preset | Model | Mean score | % register_ok | % errors_introduced | % language kept | Median | p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| team | `gemma3` | 4.42 | 80.8% | 0.0% | 100% | 0.62s | 0.70s |
| team | `gemma3:12b` | 5.00 | 100.0% | 0.0% | 100% | 1.13s | 1.25s |
| formal | `gemma3` | 4.15 | 88.5% | 23.1% | 96.2% | 0.72s | 0.81s |
| formal | `gemma3:12b` | 4.69 | 100.0% | 7.7% | 100% | 1.36s | 1.77s |
| concise | `gemma3` | 4.50 | 88.5% | 7.7% | 100% | 0.54s | 0.69s |
| concise | `gemma3:12b` | 4.92 | 100.0% | 3.8% | 96.2%* | 0.88s | 1.09s |

\* The one "language not kept" concise call (`n-en-08`, `gemma3:12b`) is a false positive in the
automatic `detect_language` check: it flags "Please verify last month's invoice PO number." as
Polish because the jargon token "PO" collides with the Polish stopword "po" ("after"/"for"). Hand
reading confirms the output is correct English. Noted in Open issues.

**Formal Polish only** (13 PL `formal` calls — the specific question this task was written to
answer):

| Model | Mean score | % register_ok | % errors_introduced | % language kept |
| --- | --- | --- | --- | --- |
| `gemma3` | 3.77 | 76.9% | 30.8% | 92.3% |
| `gemma3:12b` | 4.46 | 100.0% | 15.4% | 100.0% |

`gemma3`'s `team` miss rate (80.8% register_ok) is not a language problem: 5/26 team calls are
no-ops where the model left a neutral or formal-sounding input unchanged instead of casualizing it
(`n-pl-05`, `n-pl-07`, `n-pl-09`, `n-en-03`, `n-en-05`) — every one of these same five inputs **is**
correctly casualized by `gemma3:12b` on this run, which is clean 100% (26/26) for team. This mirrors
the formal-Polish gap: the bigger model follows the style instruction more reliably across the
board, not just for language-keeping.

Three concrete `gemma3` (4b) failure modes on the new very-casual samples, all absent from
`gemma3:12b` on the identical input:

1. **English drift on `formal`.** `n-pl-10` ("Siema! Widzimy się jutro...") drifts fully to English
   under `gemma3`'s `formal` call despite the instruction's explicit "Keep the input's language."
   `gemma3:12b` formalizes the same input and stays in Polish.
2. **Keeps the literal word the instruction names.** `n-pl-11` ("hej, sorry że tak późno pisze...")
   formalized by `gemma3` keeps "Hej" unchanged at the start of the output, even though the
   instruction explicitly lists "hej" as a word to replace. `gemma3:12b` replaces it.
3. **Spelling/grammar breakdown under slang input.** `n-pl-12` ("ziomek, wiesz coś...") formalized
   by `gemma3` produces a misspelled vocative ("Ziómku" instead of "Ziomku") and a garbled clause
   ("nikt mi z nim nie związany nie poinformował"). `gemma3:12b` produces clean, correct Polish for
   the same input.

`gemma3:12b` is not error-free: its two worst misses are a date-word confusion (`n-pl-05` formal,
"piątek"/Friday vs "piąty"/fifth — see worst cases) and a domain-jargon mistranslation (`n-pl-02`
formal, "build" → "budowa"/construction). Both are factual/semantic errors rather than
register or language failures, and both happen on the model that otherwise wins on every
register/language metric — a reminder that "bigger model" reduces but does not eliminate
hand-scoring-worthy mistakes.

## fix

20 samples (12 PL, 8 EN with deliberate errors), `eval/samples/fix.jsonl` — unchanged from M5.

| Model | Mean score | % language kept | % errors_introduced | Median latency | p90 latency |
| --- | --- | --- | --- | --- | --- |
| `gemma3` | 4.75 | 100% | 0% | 0.50s | 0.56s |
| `gemma3:12b` | 4.95 | 100% | 0% | 0.72s | 0.87s |

Every output is byte-identical between the two models except `f-pl-12`: `gemma3` (4b) again leaves
the gender-agreement error unfixed ("Ona zrobił..." should be "zrobiła" — the same miss flagged in
M5, now confirmed on a second run rather than a one-off), while `gemma3:12b` fixes it correctly
("Ona zrobiła..."). Both models also independently miss the same comma in `f-pl-03`
("przełożone[,] ponieważ") — a shared, not model-size-dependent, miss. No language drift, no new
errors introduced by either model anywhere in the set. The quality gap (4.75 vs 4.95, one sample
out of 20) does not justify `gemma3:12b`'s ~45% latency increase and, per the switch-cost finding,
would make fix pay a full model-reload tax whenever tone or translate ran recently — fix stays on
`gemma3`.

## Switch cost: translate ↔ tone under GPU memory pressure

Sequence `translate (translategemma:12b) → tone → translate → tone`, repeated 5 times, timed per
call, `ollama ps` (`/api/ps`) polled right after each call. Two variants: tone model
`gemma3:12b` (paired total ≈16.3 GB, at the edge of the 16 GB GPU) and tone model `gemma3`
4b (paired total ≈11.5 GB). `eval/switch_cost.py`, `eval/results/m5b-switch-cost.jsonl`.

| Tone model | Median latency (all steps) | Median translate | Median tone | Models resident after warm-up |
| --- | --- | --- | --- | --- |
| `gemma3:12b` | 5.99s | 6.00s | 5.93s | **1** (the other is evicted every call) |
| `gemma3` (4b) | 1.29s | 1.31s | 0.51s | **2** (both stay loaded) |

With `gemma3:12b`, `ollama ps` shows exactly one of the two models resident after every single
call, for all 20 calls in the sequence — Ollama evicts the previous model to fit the next one every
time, so there is no "warm" steady state at all: every call, translate or tone, costs the same
~6s full reload. With `gemma3` (4b), the first tone call after the first translate call is a one-
time ~2.7s swap-in; from the second cycle onward both models stay resident simultaneously and
translate/tone calls return to their normal warm latencies (~1.3s/~0.5s — translate is slightly
above its standalone 0.96s median from M5, likely secondary GPU pressure from the co-resident
4b model, but nowhere near a reload).

**Practical read:** if `llmtr`'s tone model is `gemma3:12b`, *every* shortcut press — translate or
tone — becomes a ~6s wait as long as the user alternates between the two modes, because the two
12b-class models never coexist on this GPU. If tone stays on `gemma3` (4b), both models fit
together and only the first swap after a cold start costs anything extra.

## The 5 worst outputs per model

### `gemma3` (4b)

1. **tone / concise / `n-pl-04`** (score 1) — meaning flip: input apologizes for a late fix
   ("Sorry za spóźniony fix..."); output asserts `"Nie żałuję opóźnienia"` ("I don't regret the
   delay") — the opposite sentiment. Same open issue flagged in M5, confirmed to persist under the
   new prompt/instruction wording.
2. **tone / formal / `n-pl-10`** (score 1) — drifts fully to English on a very casual Polish
   greeting input, despite "Keep the input's language" in the instruction.
3. **fix / `f-pl-12`** (score 1) — leaves `"Ona zrobił..."` (masculine verb, feminine subject)
   unfixed; the same miss as M5, now confirmed on a second independent run.
4. **tone / concise / `n-pl-05`** (score 2) — `"Przypomnijcie się"` is not valid Polish for "I
   remind you" (misused reflexive construction); also barely shortened.
5. **tone / formal / `n-pl-06`** (score 2) — fails to formalize: keeps the slang `"Mega robota"`
   unchanged in an otherwise-formal rewrite.

### `gemma3:12b`

1. **tone / formal / `n-pl-05`** (score 1) — confuses `"piątek"` (Friday) with `"piąty"` (the fifth
   day): the rewritten deadline is wrong ("do dnia piątego" instead of "do piątku"), a factual date
   error introduced by the model, not present in the 4b output for the same sample.
2. **tone / formal / `n-pl-02`** (score 2) — mistranslates "build" (CI/CD) as `"budowa"`
   (construction) — a jargon/domain error — and writes an unnaturally letter-formal
   ("Szanowny Panie/Szanowna Pani") rewrite for what is a quick status check.
3. **tone / concise / `n-en-04`** (score 3) — claims `"Bug fixed"` though the input only says the
   cause was found, not that a fix shipped — a mild overstatement of what was actually said.
4. **tone / formal / `n-en-11`** (score 4) — correctly removes all slang but reads stilted
   ("availability amongst colleagues").
5. **fix / `f-pl-03`** (score 4) — misses the same comma before "ponieważ" that the 4b model
   misses; a shared gap, not specific to model size.

## Recommendation for `formal` Polish

Adopt `gemma3:12b` as the tone model. On the 13 Polish `formal` calls specifically, it is 100%
register_ok and 100% language-kept against 4b's 76.9%/92.3%, and it fixes all three concrete 4b
failure modes found on the new very-casual samples (English drift, ignoring an explicitly-named
word to replace, spelling/grammar breakdown under slang input) on the exact same inputs. The
remaining `gemma3:12b` misses are factual/jargon slips (a date-word confusion, one mistranslated
dev-jargon term), not register or language failures — a materially different, smaller class of
problem than 4b's. The only reason not to switch outright is the switch-cost finding above: tell the
user that if they use tone and translate interleaved in the same session, every shortcut press will
cost ~6s instead of under a second, because `gemma3:12b` and `translategemma:12b` cannot both stay
loaded on a 16 GB GPU. If that trade is acceptable (quality over latency for an occasional-use
mode), `gemma3:12b` is the better default for tone; `gemma3` (4b) remains strictly better for the
high-frequency `fix` mode either way.

## Open issues

- **Non-determinism at temperature 0.** Several samples that drifted language in M5's run for
  `gemma3` (4b) with the *same* `TONE_SYSTEM_PROMPT_TEMPLATE`, the *same* team preset text and the
  *same* input text do not drift in this run (e.g. `n-pl-05` team, `n-pl-03` formal) — and a new
  drift appears on a sample that did not drift before. Ollama/llama.cpp greedy decoding at
  temperature 0 is evidently not bit-exact reproducible run-to-run on this GPU (likely batching or
  kernel-order floating-point differences flipping near-tied argmax choices). This means the
  specific failing sample IDs in this report and in M5's are not fully stable; the *aggregate*
  drift/error rates are the more trustworthy signal, not any individual sample ID in isolation.
- **`detect_language` false-positives on jargon.** `n-en-08`'s concise output is correct English
  but is auto-flagged "pl" because "PO" (purchase order) collides with the Polish stopword "po".
  Same category of issue as M5's note about `PREAMBLE_PATTERNS` under-reporting: the automatic
  checks are a first pass, not a substitute for the hand score in this report.
- **The `formal` instruction no longer forbids an added greeting** (only subject line/signature),
  a wording change made for this task per the contract. `gemma3` added an unprompted "Hello," on
  `n-en-08` formal; this is compliant with the new wording but is a visible behavior change from
  M5's stricter instruction, worth the user's awareness since it affects what "formal" means in
  practice.
- **`gemma3:12b`'s two worst tone misses are factual/jargon, not register.** The "piątek"/"piąty"
  date confusion and the "build"→"budowa" mistranslation are the kind of silent content error a
  hotkey tool should not introduce; sample size here (13 PL formal calls) is small, so this is
  worth another look with more Polish business-jargon samples before fully trusting `gemma3:12b`
  unattended on Polish formal rewrites.
- **Sample size remains small** (26 tone samples, 20 fix samples, as in M5) and hand-written by the
  evaluator. Good enough to see the gap between 4b and 12b on formal Polish; not large enough to
  rule out rarer failure modes in either direction.
