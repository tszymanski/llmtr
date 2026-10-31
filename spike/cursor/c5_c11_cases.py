"""C5 (long-lived agent), C6 (fix/tone), C7 (plan mode), C8 (injection), C9 (cancel),
C10 (cleanup check), C11 (error shapes).

Usage: uv run python c5_c11_cases.py c5|c6|c7|c8|c9|c10|c11
"""

from __future__ import annotations

import json
import sys
import time

import budget
from cursor_api import NAME_PREFIX, OUT_DIR, ApiError, Client, build_prompt, load_text, short
from runner import followup_run, fresh_run


def _agent_status(c: Client, agent_id: str) -> str:
    try:
        return c.agent(agent_id).get("status", "?")
    except ApiError as e:
        return f"HTTP {e.status}: {e.body[:120]}"
    except OSError as e:  # TimeoutError, URLError
        return f"{type(e).__name__}: {e}"


def c5_idle() -> None:
    """C5 idle check alone: one run, 10 min idle, GET agent (timed), one follow-up."""
    c = Client("c5idle")
    first = fresh_run(
        "C5",
        "idle-create-pl_sentence",
        build_prompt("translate", load_text("pl_sentence")),
        keep=True,
        client=c,
    )
    agent_id = first.agent
    try:
        print("agent status after create run:", _agent_status(c, agent_id))
        print("waiting 10 minutes idle ...", flush=True)
        time.sleep(600)
        for attempt in range(2):
            t = time.monotonic()
            st = _agent_status(c, agent_id)
            print(
                f"agent status after idle (try {attempt + 1}): {st} in {time.monotonic() - t:.2f}s"
            )
            if not st.startswith(("TimeoutError", "URLError")):
                break
        followup_run(
            c,
            "C5",
            "f6-after-idle-pl_sentence",
            agent_id,
            build_prompt("translate", load_text("pl_sentence")),
        )
        print("agent status after follow-up:", _agent_status(c, agent_id))
    finally:
        td = time.monotonic()
        c.delete(agent_id)
        print(f"deleted {short(agent_id)} in {time.monotonic() - td:.2f}s; 429s: {c.rate_limited}")


def c5() -> None:
    c = Client("c5")
    first = fresh_run(
        "C5",
        "create-pl_sentence",
        build_prompt("translate", load_text("pl_sentence")),
        keep=True,
        client=c,
    )
    agent_id = first.agent
    plan = [
        ("pl_sentence", "pl", "en"),
        ("pl_paragraph", "pl", "en"),
        ("pl_sentence", "pl", "en"),
        ("en_paragraph", "en", "pl"),
        ("en_long", "en", "pl"),
    ]
    runs: dict[str, str] = {}
    try:
        print("agent status after create run:", _agent_status(c, agent_id))
        for i, (name, src, dst) in enumerate(plan, 1):
            r = followup_run(
                c,
                "C5",
                f"f{i}-{name}",
                agent_id,
                build_prompt("translate", load_text(name), src, dst),
            )
            runs[f"f{i}-{name}"] = r.run
            print(f"  full text f{i}:", json.dumps(r.text, ensure_ascii=False)[:600])
            print("  agent status:", _agent_status(c, agent_id))
        for label in ("f1-pl_sentence", "f5-en_long"):
            try:
                u = c.usage(agent_id, runs[label])
                (OUT_DIR / f"c10_usage_{label}.json").write_text(json.dumps(u, indent=2))
                print(f"C10 usage {label}:", json.dumps(u)[:500])
            except ApiError as e:
                print(f"C10 usage {label}: HTTP {e.status} {e.body[:200]}")
        print("waiting 10 minutes idle ...", flush=True)
        time.sleep(600)
        print("agent status after 10 min idle:", _agent_status(c, agent_id))
        followup_run(
            c,
            "C5",
            "f6-after-idle-pl_sentence",
            agent_id,
            build_prompt("translate", load_text("pl_sentence")),
        )
    finally:
        td = time.monotonic()
        c.delete(agent_id)
        print(f"deleted {short(agent_id)} in {time.monotonic() - td:.2f}s; 429s: {c.rate_limited}")


def c6() -> None:
    fresh_run("C6", "fix-pl_paragraph", build_prompt("fix", load_text("pl_paragraph")))
    fresh_run("C6", "tone-en_paragraph", build_prompt("tone", load_text("en_paragraph")))
    _print_full("C6")


def c7() -> None:
    fresh_run(
        "C7", "plan-pl_paragraph", build_prompt("translate", load_text("pl_paragraph")), mode="plan"
    )
    _print_full("C7")


def c8() -> None:
    prompt = build_prompt("translate", load_text("injection_pl"), "pl", "en")
    for i in range(3):
        fresh_run("C8", f"inject-{i}", prompt)
    _print_full("C8")


def _print_full(case: str) -> None:
    for line in (OUT_DIR / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["case"] == case:
            print(f"--- {r['label']} events={r['events']}\n{r['text']}\n")


def _poll_until_terminal(c: Client, agent_id: str, run_id: str, t0: float) -> dict:
    while True:
        run = c.run(agent_id, run_id)
        st = run.get("status")
        print(
            f"  {time.monotonic() - t0:6.2f} poll status={st} durationMs={run.get('durationMs')}"
            f" result={json.dumps(run.get('result'), ensure_ascii=False)[:120]}"
        )
        if st in ("FINISHED", "ERROR", "CANCELLED", "EXPIRED"):
            return run
        time.sleep(3)


def c9() -> None:
    c = Client("c9")
    prompt = build_prompt("translate", load_text("en_long"), "en", "pl")

    # (a) cancel 2 s after RUNNING
    c.limiter.reserve(6)
    budget.take()
    t0 = time.monotonic()
    agent_id = None
    try:
        created = c.create_agent(prompt, "c9-running")
        agent_id, run_id = created["agent"]["id"], created["run"]["id"]
        print(f"  {time.monotonic() - t0:6.2f} created status={created['run']['status']}")
        t_cancel = None
        for event, data in c.run_stream(agent_id, run_id):
            now = time.monotonic() - t0
            if event == "status":
                print(f"  {now:6.2f} sse status {data.get('status')}")
            if event == "status" and data.get("status") == "RUNNING" and t_cancel is None:
                time.sleep(2)
                t_cancel = time.monotonic() - t0
                try:
                    resp = c.cancel(agent_id, run_id)
                    print(
                        f"  {t_cancel:6.2f} cancel sent -> {json.dumps(resp)[:200]}"
                        f" ({time.monotonic() - t0 - t_cancel:.2f}s)"
                    )
                except ApiError as e:
                    print(f"  {t_cancel:6.2f} cancel HTTP {e.status} {e.body[:200]}")
                break
        run = _poll_until_terminal(c, agent_id, run_id, t0)
        print(
            f"  cancel -> terminal: {time.monotonic() - t0 - (t_cancel or 0):.2f}s,"
            f" status={run.get('status')}"
        )
    finally:
        if agent_id:
            td = time.monotonic()
            try:
                c.delete(agent_id)
                print(f"  delete right after cancel: OK in {time.monotonic() - td:.2f}s")
            except ApiError as e:
                print(f"  delete right after cancel: HTTP {e.status} {e.body[:200]}")

    # (b) cancel while CREATING
    c.limiter.reserve(5)
    budget.take()
    t0 = time.monotonic()
    agent_id = None
    try:
        created = c.create_agent(prompt, "c9-creating")
        agent_id, run_id = created["agent"]["id"], created["run"]["id"]
        print(f"  {time.monotonic() - t0:6.2f} created status={created['run']['status']}")
        try:
            resp = c.cancel(agent_id, run_id)
            print(f"  {time.monotonic() - t0:6.2f} cancel -> {json.dumps(resp)[:200]}")
        except ApiError as e:
            print(f"  {time.monotonic() - t0:6.2f} cancel HTTP {e.status} {e.body[:200]}")
        time.sleep(3)
        run = _poll_until_terminal(c, agent_id, run_id, t0)
        print(f"  CREATING cancel -> status={run.get('status')} at {time.monotonic() - t0:.2f}s")
    finally:
        if agent_id:
            c.delete(agent_id)
    print("429s:", c.rate_limited)


def c9b() -> None:
    """C9 rerun: keep the stream open in a thread, cancel 2 s after RUNNING from the main thread."""
    import threading

    c = Client("c9b")
    prompt = build_prompt("translate", load_text("en_long"), "en", "pl")
    c.limiter.reserve(5)
    budget.take()
    t0 = time.monotonic()
    running = threading.Event()
    agent_id = None

    def watch(aid: str, rid: str) -> None:
        for event, data in Client("c9b").run_stream(aid, rid):
            now = time.monotonic() - t0
            if event in ("status", "result", "error", "done"):
                print(f"  {now:6.2f} sse {event} {json.dumps(data, ensure_ascii=False)[:150]}")
            if event == "status" and data.get("status") == "RUNNING":
                running.set()
            if event in ("done", "error"):
                return

    try:
        created = c.create_agent(prompt, "c9b-running")
        agent_id, run_id = created["agent"]["id"], created["run"]["id"]
        print(f"  {time.monotonic() - t0:6.2f} created status={created['run']['status']}")
        th = threading.Thread(target=watch, args=(agent_id, run_id), daemon=True)
        th.start()
        running.wait(60)
        time.sleep(2)
        tc = time.monotonic() - t0
        try:
            resp = c.cancel(agent_id, run_id)
            print(
                f"  {tc:6.2f} cancel sent -> {json.dumps(resp)[:150]} "
                f"(answered after {time.monotonic() - t0 - tc:.2f}s)"
            )
        except ApiError as e:
            print(
                f"  {tc:6.2f} cancel HTTP {e.status} {e.body[:150]} "
                f"(answered after {time.monotonic() - t0 - tc:.2f}s)"
            )
        th.join(60)
        run = c.run(agent_id, run_id)
        print(
            f"  {time.monotonic() - t0:6.2f} GET run status={run.get('status')} "
            f"durationMs={run.get('durationMs')} result="
            f"{json.dumps(run.get('result'), ensure_ascii=False)[:100]}"
        )
    finally:
        if agent_id:
            td = time.monotonic()
            try:
                c.delete(agent_id)
                print(f"  delete right after cancel: OK in {time.monotonic() - td:.2f}s")
            except ApiError as e:
                print(f"  delete right after cancel: HTTP {e.status} {e.body[:200]}")


def c10() -> None:
    c = Client("c10")
    agents = c.list_agents(include_archived=True)
    ours = [a for a in agents if str(a.get("name", "")).startswith(NAME_PREFIX)]
    print(f"C10 agents listed: {len(agents)}, with prefix {NAME_PREFIX}: {len(ours)}")
    for a in ours:
        print("  left:", short(a.get("id")), a.get("name"), a.get("status"))


def c11() -> None:
    c = Client("c11")

    def show(label: str, fn) -> None:
        try:
            out = fn()
            print(f"C11 {label}: OK (unexpected) {json.dumps(out)[:200]}")
            agent = (out or {}).get("agent", {}).get("id") if isinstance(out, dict) else None
            if agent:
                c.delete(agent)
                print(f"  cleaned up {short(agent)}")
        except ApiError as e:
            print(f"C11 {label}: HTTP {e.status} {e.body[:300]}")

    prompt = build_prompt("translate", load_text("pl_sentence"))
    show(
        "invalid model.id",
        lambda: c.request(
            "POST",
            "/v1/agents",
            {
                "prompt": {"text": prompt},
                "name": NAME_PREFIX + "c11-badmodel",
                "model": {"id": "no-such-model-xyz"},
            },
        ),
    )
    show(
        "empty prompt.text",
        lambda: c.request(
            "POST", "/v1/agents", {"prompt": {"text": ""}, "name": NAME_PREFIX + "c11-empty"}
        ),
    )

    budget.take()
    created = c.create_agent(
        build_prompt("translate", load_text("en_long"), "en", "pl"), "c11-busy"
    )
    agent_id = created["agent"]["id"]
    try:
        show("follow-up on busy agent", lambda: c.followup(agent_id, prompt))
    finally:
        try:
            c.cancel(agent_id, created["run"]["id"])
        except ApiError as e:
            print(f"  cancel HTTP {e.status}")
        c.delete(agent_id)
    print("429s seen:", c.rate_limited)


if __name__ == "__main__":
    {
        "c5": c5,
        "c5idle": c5_idle,
        "c6": c6,
        "c7": c7,
        "c8": c8,
        "c9": c9,
        "c9b": c9b,
        "c10": c10,
        "c11": c11,
    }[sys.argv[1]]()
