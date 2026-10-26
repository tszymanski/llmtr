# M11-fix1 result

## Change
- `tests/test_install.py`: `_run` sets `env["LLMTR_UNAME"] = "Linux"` so the Linux installer tests
  never dispatch to `install-macos.sh` on a macOS runner.
- New test `test_linux_path_is_taken_even_with_darwin_in_outer_env`: outer env has
  `LLMTR_UNAME=Darwin`, a `--dry-run` still prints the gsettings commands.

## Tests (final run after last edit)
- `uv run pytest`: 471 passed, 1 skipped.
- `LLMTR_UNAME=Darwin uv run pytest tests/test_install.py tests/test_install_macos.py`: 44 passed.
- `uv run ruff check .` and `uv run ruff format --check .`: clean.

## Reruns
Reruns: none
