"""C3 (stream vs poll, 3 runs each) and C4 (fresh-agent latency, two models x four texts x 3).

Usage: uv run python c3_c4_latency.py c3
       uv run python c3_c4_latency.py c4 [model ...]   (model "default" = omit model.id)
"""

from __future__ import annotations

import sys

from cursor_api import build_prompt, load_text
from runner import fresh_run

C4_CASES = [
    ("pl_sentence", "pl", "en"),
    ("pl_paragraph", "pl", "en"),
    ("en_paragraph", "en", "pl"),
    ("en_long", "en", "pl"),
]


def c3() -> None:
    prompt = build_prompt("translate", load_text("pl_sentence"), "pl", "en")
    for i in range(3):
        fresh_run("C3", f"stream-{i}", prompt, method="stream")
        fresh_run("C3", f"poll-{i}", prompt, method="poll")


def c4(models: list[str]) -> None:
    for i in range(3):
        for name, src, dst in C4_CASES:
            prompt = build_prompt("translate", load_text(name), src, dst)
            for m in models:
                fresh_run("C4", f"{name}-{i}", prompt, model=None if m == "default" else m)


if __name__ == "__main__":
    if sys.argv[1] == "c3":
        c3()
    else:
        c4(sys.argv[2:] or ["default", "gpt-5.4-nano"])
