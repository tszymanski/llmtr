# M7-security — result

Worker: Integration worker, sandbox (clone mode), branch `task/M7-security`, 2026-10-22.

## Done

- `.github/workflows/ci.yml`: all 3 `actions/checkout` steps pinned to
  `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` with `persist-credentials: false`; all 3
  `astral-sh/setup-uv` steps pinned to `07a047e608db84b3d8c06cd9a7c7dcc9c355c18e # v10.3.2`;
  `continue-on-error: true` and its comment removed from the zizmor step. Nothing else changed.
- `src/llmtr/config.py` (`parse_config` only): after `normalize_ollama_url`, a scheme other than
  `http`/`https` (case-insensitive) raises `ConfigError(source, "unsupported Ollama URL scheme
  'file' in OLLAMA_HOST (use http or https)")`, or `… in [ollama] url …` when the value came from
  the config file. Docstring "Raises" list updated. `normalize_ollama_url` untouched.
- `tests/test_config.py`: `file://`, `ftp://`, `myapp://` rejected from both `[ollama] url` and
  `OLLAMA_HOST` (message names the scheme and the source); `http://`, `https://`, `HTTP://` and
  bare `localhost:11434` accepted from both.
- `docs/architecture.md`: §4.1 `ollama.url` row and §7 "Bad config" row note that only
  `http`/`https` are accepted.

## Checks

- `uv run pytest`: 309 passed, 1 skipped (the Ollama-marked test).
- `uv run ruff check .`: All checks passed. `uv run ruff format --check .`: 72 files already formatted.
- YAML check (`uv tool run --from pyyaml python -c "import yaml; yaml.safe_load(...)"`): exit 0.
- zizmor: see below.

## zizmor output

`uvx` is not on PATH in the sandbox, so I ran `uv tool run zizmor@1.31.1` (same thing).

The online run failed: the sandbox firewall returns 403 for
`https://github.com/actions/checkout.git/git-upload-pack`, which zizmor needs to resolve tags:

```
fatal: no audit was performed
'artipacked' audit failed on file://.github/workflows/ci.yml
    3: HTTP status client error (403 Forbidden) for url (https://github.com/actions/checkout.git/git-upload-pack)
```

Offline run (`uv tool run zizmor@1.31.1 --offline .github/`), exit 0:

```
 INFO zizmor: 🌈 zizmor v1.31.1
 INFO audit: zizmor: 🌈 completed .github/workflows/ci.yml
No findings to report. Good job!
```

For comparison, the same offline run on the unchanged workflow reports
`9 findings (3 unsafe fixes): 0 informational, 3 low, 0 medium, 6 high`.

## Deviations

- Used `uv tool run` instead of `uvx` (no `uvx` binary in the sandbox).
- zizmor ran with `--offline` only; online audits (e.g. checking that the SHA matches the
  commented tag) were not run.

## New dependencies

None.

## Open issues

- Orchestrator: please run `uvx zizmor@1.31.1 .github/` on the host (online) to confirm 0 findings
  and that the pinned SHAs match their tag comments; I couldn't check the SHAs from the sandbox.
