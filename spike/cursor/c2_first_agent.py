"""C2: first no-repo agent, default model, pl_sentence PL->EN. Prints a timeline of every event."""

from __future__ import annotations

import json
import time

import budget
from cursor_api import OUT_DIR, ApiError, Client, build_prompt, load_text, short


def main() -> None:
    c = Client("c2")
    prompt = build_prompt("translate", load_text("pl_sentence"), "pl", "en")
    c.limiter.reserve(4)
    budget.take()
    t0 = time.monotonic()
    agent_id = None

    def at() -> str:
        return f"{time.monotonic() - t0:6.2f}"

    try:
        created = c.create_agent(prompt, "c2")
        agent_id = created["agent"]["id"]
        run_id = created["run"]["id"]
        print(
            at(),
            "create:",
            "agent",
            short(agent_id),
            created["agent"].get("status"),
            "run",
            short(run_id),
            created["run"].get("status"),
        )
        print("        create keys: agent", sorted(created["agent"]), "run", sorted(created["run"]))
        for event, data in c.run_stream(agent_id, run_id):
            summary = json.dumps(data, ensure_ascii=False)[:240]
            print(at(), f"sse {event}:", summary)
            if event in ("done", "error"):
                break
        run = c.run(agent_id, run_id)
        print(at(), "GET run:", json.dumps(run, ensure_ascii=False)[:800])
        (OUT_DIR / "c2_run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False))
        try:
            arts = c.artifacts(agent_id)
            print("        artifacts:", json.dumps(arts)[:300])
        except ApiError as e:
            print("        artifacts: HTTP", e.status, e.body[:200])
        ag = c.agent(agent_id)
        print("        GET agent:", json.dumps(ag, ensure_ascii=False)[:500])
    finally:
        if agent_id:
            c.delete(agent_id)
            print(at(), "deleted", short(agent_id))
        print("requests:", c.requests, "429s:", c.rate_limited)


if __name__ == "__main__":
    main()
