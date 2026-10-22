# M2-core — hand-back

## What was done

Implemented every `NotImplementedError` in the five model-side modules, matching
`docs/architecture.md` sections 2, 4, 5, 6 and 7:

- **`config.py`**: `config_path`/`state_path`/`cache_dir` (XDG lookup with `env` override),
  `normalize_ollama_url` (scheme/port defaults, `0.0.0.0`/`[::]` → `127.0.0.1`, trailing-slash
  strip), `parse_config` (type/range checks per key, `OLLAMA_HOST` override, `[[keys.override]]`
  and `[[tone.preset]]` parsing with the "team" replace-in-place rule), `load_config` (missing
  file → defaults, invalid TOML → `ConfigError`), `load_state`/`save_state` (atomic temp-file +
  `os.replace`, TOML basic-string escaping), `current_tone`/`next_tone` (wrap-around cycling),
  `save_last_result`.
- **`langdetect.py`**: `detect_language` (diacritic × 3 + stopword scoring, tie → `"en"`) and
  `choose_direction`.
- **`prompts.py`**: `build_translate_messages`/`build_fix_messages`/`build_tone_messages`, and
  `strip_preamble` (preamble-line removal, `<text>` tag removal, one fence/quote-pair unwrap
  unless the original was wrapped the same way, then re-applying the original's leading/trailing
  whitespace). `TRANSLATEGEMMA_TEMPLATE` and the other constants were not touched.
- **`ollama_client.py`**: `UrllibTransport.post_json` (stdlib `urllib.request`, mapping
  `HTTPError`→`HTTPStatusError`, socket timeout→`TimeoutError`, other `URLError`/`OSError`→
  `ConnectionError`, bad JSON→`ValueError`) and `OllamaClient` (`__init__`, `chat`: builds the
  `/api/chat` payload, maps transport exceptions to `llmtr.errors` per the architecture table).
- **`engine.py`**: `plan_job` (model selection incl. `--quality`/explicit `model` override,
  direction via `langdetect`, prompt building per mode, `EmptySelection`/`TextTooLong`),
  `progress_text`, `run_job` (calls the client with `temperature`/`num_ctx`/`keep_alive`, then
  `strip_preamble`; raises `OllamaError("The model returned no text.")` on an empty result).

## Tests

New files: `tests/test_config.py` (41 tests), `tests/test_langdetect.py` (12),
`tests/test_prompts.py` (22), `tests/test_ollama_client.py` (14, including a local
`http.server` thread for `UrllibTransport` — no test touches a real Ollama server),
`tests/test_engine.py` (16, one of them the optional `@pytest.mark.ollama` real-model test).

```
uv run pytest               -> 125 passed, 1 skipped (the ollama-marked test)
uv run ruff check .         -> All checks passed!
uv run ruff format --check . -> 31 files already formatted
```

### Optional real-Ollama test

`tests/test_engine.py::test_translate_pl_to_en_with_real_ollama` (marked `@pytest.mark.ollama`,
skipped unless `LLMTR_OLLAMA_TESTS=1`) translates "Dzień dobry, jak się masz?" with
`translategemma:12b` through the real `OllamaClient`/`UrllibTransport`. Ran it manually with
`LLMTR_OLLAMA_TESTS=1 OLLAMA_HOST=http://host.docker.internal:11434`: it fails in this sandbox
because the network rule for `localhost:11434` is not enabled here — the proxy returns
`403 Blocked by network policy: domain localhost:11434 ... no matching allow rule — blocked by
default deny policy`, which `OllamaClient.chat` correctly turns into `OllamaError`. Confirmed via
a direct `UrllibTransport.post_json` call. Per the task contract this is not a blocker; it should
be re-run on the host or in an evaluator sandbox with that rule enabled.

## Deviations from the architecture

None. Implementation follows the stub signatures and docstrings as written.

## Open issues

- The sandbox network policy blocks `localhost:11434`, so the optional ollama-marked test could
  not be verified end to end here (see above). No code issue found; flagging for the
  orchestrator/evaluator to confirm on a sandbox or host with that rule enabled.
- `strip_preamble`'s fence/quote-unwrap step and the preamble-pattern list leave some judgment
  calls undocumented at the character level (e.g. exact handling of a fenced code block with a
  language tag). I implemented a reasonable interpretation consistent with the architecture's
  prose and covered it with table-driven tests; flagging in case M5 evaluation surfaces a real
  model output shape that needs different handling.
