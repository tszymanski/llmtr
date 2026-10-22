"""M5b switch-cost measurement: translate <-> tone model swapping under GPU memory pressure.

Runs the realistic shortcut sequence translate -> tone -> translate -> tone, 5 times, once with
the tone model `gemma3:12b` (paired with `translategemma:12b`, ~16 GB together) and once with
`gemma3` (4b, ~11 GB together). Every call goes through `llmtr.engine.plan_job`/`run_job` like
`run_eval.py`; timing and a GET `/api/ps` snapshot are recorded right after each call so a
cold-load (model evicted, must reload) is visible as a latency spike plus a changed `/api/ps`
model list.

Usage: ``uv run python eval/switch_cost.py``
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from llmtr.config import load_config
from llmtr.engine import Mode, plan_job, run_job
from llmtr.ollama_client import OllamaClient

EVAL_DIR = Path(__file__).parent
CONFIG_PATH = EVAL_DIR / "eval-config.toml"
RESULTS_DIR = EVAL_DIR / "results"
OUT_PATH = RESULTS_DIR / "m5b-switch-cost.jsonl"

TRANSLATE_MODEL = "translategemma:12b"
TONE_MODELS = ["gemma3:12b", "gemma3"]
REPS = 5

TRANSLATE_TEXT = (
    "Thanks for yesterday's presentation, I really enjoyed it. Could we schedule some time "
    "next week to discuss the rollout details?"
)
TONE_TEXT = "Hey, did you see the build is red again? Could someone take a look when free?"


def get_ps(base_url: str) -> list[dict[str, Any]]:
    """GET ``{base_url}/api/ps``; returns the ``models`` list (name + size_vram), or ``[]``
    on any error (the switch-cost run should not abort just because a status probe failed).
    """
    try:
        with urllib.request.urlopen(f"{base_url}/api/ps", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return []
    models = data.get("models", [])
    return [
        {"name": m.get("name"), "size_vram": m.get("size_vram")}
        for m in models
        if isinstance(m, dict)
    ]


def run_step(mode: Mode, text: str, model: str, config, client) -> tuple[str, float]:
    tone = config.tone.presets[0] if mode == Mode.TONE else None
    job = plan_job(mode, text, config, tone=tone, model=model)
    start = time.monotonic()
    run_job(job, client, config)
    return model, time.monotonic() - start


def main() -> int:
    config = load_config(CONFIG_PATH)
    client = OllamaClient(config.ollama.url, config.ollama.timeout)
    base_url = config.ollama.url

    results: list[dict[str, Any]] = []
    for tone_model in TONE_MODELS:
        print(f"=== switch cost: translategemma:12b <-> {tone_model} ===")
        for rep in range(1, REPS + 1):
            sequence = [
                (Mode.TRANSLATE, TRANSLATE_TEXT, TRANSLATE_MODEL),
                (Mode.TONE, TONE_TEXT, tone_model),
                (Mode.TRANSLATE, TRANSLATE_TEXT, TRANSLATE_MODEL),
                (Mode.TONE, TONE_TEXT, tone_model),
            ]
            for step, (mode, text, model) in enumerate(sequence, start=1):
                _, latency = run_step(mode, text, model, config, client)
                ps = get_ps(base_url)
                entry = {
                    "tone_model": tone_model,
                    "rep": rep,
                    "step": step,
                    "mode": mode.value,
                    "model": model,
                    "latency_s": round(latency, 3),
                    "ollama_ps": ps,
                }
                results.append(entry)
                loaded = ",".join(m["name"] for m in ps)
                print(
                    f"  rep{rep} step{step} {mode.value}/{model}\t{latency:.2f}s\tloaded=[{loaded}]"
                )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as handle:
        for entry in results:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"wrote {len(results)} results to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
