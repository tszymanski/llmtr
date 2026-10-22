# M5 evaluation report

Ran on the host's Ollama (`http://host.docker.internal:11434`) from a Docker sandbox, 2026-10-04.
Every call went through the real `llmtr.engine.plan_job`/`run_job` pipeline with
`llmtr.ollama_client.OllamaClient` — no prompts were re-implemented for this eval. Temperature 0,
one run per sample × model, each model warmed up once before timing. Raw outputs:
`eval/results/*.jsonl`; scored outputs (1-5, every output read by hand): `eval/results/*.scored.jsonl`.

## Summary — recommended defaults

| Mode | Recommended default | Why |
| --- | --- | --- |
| translate | `translategemma:12b` (unchanged) | Tied with `translategemma:27b` on quality (4.95 vs 5.00 mean, both 100% correct language, 0% errors) but 3-5x faster (0.96s vs 3.79s median); `Bielik-tansleter` is unusable (mean 3.25, with outright mistranslations, a wrong date, and leaked explanations in 20% of samples). |
| fix | `gemma3` (unchanged) | Mean 4.75 vs 3.20 for `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0`, which translated Polish input to English in 6/20 samples (30%) despite the system prompt saying "never translate" — disqualifying for a grammar-fix tool. |
| tone | `gemma3` (unchanged), with the tuned `TONE_SYSTEM_PROMPT_TEMPLATE` below | Mean 4.61 vs 2.83 for Bielik, which also drifted language (20% of calls) and additionally produced truncated garbage output (e.g. `"awesom"`, `"Coudl"`) on ~7% of English samples — a reliability bug, not just a quality gap. |

None of the three "M5 may change the default" candidates (`translategemma:27b`, both Bielik models)
displace the current defaults. The one concrete change from this task is the tone prompt fix below,
which cut gemma3's own language-drift rate from 4/54 (7.4%) to 1/54 (1.9%).

## translate

20 samples (10 PL→EN, 10 EN→PL), `eval/samples/translate.jsonl`.

| Model | Mean score | % language kept | % preamble/tag leftover* | Median latency | p90 latency |
| --- | --- | --- | --- | --- | --- |
| `translategemma:12b` | 4.95 | 100% | 0% | 0.96s | 1.28s |
| `translategemma:27b` | 5.00 | 100% | 0% | 3.79s | 4.82s |
| `Bielik-tansleter:latest` | 3.25 | 100% | 0%* | 0.60s | 1.31s |

\* The automatic `PREAMBLE_PATTERNS` check only strips one leading chatter line; it does not catch
multi-line trailing commentary. `Bielik-tansleter` added leftover explanations (`"Tłumaczenie:"`,
`"Wyjaśnienie zmian:"`, `"Here is the English translation:"`) on 4/20 samples that this automatic
check missed entirely — all caught by hand and reflected in its score. See `t-en-06`, `t-en-09`
below.

`translategemma:12b` and `:27b` are essentially tied in quality on these 20 short, realistic
messages — 27b reads marginally more natural in a couple of spots but never fixes a 12b error.
Given 27b's 3-5x latency, 12b stays the default; 27b remains available via `--quality` for
longer/harder text where the gap may widen (not tested here — samples are short by design, matching
real Slack/Teams usage).

`Bielik-tansleter` (the user's custom model) is not fit for purpose: beyond the leaked commentary,
it fabricated content (`t-pl-01`), swapped the grammatical subject (`t-pl-02`: "He sent" for "I
sent"), and twice changed facts outright — a date (`t-pl-09`: "this Friday" → "tomorrow") and the
entire meaning of a greeting (`t-en-10`: "Happy birthday" → "Happy New Year"). These are exactly the
kind of silent errors a hotkey tool must not introduce.

## fix

20 samples (12 PL, 8 EN with deliberate errors), `eval/samples/fix.jsonl`.

| Model | Mean score | % language kept | % preamble/tag leftover | Median latency | p90 latency |
| --- | --- | --- | --- | --- | --- |
| `gemma3` | 4.75 | 100% | 0% | 0.50s | 0.58s |
| `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` | 3.20 | 70% | 0% | 0.37s | 0.45s |

`gemma3` fixed 19/20 samples correctly; its one miss (`f-pl-12`) left a gender-agreement error
unfixed (see worst cases). No language drift and no over-editing, so `FIX_SYSTEM_PROMPT` was left
unchanged — the contract's trigger conditions for tuning it ("if fix shows language drift or
over-editing") did not occur for the default model.

`SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` translated Polish input to English instead of fixing it
in 6/12 Polish samples (`f-pl-01, 02, 06, 08, 10, 11`) — the same "never translate" instruction
`gemma3` followed without issue. It also leaked a special token (`<|generate_text|>`, `f-pl-03`) and
wrapped several outputs in markdown `**bold**` markers not present in the input. Its English-mode
results were decent (mean ~4.4) but the Polish failure rate alone disqualifies it: the user's own
language is Polish, and 30% of Polish fixes being translations instead of fixes is not usable
unattended.

## tone

18 samples (9 PL, 9 EN) × 3 presets (team/formal/concise) = 54 calls per model,
`eval/samples/tone.jsonl`, presets from `eval/eval-config.toml` (user's current config).

| Model | Mean score | % language kept | % preamble/tag leftover | Median latency | p90 latency |
| --- | --- | --- | --- | --- | --- |
| `gemma3` | 4.61 | 92.6% | 0% | 0.63s | 0.76s |
| `SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` | 2.83 | 79.6% | 0% | 0.51s | 0.83s |

This confirms the 2026-10-04 "Finding for M5" in `docs/proposal.md`: `gemma3` drifted Polish input
into English on 4/54 calls (`n-pl-03` formal, `n-pl-05` team, `n-pl-07` team, `n-pl-08` formal) even
though the system prompt said "keep the original language: never translate." The `team` preset is
most exposed because the user's own `team` instruction text has no language clause at all (unlike
`formal`/`concise`, which repeat "same language" themselves) — the drift has to be stopped at the
shared template level, which is what the prompt tuning below does.

`SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0` is substantially worse on every axis: language drift in
both directions (11/54, including one EN→PL drift, `n-en-03` formal), frequent no-ops that just
echo the input unchanged despite a clear style instruction (8/54), a hallucinated wrong word
(`"Timeshares"` for "timesheets", `n-en-05` concise), and outright truncated/garbage output on 4/54
calls (`"awesom"`, `"Coudl"`, see worst cases) — a reliability bug independent of style quality.
`gemma3` remains the default.

### Prompt A/B: `TONE_SYSTEM_PROMPT_TEMPLATE`

Tested two candidate rewordings of the shared tone system prompt against `gemma3` (the default
model) on all 54 sample×preset combinations, temperature 0, same samples as above.

| Template | Language drift | Mean concise ratio | Mean formal ratio | Mean team ratio |
| --- | --- | --- | --- | --- |
| Current (production) | 4/54 (7.4%) | 0.640 | 1.367 | 0.982 |
| V2: names "Polish or English" explicitly | 23/54 (42.6%) | — | — | — |
| **V3 (adopted)**: generic "same language as the text between the tags", stated once near the style instruction and once near the output instruction, no language named | **1/54 (1.9%)** | 0.681 | 1.230 | 0.939 |

V2 (spelling out "the input text is in Polish or English; write your reply in that language")
backfired badly: naming the candidate languages measurably biased `gemma3` toward Polish, turning
*most* English inputs into Polish output (drift jumped to 42.6%, almost all EN→PL) — worse than the
production prompt it was meant to fix. Dropped after the A/B run, kept here as a documented dead
end so nobody retries it.

V3 instead refers to "the same language as the text between the tags" without ever naming Polish or
English, and repeats that instruction twice (once right after the style sentence, once right before
the output-format instruction) plus a global "don't add a subject line, greeting or signature the
input doesn't have" rule (previously only in the `formal`/`concise` preset text, not the shared
template). Result: drift fell from 4/54 to 1/54 (the one survivor, `n-pl-03` formal, drifted under
both templates), with no regression in conciseness (ratios move by ≤0.14 in either direction) and no
new greeting/signature violations. Adopted into `src/llmtr/prompts.py`.

`FIX_SYSTEM_PROMPT` was not changed: `gemma3`, the default fix model, showed zero language drift and
no over-editing in this eval, so the contract's conditions for tuning it did not apply.

## The 5 worst outputs

1. **translate / Bielik-tansleter / `t-en-10`** (score 1) — mistranslated "Happy birthday!" as
   `"Szczęśliwego Nowego Roku!"` ("Happy New Year!"). Wrong content delivered with full confidence;
   no error signal of any kind.
2. **translate / Bielik-tansleter / `t-pl-09`** (score 1) — input says the deadline is "this
   Friday"; output says `"...is tomorrow."`, followed by leaked reasoning: `Explanation of important
   changes: Changed "Przypominam" (remember) to "I remind," and "mija w ten piątek" (passes on this
   Friday) to "tomorrow."`. A silently wrong date in a work message.
3. **fix / Bielik-4.5b / `f-pl-01`** (score 1) — input `"Wczoraj poszłem do sklepu po chleb i
   masło."` (a grammar error to fix); output: `"Is there anything else I can help you with?"`. The
   model answered as a chatbot instead of touching the text at all.
4. **tone / Bielik-4.5b / `n-en-06` concise** (score 1) — input "awesome work team! the rollout went
   through with zero issues, client is thrilled." (18 words); output: `"awesom"`. Generation cut off
   mid-word; this is a reliability failure, not a style miss (recurs on `n-en-02` and the `n-en-03`
   concise call, which produced `"Coudl"`).
5. **fix / gemma3 / `f-pl-12`** (score 1) — the one miss from the recommended default model: input
   `"Ona zrobił dobrą robotę..."` (masculine verb form with a feminine subject) was returned
   unchanged, i.e. the agreement error was not fixed. Noted as an open issue below; `gemma3` fixed
   the equivalent error correctly when phrased differently in other samples, so this looks like an
   isolated miss rather than a systematic blind spot — worth a larger sample before concluding
   anything stronger.

## Open issues

- **`gemma3` tone `concise` can flip meaning.** `n-pl-04` concise turned "Sorry for the delayed fix"
  into `"Nie żałuję opóźnienia"` ("I don't regret the delay") — the opposite sentiment — under both
  the old and the new prompt template. Only observed with the apology framing in this preset; not
  covered by the language-drift fix above and not large enough a sample to prompt-tune confidently.
  Worth another look if users report concise rewrites changing meaning.
- **`gemma3` fix missed one PL gender-agreement error** (`f-pl-12`, see worst cases) while fixing an
  equivalent error correctly elsewhere in the set. Single occurrence in 20 samples; not acted on.
- **The automatic "preamble/tag leftover" check under-reports.** `PREAMBLE_PATTERNS` only strips one
  leading line; it missed all of `Bielik-tansleter`'s trailing explanation blocks (see translate
  table). Automatic checks flagged 0% leftover for every model even though several Bielik outputs
  clearly had leftover commentary — the numbers in this report come from manual reading, not the
  automatic flag. Not worth tuning `PREAMBLE_PATTERNS` for a model that is already disqualified on
  other grounds; flagging here in case `Bielik-tansleter` is revisited later.
- **`translategemma:27b` was only tested on short (1-6 sentence) messages**, per the user's stated
  use case. `docs/proposal.md`'s latency table shows the 12b/27b gap widening further on long text
  (7.0s vs 34.6s for a 220-word text); this eval does not re-confirm a quality gap opens up too, so
  `--quality` for long/hard text is still a reasonable escape hatch, just not validated here.
- **Sample size is small** (18-20 per mode, 54 tone calls) and hand-written by the evaluator, not
  drawn from real usage. Good enough to separate "usable" from "unusable" candidates here (the gaps
  are large), but not precise enough to detect small regressions in future prompt or model changes.
