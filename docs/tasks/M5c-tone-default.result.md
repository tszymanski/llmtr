# M5c-tone-default — result

## What was done

- `src/llmtr/config.py`: `ModelsConfig.tone` default changed from `"gemma3"` to `"gemma3:12b"`.
  `fix` left unchanged at `"gemma3"`.
- `config.example.toml`: `tone = "gemma3:12b"` with a comment noting better formal Polish (M5b)
  and the ~6 s reload when alternating with `translate` on a 16 GB GPU.
- `README.md`: requirements section now lists `ollama pull gemma3:12b` alongside the existing
  pulls, and one sentence notes the tone default and its reload trade-off.
- `tests/test_interfaces.py`: `test_errors_carry_user_messages`/`test_config_defaults` split the
  combined `fix == tone == "gemma3"` assertion so `fix` still asserts `"gemma3"` and `tone` now
  asserts `"gemma3:12b"`.
- `tests/test_config.py`, `tests/test_engine.py`: no changes needed — neither hardcodes the tone
  default (`test_config.py`'s `fix`-only assertions are untouched; `test_engine.py` reads
  `cfg.models.tone` back from the config it builds).
- `install.sh`: unchanged — it doesn't check or pull specific models.

## Checks

- `uv run pytest` — pass (196 passed, 1 skipped).
- `uv run ruff check .` — pass.
- `uv run ruff format --check .` — pass (63 files already formatted).
- `bash -n install.sh` — pass.

## Deviations / open issues

- `docs/architecture.md` (not in this task's file list) still documents `models.tone` default as
  `"gemma3"` (table around line 307) and a `fix = "gemma3"` example snippet that doesn't show
  `tone`. Flagging per the "stay inside the files your task contract lists" rule rather than
  editing it; the orchestrator may want a tiny follow-up to keep the architecture doc in sync.
- No new dependencies.
