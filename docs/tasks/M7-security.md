# Task M7-security — fix zizmor workflow findings, reject non-HTTP Ollama URLs

Role: **Integration worker**. Sandbox, clone mode. Branch: `task/M7-security`.
Read `CLAUDE.md`, `docs/architecture.md` (§2 `config.py`, §4.1 `ollama.url`), `.github/workflows/ci.yml`.

## Background (orchestrator, 2026-10-22)

The repo is public now. A local security pass found two things to fix:

1. **zizmor** (`uvx zizmor@1.31.1 .github/`) reports 9 findings in `ci.yml`. The `security` CI job
   already runs zizmor, but with `continue-on-error: true` until they are fixed:
   - `unpinned-uses` (high) ×6: `actions/checkout@v7` and `astral-sh/setup-uv@v10.3.2` in each of the
     3 jobs use tags, which can be moved.
   - `artipacked` (low) ×3: `actions/checkout` keeps the GitHub token in `.git/config`.
2. **Ruff S310**: `UrllibTransport.post_json` calls `urllib.request.urlopen` on the configured Ollama
   URL without checking its scheme, so `[ollama] url = "file:///etc/passwd"` or
   `OLLAMA_HOST=file:///…` is accepted and the file read. The risk is low (the user controls both),
   but only `http` and `https` make sense.

## Change

### Workflow (`.github/workflows/ci.yml`)

- Pin every action to its full commit SHA, with the tag as a trailing comment:
  - `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`
  - `astral-sh/setup-uv@07a047e608db84b3d8c06cd9a7c7dcc9c355c18e # v10.3.2`
  (SHAs taken by the orchestrator with `git ls-remote` on 2026-10-22.)
- Add `with: persist-credentials: false` to every `actions/checkout` step. No step pushes or needs
  the token.
- In the `security` job, remove `continue-on-error: true` and the comment above it, so zizmor blocks.
- Change nothing else in the workflow.

### Ollama URL scheme (`src/llmtr/config.py`)

- In `parse_config`, after `normalize_ollama_url(url)`, raise `ConfigError(source, …)` when the
  scheme is not `http` or `https` (case-insensitive). Message, short and plain, naming where the
  value came from, e.g. `unsupported Ollama URL scheme 'file' in OLLAMA_HOST (use http or https)` or
  `… in [ollama] url …`.
- Do not change the signature or the documented rules of `normalize_ollama_url` (frozen in M1).
  A value without a scheme still gets `http://`.
- `docs/architecture.md`: in the §4.1 `ollama.url` row and §7 (error handling) if it lists config
  errors, add one short clause: only `http`/`https` are accepted.

### Tests (`tests/test_config.py`)

- `file://`, `ftp://` and a custom scheme are rejected, from both `[ollama] url` and `OLLAMA_HOST`,
  with `ConfigError` whose message names the scheme and the source.
- `http://`, `https://`, `HTTP://` (upper case), and a bare `localhost:11434` are accepted.

## Files you may change

`.github/workflows/ci.yml`, `src/llmtr/config.py` (`parse_config` only), `tests/test_config.py`,
`docs/architecture.md` (the two spots above), `docs/tasks/M7-security.result.md`.

## Must pass

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`
- `uvx zizmor@1.31.1 .github/` exits 0 with no findings.
- `uvx --from pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
- If the sandbox blocks `uvx` downloads, say so in the result file; the orchestrator runs them on
  the host.

## Out of scope

Ruff `S` rules in `pyproject.toml`, Dependabot, other actions or jobs, any other validation in
`config.py`.

## Hand-back

Commit on `task/M7-security` (prefix `M7-security:`, end each message with
`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Do not push. Short result file:
what was done, test summary, zizmor output, deviations, open issues.
