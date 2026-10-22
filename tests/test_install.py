"""Tests for install.sh (owner: M4).

No test touches a real `gsettings`, `uv tool install`, or `systemctl`: a temp PATH holds tiny
fake scripts that log their argv (and, for `gsettings`, keep just enough state to answer `get`
after a `set`) so the keybinding-merge logic can be exercised for real without any desktop
environment.

Every subprocess `install.sh` runs under test gets a PATH built *only* from `fake_bin` (the
fakes above, plus a handful of real coreutils resolved once via ``shutil.which`` and symlinked
in) -- never the inherited host PATH. A host running these tests (e.g. the Ubuntu desktop this
installer targets) may have a real `ydotool`/`ydotoold`/`gsettings`/`systemctl`/`uv`/`llmtr` on
PATH; appending the inherited PATH after `fake_bin` would let a "missing tool" scenario (built by
deleting a fake from `fake_bin`) silently fall through to that real binary and pass for the wrong
reason, while still failing on a real host where that binary behaves differently (see
`test_path_does_not_leak_host_directories` below, and docs/tasks/M4-integration.result.md's
"Fix round 2" note).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"

MEDIA_KEYS_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
BASE_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
LLMTR_SLOTS = ("translate", "fix", "tone", "tone-next", "tone-show")
LLMTR_PATHS = [f"{BASE_PATH}/llmtr-{slot}/" for slot in LLMTR_SLOTS]
LLMTR_NAMES = [
    "llmtr translate",
    "llmtr fix",
    "llmtr tone",
    "llmtr tone --next",
    "llmtr tone --show",
]
LLMTR_ARGS = ["translate", "fix", "tone", "tone --next", "tone --show"]
LLMTR_BINDINGS = [
    "<Super><Alt>t",
    "<Super><Alt>g",
    "<Super><Alt>r",
    "<Shift><Super><Alt>r",
    "<Shift><Super><Alt>t",
]

# The pre-M4-show install: four shortcuts, no tone-show slot. Used by the upgrade test below.
OLD_LLMTR_PATHS = [f"{BASE_PATH}/llmtr-{slot}/" for slot in LLMTR_SLOTS[:4]]

GSETTINGS_FAKE = """\
#!/usr/bin/env bash
state="$FAKE_BIN_LOG/gsettings_state.txt"
touch "$state"
if [[ "$1" == "get" ]]; then
    key="$2 $3"
    val=$(grep -F "GET::$key::" "$state" | tail -n1 | sed "s/^GET::$key:://")
    if [[ -z "$val" ]]; then echo "@as []"; else echo "$val"; fi
elif [[ "$1" == "set" ]]; then
    key="$2 $3"
    val="$4"
    grep -v -F "GET::$key::" "$state" > "$state.tmp" 2>/dev/null || true
    mv "$state.tmp" "$state" 2>/dev/null || true
    echo "GET::$key::$val" >> "$state"
fi
echo "gsettings $*" >> "$FAKE_BIN_LOG/gsettings.log"
exit 0
"""

UV_FAKE = """\
#!/usr/bin/env bash
echo "uv $*" >> "$FAKE_BIN_LOG/uv.log"
if [[ "$1 $2 $3" == "tool dir --bin" ]]; then
    echo "$FAKE_BIN_LOG/uvbin"
fi
exit 0
"""

LLMTR_FAKE = """\
#!/usr/bin/env bash
exit 0
"""

# Real ydotool 1.0.4 has no --version/-V of its own ("ydotool: Unknown command: --version");
# only the daemon reports a version. This fake just logs argv, matching that behaviour (any
# subcommand, including --version/-V, is accepted and ignored).
YDOTOOL_FAKE = """\
#!/usr/bin/env bash
echo "ydotool $*" >> "$FAKE_BIN_LOG/ydotool.log"
exit 0
"""

# ``ydotoold -V`` on the real 1.0.4 build prints exactly "v1.0.4-0-g57ba7d0". Controlled by
# $FAKE_YDOTOOLD_VERSION so tests can simulate other builds; defaults to the real 1.0.4 string.
YDOTOOLD_FAKE = """\
#!/usr/bin/env bash
echo "ydotoold $*" >> "$FAKE_BIN_LOG/ydotoold.log"
if [[ "$1" == "-V" ]]; then
    echo "${FAKE_YDOTOOLD_VERSION:-v1.0.4-0-g57ba7d0}"
fi
exit 0
"""

# Only "systemctl --user is-active ydotoold.service" matters to install.sh; controlled by
# $FAKE_YDOTOOLD_ACTIVE (default "1" = active, matching `systemctl is-active`'s own exit codes).
SYSTEMCTL_FAKE = """\
#!/usr/bin/env bash
echo "systemctl $*" >> "$FAKE_BIN_LOG/systemctl.log"
if [[ "$*" == *"is-active ydotoold.service"* ]]; then
    if [[ "${FAKE_YDOTOOLD_ACTIVE:-1}" == "1" ]]; then
        echo "active"
        exit 0
    else
        echo "inactive"
        exit 3
    fi
fi
exit 0
"""


def _write_fake(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


# The only real binaries install.sh's own code and the fake scripts above need: bash (to run
# install.sh and, via each fake's "#!/usr/bin/env bash" shebang, itself), dirname/grep/tr/head
# (install.sh), and touch/grep/tail/sed/mv (the GSETTINGS_FAKE state file dance). Resolved once
# per test session via shutil.which and symlinked into every fake_bin, so a test's PATH never
# needs to fall back to the inherited (host) PATH to find them.
MINIMAL_TOOLS = ("bash", "grep", "sed", "tr", "head", "tail", "dirname", "mv", "touch")


@pytest.fixture(scope="session")
def _minimal_tool_paths() -> dict[str, str]:
    paths = {}
    for name in MINIMAL_TOOLS:
        found = shutil.which(name)
        assert found is not None, f"test environment is missing required tool: {name}"
        paths[name] = found
    return paths


@pytest.fixture
def fake_bin(tmp_path: Path, _minimal_tool_paths: dict[str, str]) -> Path:
    """A directory of fake uv/llmtr/gsettings/ydotool/ydotoold/systemctl (plus symlinks to the
    few real coreutils from ``_minimal_tool_paths``) that becomes the *entire* PATH for anything
    run against it via ``_run``, logging the fakes' argv to ``fake_bin/*.log``. Defaults to a
    "ydotool 1.x, ydotoold active" setup; individual tests remove a binary or set an env var to
    simulate the other states -- removing one here means install.sh truly cannot find it
    anywhere, not just in this directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, real_path in _minimal_tool_paths.items():
        (bin_dir / name).symlink_to(real_path)
    _write_fake(bin_dir / "uv", UV_FAKE)
    _write_fake(bin_dir / "llmtr", LLMTR_FAKE)
    _write_fake(bin_dir / "gsettings", GSETTINGS_FAKE)
    _write_fake(bin_dir / "ydotool", YDOTOOL_FAKE)
    _write_fake(bin_dir / "ydotoold", YDOTOOLD_FAKE)
    _write_fake(bin_dir / "systemctl", SYSTEMCTL_FAKE)
    return bin_dir


def _run(args: list[str], fake_bin: Path, env_extra: dict[str, str] | None = None):
    env = dict(os.environ)
    # PATH is *only* fake_bin -- never the inherited PATH (see module docstring and
    # test_path_does_not_leak_host_directories). Any tool install.sh needs must be a fake or a
    # real one explicitly symlinked into fake_bin by MINIMAL_TOOLS.
    env["PATH"] = str(fake_bin)
    env["FAKE_BIN_LOG"] = str(fake_bin)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=env,
    )


def _gsettings_log(fake_bin: Path) -> str:
    log = fake_bin / "gsettings.log"
    return log.read_text() if log.exists() else ""


def _uv_log(fake_bin: Path) -> str:
    log = fake_bin / "uv.log"
    return log.read_text() if log.exists() else ""


def _set_initial_custom_keybindings(fake_bin: Path, literal: str) -> None:
    """Seed the fake gsettings state as if some other app already owns a shortcut."""
    state = fake_bin / "gsettings_state.txt"
    key = f"{MEDIA_KEYS_SCHEMA} custom-keybindings"
    state.write_text(f"GET::{key}::{literal}\n")


# --- syntax -----------------------------------------------------------------------------------


def test_install_sh_is_valid_bash() -> None:
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SH)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


# --- --dry-run: never touches gsettings/uv for real -------------------------------------------


def test_dry_run_prints_commands_without_running_them(fake_bin: Path) -> None:
    result = _run(["--dry-run"], fake_bin)

    assert result.returncode == 0, result.stderr
    assert "+ uv tool install --force --reinstall" in result.stdout
    assert "+ gsettings set" in result.stdout
    # Read-only lookups (needed to decide what to print) still run for real, but no mutating
    # command does: no "gsettings set" reached the fake script, and uv was never invoked at all.
    gsettings_log_lines = _gsettings_log(fake_bin).splitlines()
    assert not any(line.startswith("gsettings set") for line in gsettings_log_lines)
    assert _uv_log(fake_bin) == ""


def test_dry_run_prints_all_five_bindings(fake_bin: Path) -> None:
    result = _run(["--dry-run"], fake_bin)

    for binding in LLMTR_BINDINGS:
        assert binding.replace("<", r"\<").replace(">", r"\>") in result.stdout or (
            binding in result.stdout
        )


# --- a real run (fakes on PATH): installs and registers five shortcuts -----------------------


def test_install_registers_five_shortcuts_appending_to_existing_list(fake_bin: Path) -> None:
    other_path = f"{BASE_PATH}/other-app/"
    _set_initial_custom_keybindings(fake_bin, f"['{other_path}']")

    result = _run([], fake_bin)
    assert result.returncode == 0, result.stderr

    state = (fake_bin / "gsettings_state.txt").read_text()
    key = f"GET::{MEDIA_KEYS_SCHEMA} custom-keybindings::"
    final_line = next(line for line in state.splitlines() if line.startswith(key))
    final_value = final_line[len(key) :]

    assert other_path in final_value
    for path in LLMTR_PATHS:
        assert path in final_value

    for path, name, args, binding in zip(
        LLMTR_PATHS, LLMTR_NAMES, LLMTR_ARGS, LLMTR_BINDINGS, strict=True
    ):
        schema = f"{MEDIA_KEYS_SCHEMA}.custom-keybinding:{path}"
        assert f"GET::{schema} name::{name}" in state
        assert f"GET::{schema} binding::{binding}" in state
        assert f"GET::{schema} command::" in state
        command_key = f"GET::{schema} command::"
        command_line = next(line for line in state.splitlines() if line.startswith(command_key))
        assert command_line.endswith(f" {args}")
        assert command_line[len(command_key) :].split(" ", 1)[0] == str(fake_bin / "llmtr")


def test_install_runs_uv_tool_install_with_force_reinstall(fake_bin: Path) -> None:
    result = _run([], fake_bin)
    assert result.returncode == 0, result.stderr

    uv_log = _uv_log(fake_bin)
    assert "tool install --force --reinstall" in uv_log
    assert "pip" not in result.stdout.lower()


def test_install_is_idempotent_on_second_run(fake_bin: Path) -> None:
    first = _run([], fake_bin)
    assert first.returncode == 0, first.stderr
    state_after_first = (fake_bin / "gsettings_state.txt").read_text()

    second = _run([], fake_bin)
    assert second.returncode == 0, second.stderr
    state_after_second = (fake_bin / "gsettings_state.txt").read_text()

    key = f"GET::{MEDIA_KEYS_SCHEMA} custom-keybindings::"

    def _final_array(state: str) -> str:
        line = next(line for line in state.splitlines() if line.startswith(key))
        return line[len(key) :]

    first_array = _final_array(state_after_first)
    second_array = _final_array(state_after_second)
    assert first_array == second_array
    for path in LLMTR_PATHS:
        assert second_array.count(path) == 1


def test_install_upgrades_old_four_entry_list_to_five_without_duplicating(
    fake_bin: Path,
) -> None:
    """A pre-M4-show install only ever registered four llmtr shortcuts (no tone-show slot).
    Re-running the upgraded installer must add the fifth entry and leave the other four, plus
    any other app's shortcut, appearing exactly once -- never duplicated."""
    other_path = f"{BASE_PATH}/other-app/"
    old_literal = "[" + ",".join(f"'{p}'" for p in (other_path, *OLD_LLMTR_PATHS)) + "]"
    _set_initial_custom_keybindings(fake_bin, old_literal)

    result = _run([], fake_bin)
    assert result.returncode == 0, result.stderr

    state = (fake_bin / "gsettings_state.txt").read_text()
    key = f"GET::{MEDIA_KEYS_SCHEMA} custom-keybindings::"
    final_line = next(line for line in state.splitlines() if line.startswith(key))
    final_value = final_line[len(key) :]

    assert other_path in final_value
    for path in LLMTR_PATHS:
        assert final_value.count(path) == 1

    tone_show_path = LLMTR_PATHS[4]
    schema = f"{MEDIA_KEYS_SCHEMA}.custom-keybinding:{tone_show_path}"
    assert f"GET::{schema} name::llmtr tone --show" in state
    assert f"GET::{schema} binding::<Shift><Super><Alt>t" in state


def test_install_missing_uv_fails_fast(fake_bin: Path) -> None:
    (fake_bin / "uv").unlink()

    result = _run([], fake_bin)

    assert result.returncode != 0
    assert "uv" in result.stderr


YDOTOOL_NOT_SET_UP = "ydotool >= 1.0 with the ydotoold user service is not set up"


# --- ydotool detection: ydotool_ready / check_ydotool ------------------------------------------


def test_ydotool_missing_warns(fake_bin: Path) -> None:
    (fake_bin / "ydotool").unlink()

    result = _run([], fake_bin)

    assert result.returncode == 0, result.stderr
    assert YDOTOOL_NOT_SET_UP in result.stderr


def test_old_ydotool_without_ydotoold_warns(fake_bin: Path) -> None:
    # Ubuntu's old 0.1.x ydotool package ships the client but no ydotoold daemon at all.
    (fake_bin / "ydotoold").unlink()

    result = _run([], fake_bin)

    assert result.returncode == 0, result.stderr
    assert YDOTOOL_NOT_SET_UP in result.stderr


def test_ydotool_1x_with_active_service_warns_nothing(fake_bin: Path) -> None:
    result = _run([], fake_bin)

    assert result.returncode == 0, result.stderr
    assert YDOTOOL_NOT_SET_UP not in result.stderr
    ydotoold_log = (fake_bin / "ydotoold.log").read_text()
    assert "-V" in ydotoold_log


def test_ydotool_1x_with_inactive_service_warns(fake_bin: Path, tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()

    result = _run(
        [],
        fake_bin,
        env_extra={"FAKE_YDOTOOLD_ACTIVE": "0", "XDG_RUNTIME_DIR": str(runtime_dir)},
    )

    assert result.returncode == 0, result.stderr
    assert YDOTOOL_NOT_SET_UP in result.stderr


def test_with_ydotool_flag_runs_install_ydotool_script(fake_bin: Path) -> None:
    (fake_bin / "ydotool").unlink()

    result = _run(["--dry-run", "--with-ydotool"], fake_bin)

    assert result.returncode == 0, result.stderr
    assert "install-ydotool.sh" in result.stdout


def test_path_does_not_leak_host_directories(
    fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: _run() used to build PATH as ``fake_bin + the inherited PATH``, so deleting
    e.g. ``ydotool``/``ydotoold`` from fake_bin to simulate "missing" still let install.sh find a
    *real* one on the host running the tests (ydotool 1.0.4 lives in /usr/local/bin on the
    target Ubuntu desktop) and the "missing" tests passed in a sandbox with no real ydotool but
    failed on that host. Put a decoy ydotool/ydotoold (claiming v1.0.4, like the real binary)
    into a directory added to the *ambient* PATH -- standing in for a host's real install
    directories -- then delete both from fake_bin and confirm install.sh still reports ydotool as
    not set up, proving the decoy (and the ambient PATH generally) was never reachable."""
    decoy_dir = tmp_path / "host-like-dir"
    decoy_dir.mkdir()
    _write_fake(decoy_dir / "ydotool", YDOTOOL_FAKE)
    _write_fake(decoy_dir / "ydotoold", YDOTOOLD_FAKE)
    monkeypatch.setenv("PATH", f"{decoy_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    (fake_bin / "ydotool").unlink()
    (fake_bin / "ydotoold").unlink()

    result = _run([], fake_bin)

    assert result.returncode == 0, result.stderr
    assert YDOTOOL_NOT_SET_UP in result.stderr


# --- --uninstall: removes only llmtr's shortcuts and the uv tool ------------------------------


def test_uninstall_removes_only_llmtr_shortcuts_and_uv_tool(fake_bin: Path) -> None:
    other_path = f"{BASE_PATH}/other-app/"
    _set_initial_custom_keybindings(fake_bin, f"['{other_path}']")
    install_result = _run([], fake_bin)
    assert install_result.returncode == 0, install_result.stderr

    result = _run(["--uninstall"], fake_bin)
    assert result.returncode == 0, result.stderr

    state = (fake_bin / "gsettings_state.txt").read_text()
    key = f"GET::{MEDIA_KEYS_SCHEMA} custom-keybindings::"
    final_line = next(line for line in state.splitlines() if line.startswith(key))
    final_value = final_line[len(key) :]

    assert other_path in final_value
    for path in LLMTR_PATHS:
        assert path not in final_value

    uv_log = _uv_log(fake_bin)
    assert "tool uninstall llmtr" in uv_log


def test_uninstall_does_not_touch_config_or_ydotool(fake_bin: Path) -> None:
    result = _run(["--uninstall"], fake_bin)
    assert result.returncode == 0, result.stderr
    assert "install-ydotool.sh" not in result.stdout
    assert "config" not in result.stdout.lower()


# --- unknown flags ------------------------------------------------------------------------------


def test_unknown_flag_is_a_usage_error(fake_bin: Path) -> None:
    result = _run(["--bogus-flag"], fake_bin)
    assert result.returncode == 2
    assert "unknown option" in result.stderr
