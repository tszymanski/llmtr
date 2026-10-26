# M12-fix1 — result

Worker: Integration worker (Claude Sonnet 5.5), branch `task/M12-fix1`.

## What changed
- **D1** `errors.py`: `accessibility` message now names "Device Control and Data Access
  (Accessibility)". `tests/test_interfaces.py` asserts the new text. Architecture §14 and §19 updated.
  README "macOS permissions" item 1 already named both panes; only wording "here" → "there" fixed.
  `tests/test_cli.py` does not assert the text.
- **D2** `pyproject.toml`: `uv_build>=0.12.22,<0.14.0`. `uv lock` left `uv.lock` unchanged;
  `uv sync --locked` OK; `uv build` into a temp dir OK (sdist + wheel).
- **D3** README "macOS notifications" reworded as specified.
- **D4** README "macOS troubleshooting": iTerm clipboard item added.
- **D5** README Karabiner step 4 reworded.

## Checks (final run after last edit)
`uv run pytest` pass; `uv run ruff check .` pass; `uv run ruff format --check .` pass;
`uv sync --locked` OK; grep for the old D1 text in `src tests` is empty.

## Reruns
Reruns: none.

## Deviations / open issues
None. The old D1 text remains only in `docs/tasks/M12-mac-acceptance.result.md` (a historical record).
