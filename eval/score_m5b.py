"""Merges the M5b hand-scoring judgments into the scored result files.

Not part of the eval CLI surface used by M5 (`run_eval.py`); a record of how
`eval/results/m5b-{tone,fix}.scored.jsonl` were produced, kept alongside them for traceability.
Reads `eval/results/m5b-{tone,fix}.jsonl`, attaches `score`, `register_ok`, `errors_introduced`,
`note` from the hand-scoring tables below (every entry read and judged by hand against the sample
text and the rubric in `eval/report-m5b.md`), and writes `eval/results/m5b-{tone,fix}.scored.jsonl`.
Re-running it is a no-op (same input, same tables, same output).
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"

# (id, preset) -> {model: (score, register_ok, errors_introduced, note)}
TONE_SCORES: dict[tuple[str, str], dict[str, tuple[int, bool, bool, str]]] = {
    ("n-pl-01", "team"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-01", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (5, True, False, "unchanged, already formal"),
    },
    ("n-pl-01", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-02", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, "already casual, correctly left as-is"),
    },
    ("n-pl-02", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (
            2,
            True,
            True,
            "mistranslates 'build' (CI/CD) as 'budowa' (construction) -- jargon error; "
            "also unnaturally letter-formal ('Szanowny Panie/Szanowna Pani') for a quick check",
        ),
    },
    ("n-pl-02", "concise"): {
        "gemma3": (4, True, False, 'drops the "no time" context, acceptable but a little lossy'),
        "gemma3:12b": (
            5,
            True,
            False,
            "keeps 'Build' as jargon correctly, unlike the 12b formal call",
        ),
    },
    ("n-pl-03", "team"): {
        "gemma3": (4, True, False, "slightly convoluted phrasing"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-03", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-03", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, "drops the thank-you as a pleasantry, per instructions"),
    },
    ("n-pl-04", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-04", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-04", "concise"): {
        "gemma3": (
            1,
            False,
            True,
            'MEANING FLIP: "Nie żałuję opóźnienia" (I don\'t regret the delay) contradicts '
            "the apology in the input -- same open issue as M5, persists under the new prompt",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-05", "team"): {
        "gemma3": (
            3,
            False,
            False,
            "input is not casual; left as a plain neutral reminder, no team style applied",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-05", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (
            1,
            True,
            True,
            "confuses 'piątek' (Friday) with 'piąty' (the fifth day) -- wrong deadline date",
        ),
    },
    ("n-pl-05", "concise"): {
        "gemma3": (
            2,
            False,
            True,
            '"Przypomnijcie się" is not valid Polish for "I remind you" (reflexive '
            "misuse); barely shortened",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-06", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-06", "formal"): {
        "gemma3": (2, False, False, "barely formalizes; keeps slang 'Mega robota'"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-06", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-07", "team"): {
        "gemma3": (
            2,
            False,
            False,
            "no-op on a formal-sounding input; the EN sibling sample was casualized",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-07", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-07", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-08", "team"): {
        "gemma3": (4, True, False, "already casual; only capitalization changed"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-08", "formal"): {
        "gemma3": (
            2,
            True,
            True,
            'gender agreement error: "faktura ... zawierał" should be "zawierała" (fem. subject)',
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-08", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-09", "team"): {
        "gemma3": (
            2,
            False,
            False,
            "no-op on a formal-sounding input; 12b casualizes the same input",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-09", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-09", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-01", "team"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-01", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-01", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-02", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-02", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-02", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-03", "team"): {
        "gemma3": (
            3,
            False,
            False,
            "no-op on a neutral-polite input (no casual markers); 12b adds 'Hey!'",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-03", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-03", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-04", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-04", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-04", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (
            3,
            True,
            True,
            'claims "Bug fixed" though the input only says the cause was found, not that '
            "a fix shipped -- mild overstatement",
        ),
    },
    ("n-en-05", "team"): {
        "gemma3": (3, False, False, "no-op on a neutral input; 12b adds 'Hey everyone!' framing"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-05", "formal"): {
        "gemma3": (5, True, False, "unchanged, already formal"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-05", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-06", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-06", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-06", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-07", "team"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-07", "formal"): {
        "gemma3": (3, True, True, "invents 'this morning's' meeting time, not stated in the input"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-07", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-08", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-08", "formal"): {
        "gemma3": (
            5,
            True,
            False,
            "adds 'Hello,' greeting -- permitted by the updated instruction, which only "
            "forbids a subject line or signature, not a greeting",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-08", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (
            5,
            True,
            False,
            "automatic detect_language flags this 'pl' because 'PO' collides with the Polish "
            "stopword 'po' -- false positive; the output is correct English",
        ),
    },
    ("n-en-09", "team"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-09", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-09", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-10", "team"): {
        "gemma3": (
            4,
            True,
            False,
            'minor meaning drift ("chcę to w ogóle zrobić") but casual and in Polish',
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-10", "formal"): {
        "gemma3": (
            1,
            False,
            True,
            "drifted to English despite 'keep the input's language' -- very casual PL "
            "slang ('siema') still triggers drift on the 4b model",
        ),
        "gemma3:12b": (
            5,
            True,
            False,
            "no drift this time -- the 12b model keeps Polish on the same input",
        ),
    },
    ("n-pl-10", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-11", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-11", "formal"): {
        "gemma3": (
            2,
            False,
            True,
            "keeps 'Hej' despite the formal instruction explicitly listing it as a word to "
            "replace; also 'przepraszam za późniejsze zwrócenie się' is garbled/unnatural Polish",
        ),
        "gemma3:12b": (
            5,
            True,
            False,
            "replaces 'hej' this time, unlike the 4b model on the same input",
        ),
    },
    ("n-pl-11", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-12", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-12", "formal"): {
        "gemma3": (
            2,
            True,
            True,
            'spelling error "Ziómku" (should be "Ziomku") and a garbled clause '
            '("nikt mi z nim nie związany nie poinformował")',
        ),
        "gemma3:12b": (
            5,
            True,
            False,
            "correct grammar and spelling, unlike the 4b model on the same input",
        ),
    },
    ("n-pl-12", "concise"): {
        "gemma3": (
            3,
            True,
            False,
            "drops half the message (wanting to get up to speed) -- a bit over-trimmed",
        ),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-13", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-13", "formal"): {
        "gemma3": (5, True, False, "fully formalized, no drift, grammatically correct"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-pl-13", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-10", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-10", "formal"): {
        "gemma3": (5, True, False, "fully removes 'gotta'/'tho'/'no biggie', formal English"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-10", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-11", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-11", "formal"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (
            4,
            True,
            False,
            "slightly stilted ('availability amongst colleagues') but slang-free",
        ),
    },
    ("n-en-11", "concise"): {
        "gemma3": (3, False, False, "minimal shortening (ratio 0.88), only drops 'lol'"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-12", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-12", "formal"): {
        "gemma3": (4, True, False, "slightly awkward opening ('Just a notification that')"),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-12", "concise"): {
        "gemma3": (5, True, False, ""),
        "gemma3:12b": (5, True, False, ""),
    },
    ("n-en-13", "team"): {
        "gemma3": (5, True, False, "already casual, correctly left as-is"),
        "gemma3:12b": (5, True, False, "nicely interprets 'no cap' as 'seriously'"),
    },
    ("n-en-13", "formal"): {
        "gemma3": (
            2,
            True,
            True,
            "drops the specific day 'Friday' ('fri'), replaced with vague 'following our "
            "scheduled activities' -- violates the 'keep every date' rule",
        ),
        "gemma3:12b": (
            5,
            True,
            False,
            "keeps 'Friday' correctly, unlike the 4b model on the same input",
        ),
    },
    ("n-en-13", "concise"): {
        "gemma3": (
            4,
            True,
            False,
            '"client approved" is weaker than "loved it" but Friday is kept',
        ),
        "gemma3:12b": (5, True, False, ""),
    },
}

# id -> {model: (score, errors_introduced, note)}; fix has no preset/register axis.
FIX_SCORES: dict[str, dict[str, tuple[int, bool, str]]] = {
    "f-pl-01": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-02": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-03": {
        "gemma3": (4, False, 'missed the comma before "ponieważ"'),
        "gemma3:12b": (4, False, 'missed the comma before "ponieważ" -- same miss as the 4b model'),
    },
    "f-pl-04": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-05": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-06": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-07": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-08": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-09": {
        "gemma3": (5, False, 'capitalizes "Ci" as a polite address -- acceptable'),
        "gemma3:12b": (5, False, 'capitalizes "Ci" as a polite address -- acceptable'),
    },
    "f-pl-10": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-11": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-pl-12": {
        "gemma3": (
            1,
            False,
            'left the gender-agreement error ("zrobił") unfixed -- same miss as M5',
        ),
        "gemma3:12b": (5, False, "correctly fixes the agreement error the 4b model misses"),
    },
    "f-en-01": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-02": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-03": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-04": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-05": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-06": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
    "f-en-07": {
        "gemma3": (5, False, "comma->semicolon style swap, not wrong"),
        "gemma3:12b": (5, False, "comma->semicolon style swap, not wrong"),
    },
    "f-en-08": {"gemma3": (5, False, ""), "gemma3:12b": (5, False, "")},
}


def score_tone() -> None:
    in_path = RESULTS_DIR / "m5b-tone.jsonl"
    out_path = RESULTS_DIR / "m5b-tone.scored.jsonl"
    with in_path.open(encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    with out_path.open("w", encoding="utf-8") as out:
        for entry in entries:
            key = (entry["id"], entry["preset"])
            score, register_ok, errors_introduced, note = TONE_SCORES[key][entry["model"]]
            entry["score"] = score
            entry["register_ok"] = register_ok
            entry["errors_introduced"] = errors_introduced
            entry["note"] = note
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"wrote {len(entries)} scored entries to {out_path}")


def score_fix() -> None:
    in_path = RESULTS_DIR / "m5b-fix.jsonl"
    out_path = RESULTS_DIR / "m5b-fix.scored.jsonl"
    with in_path.open(encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    with out_path.open("w", encoding="utf-8") as out:
        for entry in entries:
            score, errors_introduced, note = FIX_SCORES[entry["id"]][entry["model"]]
            entry["score"] = score
            entry["errors_introduced"] = errors_introduced
            entry["note"] = note
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"wrote {len(entries)} scored entries to {out_path}")


if __name__ == "__main__":
    score_tone()
    score_fix()
