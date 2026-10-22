"""M5 evaluation runner: real samples through the real llmtr engine against candidate models.

Never re-implements prompts: every call goes through ``llmtr.engine.plan_job``/``run_job`` with a
real ``llmtr.ollama_client.OllamaClient`` (``OLLAMA_HOST`` env, see ``eval/eval-config.toml``).
For each mode, every candidate model is warmed up once (untimed) and then run against every
sample (tone: against every sample x preset). One JSON line per (sample[, preset], model) is
appended to ``eval/results/<mode>.jsonl`` with the output, latency and a few automatic checks;
judging (1-5 scores) happens by hand afterwards in ``eval/results/<mode>.scored.jsonl``.

Usage: ``uv run python eval/run_eval.py [--mode translate|fix|tone] [--models NAME ...]``
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from llmtr.config import Config, TonePreset, load_config
from llmtr.engine import Mode, plan_job, run_job
from llmtr.errors import LlmtrError, ModelMissing, OllamaUnavailable
from llmtr.langdetect import detect_language
from llmtr.ollama_client import ChatClient, OllamaClient
from llmtr.prompts import PREAMBLE_PATTERNS, TEXT_CLOSE, TEXT_OPEN

EVAL_DIR = Path(__file__).parent
CONFIG_PATH = EVAL_DIR / "eval-config.toml"
SAMPLES_DIR = EVAL_DIR / "samples"
RESULTS_DIR = EVAL_DIR / "results"

MODE_CANDIDATES: dict[str, list[str]] = {
    "translate": ["translategemma:12b", "translategemma:27b", "Bielik-tansleter:latest"],
    "fix": ["gemma3", "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"],
    "tone": ["gemma3", "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"],
}

_PREAMBLE_RE = tuple(re.compile(pattern) for pattern in PREAMBLE_PATTERNS)


def load_samples(mode: str) -> list[dict[str, Any]]:
    """Read ``eval/samples/<mode>.jsonl`` into a list of dicts, in file order."""
    path = SAMPLES_DIR / f"{mode}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def has_preamble_leftover(output: str) -> bool:
    """True if ``output`` still has an echoed ``<text>`` tag or a chatter line ``strip_preamble``
    did not remove (only one preamble line is stripped; a second one would still show up here).
    """
    if TEXT_OPEN in output or TEXT_CLOSE in output:
        return True
    return any(pattern.match(output) for pattern in _PREAMBLE_RE)


def call_job(
    mode: Mode,
    text: str,
    config: Config,
    client: ChatClient,
    *,
    model: str,
    tone: TonePreset | None,
) -> tuple[str, float, str | None, str | None]:
    """Run one ``plan_job`` + ``run_job`` call, timed. Returns ``(output, latency_s, source_lang,
    target_lang)``; ``source_lang``/``target_lang`` are ``None`` outside translate mode.
    """
    job = plan_job(mode, text, config, tone=tone, model=model)
    start = time.monotonic()
    output = run_job(job, client, config)
    latency = time.monotonic() - start
    return output, latency, job.source_lang, job.target_lang


def run_mode(
    mode: str, models: list[str], config: Config, client: ChatClient
) -> list[dict[str, Any]]:
    """Run every sample (x preset, for tone) against every model in ``models``.

    Raises ``OllamaUnavailable`` immediately (the whole run stops). A model that turns out to be
    missing is skipped (reported on stderr) rather than failing the whole run; any other
    ``LlmtrError`` for a single sample is recorded as an ``error`` field and the run continues.
    """
    samples = load_samples(mode)
    presets: list[TonePreset | None] = list(config.tone.presets) if mode == "tone" else [None]
    results: list[dict[str, Any]] = []

    for model in models:
        try:
            call_job(Mode(mode), samples[0]["text"], config, client, model=model, tone=presets[0])
        except ModelMissing as exc:
            print(f"skipping {model}: {exc.user_message}", file=sys.stderr)
            continue

        for sample in samples:
            for preset in presets:
                entry: dict[str, Any] = {"id": sample["id"], "model": model}
                if preset is not None:
                    entry["preset"] = preset.name
                try:
                    output, latency, source_lang, target_lang = call_job(
                        Mode(mode), sample["text"], config, client, model=model, tone=preset
                    )
                except LlmtrError as exc:
                    entry["error"] = exc.user_message
                    results.append(entry)
                    continue

                expected_lang = target_lang if mode == "translate" else sample.get("src")
                detected_lang = detect_language(output)
                entry.update(
                    output=output,
                    latency_s=round(latency, 3),
                    expected_lang=expected_lang,
                    detected_lang=detected_lang,
                    lang_ok=detected_lang == expected_lang,
                    preamble_leftover=has_preamble_leftover(output),
                    empty_output=not output.strip(),
                )
                if mode == "tone":
                    entry["length_ratio"] = round(len(output) / max(len(sample["text"]), 1), 3)
                results.append(entry)
                print(f"  {model}\t{entry.get('preset', '-')}\t{sample['id']}\t{latency:.2f}s")

    return results


def write_results(mode: str, results: list[dict[str, Any]], out_prefix: str | None = None) -> Path:
    """Overwrite ``eval/results/<mode>.jsonl`` with one JSON line per result, in order.

    ``out_prefix`` (e.g. ``"m5b"``) writes to ``eval/results/<out_prefix>-<mode>.jsonl`` instead,
    so a follow-up eval run never overwrites an earlier task's result files.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{out_prefix}-{mode}.jsonl" if out_prefix else f"{mode}.jsonl"
    out_path = RESULTS_DIR / filename
    with out_path.open("w", encoding="utf-8") as handle:
        for entry in results:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=sorted(MODE_CANDIDATES), help="run only this mode")
    parser.add_argument("--models", nargs="+", help="override the candidate model list")
    parser.add_argument(
        "--out-prefix", help="write to eval/results/<prefix>-<mode>.jsonl instead of <mode>.jsonl"
    )
    args = parser.parse_args(argv)

    config = load_config(CONFIG_PATH)
    client = OllamaClient(config.ollama.url, config.ollama.timeout)

    modes = [args.mode] if args.mode else list(MODE_CANDIDATES)
    for mode in modes:
        models = args.models if args.models else MODE_CANDIDATES[mode]
        print(f"=== {mode}: {models} ===")
        try:
            results = run_mode(mode, models, config, client)
        except OllamaUnavailable as exc:
            print(f"Ollama unreachable, stopping: {exc.user_message}", file=sys.stderr)
            return 1
        out_path = write_results(mode, results, args.out_prefix)
        print(f"wrote {len(results)} results to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
