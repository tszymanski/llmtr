"""One timed run: create (or follow up), wait for the final text by stream or poll, delete.

Times are seconds from just before the first request (time.monotonic()).
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import budget
from cursor_api import OUT_DIR, ApiError, Client, short

TERMINAL = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}


@dataclass
class RunResult:
    case: str
    label: str
    model: str
    method: str
    agent: str = ""
    run: str = ""
    status: str = ""
    t_create: float = 0.0  # POST returned
    t_running: float | None = None  # first RUNNING seen
    t_text: float | None = None  # final text available (result event / FINISHED poll)
    t_assistant_end: float | None = None  # stream: turn-ended (assistant text complete)
    t_delete: float | None = None  # duration of DELETE
    duration_ms: int | None = None
    text: str = ""
    requests: int = 0
    thinking: bool = False
    tool_calls: list[str] = field(default_factory=list)
    events: dict[str, int] = field(default_factory=dict)
    error: str = ""

    def save(self) -> None:
        with (OUT_DIR / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(self), ensure_ascii=False) + "\n")

    def line(self) -> str:
        def f(x: float | None) -> str:
            return "  -  " if x is None else f"{x:5.2f}"

        return (
            f"{self.case:3} {self.label:24} {self.model[:12]:12} {self.method:6} {self.status:9} "
            f"create {f(self.t_create)} running {f(self.t_running)} text {f(self.t_text)} "
            f"dur {self.duration_ms} req {self.requests} del {f(self.t_delete)} "
            f"think {int(self.thinking)} tools {self.tool_calls} | {self.text[:70]!r}"
        )


def _tool_name(data: Any) -> str:
    if isinstance(data, dict):
        for k in ("name", "toolName", "tool", "type"):
            if isinstance(data.get(k), str):
                return data[k]
    return json.dumps(data, ensure_ascii=False)[:60]


def wait_stream(c: Client, r: RunResult, agent_id: str, run_id: str, t0: float) -> None:
    assistant: list[str] = []
    for event, data in c.run_stream(agent_id, run_id):
        now = time.monotonic() - t0
        r.events[event] = r.events.get(event, 0) + 1
        if event == "status" and isinstance(data, dict):
            r.status = data.get("status", r.status)
            if r.status == "RUNNING" and r.t_running is None:
                r.t_running = now
        elif event == "thinking":
            r.thinking = True
        elif event == "tool_call":
            r.tool_calls.append(_tool_name(data))
        elif event == "assistant" and isinstance(data, dict):
            assistant.append(data.get("text", ""))
        elif event == "interaction_update" and isinstance(data, dict):
            kind = data.get("type")
            if kind == "turn-ended" and r.t_assistant_end is None:
                r.t_assistant_end = now
            elif kind and "tool" in kind:
                r.tool_calls.append(f"iu:{kind}:{_tool_name(data)}")
        elif event == "result" and isinstance(data, dict):
            r.t_text = now
            r.status = data.get("status", r.status)
            r.text = data.get("text") or ""
            r.duration_ms = data.get("durationMs")
        elif event == "error":
            r.error = json.dumps(data, ensure_ascii=False)[:300]
        if event in ("done", "error"):
            break
    if not r.text and assistant:
        r.text = "".join(assistant)


def wait_poll(
    c: Client, r: RunResult, agent_id: str, run_id: str, t0: float, every: float = 3.0
) -> None:
    while True:
        time.sleep(every)
        run = c.run(agent_id, run_id)
        now = time.monotonic() - t0
        r.status = run.get("status", "")
        if r.status == "RUNNING" and r.t_running is None:
            r.t_running = now
        if r.status in TERMINAL:
            r.t_text = now
            r.duration_ms = run.get("durationMs")
            res = run.get("result")
            r.text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
            return


def fresh_run(
    case: str,
    label: str,
    prompt: str,
    *,
    model: str | None = None,
    method: str = "stream",
    mode: str = "agent",
    keep: bool = False,
    client: Client | None = None,
) -> RunResult:
    """Fresh agent per call. With keep=True the agent is not deleted (caller must delete)."""
    c = client or Client(case.lower())
    r = RunResult(case, label, model or "default", method)
    c.limiter.reserve(3 if method == "stream" else 6)
    budget.take()
    req0 = c.requests
    t0 = time.monotonic()
    agent_id = None
    try:
        created = c.create_agent(prompt, f"{case.lower()}-{label}", model=model, mode=mode)
        r.t_create = time.monotonic() - t0
        agent_id = created["agent"]["id"]
        run_id = created["run"]["id"]
        r.agent, r.run, r.status = short(agent_id), short(run_id), created["run"]["status"]
        if method == "stream":
            wait_stream(c, r, agent_id, run_id, t0)
        else:
            wait_poll(c, r, agent_id, run_id, t0)
    except ApiError as e:
        r.error = f"HTTP {e.status}: {e.body[:300]}"
    finally:
        r.requests = c.requests - req0
        if agent_id and not keep:
            td = time.monotonic()
            try:
                c.delete(agent_id)
            except ApiError as e:
                r.error += f" | delete HTTP {e.status}: {e.body[:200]}"
            r.t_delete = time.monotonic() - td
    r.save()
    print(r.line(), flush=True)
    if keep:
        r.agent = agent_id or ""  # full id for the caller; not saved
        r.run = run_id if agent_id else ""
    return r


def followup_run(
    c: Client, case: str, label: str, agent_id: str, prompt: str, *, model: str = "default"
) -> RunResult:
    """Follow-up run on an existing agent, read by stream. r.run holds the full run id."""
    r = RunResult(case, label, model, "stream")
    c.limiter.reserve(2)
    budget.take()
    req0 = c.requests
    t0 = time.monotonic()
    run_id = ""
    try:
        created = c.followup(agent_id, prompt)
        r.t_create = time.monotonic() - t0
        run = created.get("run", created)
        run_id = run["id"]
        r.agent, r.run, r.status = short(agent_id), short(run_id), run.get("status", "")
        wait_stream(c, r, agent_id, run_id, t0)
    except ApiError as e:
        r.error = f"HTTP {e.status}: {e.body[:300]}"
    r.requests = c.requests - req0
    r.save()
    print(r.line(), flush=True)
    r.run = run_id
    return r
