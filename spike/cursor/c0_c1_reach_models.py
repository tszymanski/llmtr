"""C0 (reachability, auth) and C1 (models). Creates no agents.

Prints only statuses, field names and model ids; full bodies go to temp/m14/c0c1.jsonl.
"""

from __future__ import annotations

import json
import sys

from cursor_api import OUT_DIR, ApiError, Client, bad_key


def try_me(auth: str, key: str | None = None) -> None:
    c = Client("c0c1", key=key, auth=auth)
    try:
        me = c.me()
        fields = sorted(me) if isinstance(me, dict) else type(me).__name__
        print(f"C0 /v1/me auth={auth}: OK, fields={fields}")
        (OUT_DIR / "me.json").write_text(json.dumps(me, indent=2))
    except ApiError as e:
        print(f"C0 /v1/me auth={auth}: HTTP {e.status} body={e.body[:300]}")


def main() -> None:
    try_me("basic")
    try_me("bearer")
    try_me("bearer", key=bad_key())
    try_me("basic", key=bad_key())
    try:
        Client("c0c1", key="", auth="none").models()
        print("C0 /v1/models no key: OK (unexpected)")
    except ApiError as e:
        print(f"C0 /v1/models no key: HTTP {e.status} body={e.body[:300]}")

    if "--no-models" in sys.argv:
        return
    models = Client("c0c1").models()
    (OUT_DIR / "models.json").write_text(json.dumps(models, indent=2))
    print("C1 models response keys:", sorted(models) if isinstance(models, dict) else "list")


if __name__ == "__main__":
    main()
