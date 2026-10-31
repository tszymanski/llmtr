"""Print markdown tables for C3, C4 and C5 from temp/m14/results.jsonl."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict

from cursor_api import OUT_DIR


def mmm(xs: list[float]) -> str:
    xs = [x for x in xs if x is not None]
    if not xs:
        return "-"
    return f"{min(xs):.2f} / {statistics.median(xs):.2f} / {max(xs):.2f}"


def main() -> None:
    rows = [json.loads(x) for x in (OUT_DIR / "results.jsonl").read_text().splitlines()]

    print("### C3\n")
    print(
        "| Method | Runs | Time to text min / med / max (s) | durationMs med | Requests per run "
        "(+1 DELETE) | DELETE min / med / max (s) |"
    )
    print("| --- | --- | --- | --- | --- | --- |")
    for method in ("stream", "poll"):
        g = [r for r in rows if r["case"] == "C3" and r["method"] == method]
        if g:
            print(
                f"| {method} | {len(g)} | {mmm([r['t_text'] for r in g])} | "
                f"{statistics.median(r['duration_ms'] for r in g):.0f} | "
                f"{statistics.median(r['requests'] for r in g):.0f} | "
                f"{mmm([r['t_delete'] for r in g])} |"
            )

    print("\n### C4\n")
    print(
        "| Text | Model | n | Total to text (s) | Create → RUNNING (s) | RUNNING → text (s) "
        "| durationMs min / med / max | thinking |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r["case"] == "C4":
            groups[(r["label"].rsplit("-", 1)[0], r["model"])].append(r)
    for (text, model), g in groups.items():
        dur = [r["duration_ms"] / 1000 for r in g if r["duration_ms"]]
        print(
            f"| {text} | {model} | {len(g)} | {mmm([r['t_text'] for r in g])} | "
            f"{mmm([r['t_running'] for r in g])} | "
            f"{mmm([r['t_text'] - r['t_running'] for r in g if r['t_running']])} | "
            f"{mmm(dur)} | {sum(r['thinking'] for r in g)}/{len(g)} |"
        )
    dels = [r["t_delete"] for r in rows if r.get("t_delete") is not None]
    print(
        f"\nDELETE over all fresh runs (n={len(dels)}): {mmm(dels)}; "
        f">30 s: {sum(d > 30 for d in dels)}"
    )

    print("\n### C5\n")
    print("| Run | Total to text (s) | Create → RUNNING (s) | durationMs | Text start |")
    print("| --- | --- | --- | --- | --- |")
    for r in rows:
        if r["case"] == "C5":
            run = f"{r['t_running']:.2f}" if r["t_running"] else "-"
            text = r["text"][:50].replace("|", "/").replace("\n", " ")
            print(
                f"| {r['label']} | {r['t_text'] or 0:.2f} | {run} | {r['duration_ms']} | {text} |"
            )


if __name__ == "__main__":
    main()
