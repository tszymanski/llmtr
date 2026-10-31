"""Run counter shared by all spike scripts (temp/m14/runs.json). Refuses to go over the limit."""

from __future__ import annotations

import json

from cursor_api import OUT_DIR

LIMIT = 70
PATH = OUT_DIR / "runs.json"


def count() -> int:
    try:
        return int(json.loads(PATH.read_text())["runs"])
    except (OSError, ValueError, KeyError):
        return 0


def take(n: int = 1) -> int:
    used = count()
    if used + n > LIMIT:
        raise SystemExit(f"Run budget: {used} used, {n} more would pass {LIMIT}. Ask the user.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps({"runs": used + n}))
    return used + n
