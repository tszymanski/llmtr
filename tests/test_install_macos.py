"""Tests for scripts/install-macos.sh, the macOS branch of install.sh and macos/llmtr.lua.in.

Nothing real runs: every subprocess gets a temp HOME and a PATH made only of fake `uv`/`open`
(and `pgrep`) scripts that log their argv, plus a few real coreutils symlinked in (see
test_install.py for why the host PATH is never inherited). `Hammerspoon.app` is an empty
directory under the temp HOME's Applications.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"
INSTALL_MACOS_SH = REPO_ROOT / "scripts" / "install-macos.sh"
LUA_TEMPLATE = REPO_ROOT / "macos" / "llmtr.lua.in"

REQUIRE_LINE = 'require("llmtr")'

# `uv tool dir --bin` answers with $FAKE_BIN_LOG/uvbin; `uv tool install` creates llmtr there.
UV_FAKE = """\
#!/usr/bin/env bash
echo "uv $*" >> "$FAKE_BIN_LOG/uv.log"
if [[ "$1 $2 $3" == "tool dir --bin" ]]; then
    echo "$FAKE_BIN_LOG/uvbin"
elif [[ "$1 $2" == "tool install" ]]; then
    mkdir -p "$FAKE_BIN_LOG/uvbin"
    printf '#!/bin/sh\\nexit 0\\n' > "$FAKE_BIN_LOG/uvbin/llmtr"
    chmod +x "$FAKE_BIN_LOG/uvbin/llmtr"
fi
exit 0
"""

OPEN_FAKE = """\
#!/usr/bin/env bash
echo "open $*" >> "$FAKE_BIN_LOG/open.log"
exit 0
"""

PGREP_FAKE = """\
#!/usr/bin/env bash
echo "pgrep $*" >> "$FAKE_BIN_LOG/pgrep.log"
exit 0
"""

MINIMAL_TOOLS = ("bash", "grep", "tail", "mkdir", "cat", "dirname", "rm", "uname", "chmod")


def _write_fake(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@dataclass
class Sandbox:
    bin_dir: Path
    home: Path

    @property
    def hs_dir(self) -> Path:
        return self.home / ".hammerspoon"

    @property
    def init_lua(self) -> Path:
        return self.hs_dir / "init.lua"

    @property
    def module(self) -> Path:
        return self.hs_dir / "llmtr.lua"

    def log(self, name: str) -> str:
        path = self.bin_dir / f"{name}.log"
        return path.read_text() if path.exists() else ""

    def run(self, args: list[str], script: Path = INSTALL_MACOS_SH, **env_extra: str):
        env = {
            "PATH": str(self.bin_dir),
            "HOME": str(self.home),
            "FAKE_BIN_LOG": str(self.bin_dir),
            **env_extra,
        }
        return subprocess.run(
            ["bash", str(script), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=env,
        )


def _make_sandbox(root: Path) -> Sandbox:
    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in MINIMAL_TOOLS:
        found = shutil.which(name)
        assert found is not None, f"test environment is missing required tool: {name}"
        (bin_dir / name).symlink_to(found)
    _write_fake(bin_dir / "uv", UV_FAKE)
    _write_fake(bin_dir / "open", OPEN_FAKE)
    home = root / "home"
    (home / "Applications" / "Hammerspoon.app").mkdir(parents=True)
    return Sandbox(bin_dir=bin_dir, home=home)


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    return _make_sandbox(tmp_path)


def _llmtr_bin(sb: Sandbox) -> str:
    return str(sb.bin_dir / "uvbin" / "llmtr")


def test_script_is_valid_bash() -> None:
    for script in (INSTALL_SH, INSTALL_MACOS_SH):
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr


def test_install_writes_module_with_absolute_path(sandbox: Sandbox) -> None:
    result = sandbox.run([])
    assert result.returncode == 0, result.stderr

    text = sandbox.module.read_text()
    assert f'local LLMTR = "{_llmtr_bin(sandbox)}"' in text
    assert "@LLMTR_BIN@" not in text
    assert "tool install --force --reinstall" in sandbox.log("uv")


@pytest.mark.parametrize("bash_compat", ["31", "42", ""])
def test_install_writes_exact_path_with_space_and_ampersand(
    tmp_path: Path, bash_compat: str
) -> None:
    # macOS runs this under bash 3.2; BASH_COMPAT=31 reproduces its quote handling.
    root = tmp_path / "Jan Kowalski & Co"
    root.mkdir()
    sb = _make_sandbox(root)
    env = {"BASH_COMPAT": bash_compat} if bash_compat else {}
    result = sb.run([], **env)
    assert result.returncode == 0, result.stderr

    path = _llmtr_bin(sb)
    assert " " in path and "&" in path
    lines = sb.module.read_text().splitlines()
    llmtr_lines = [line for line in lines if line.startswith("local LLMTR = ")]
    assert len(llmtr_lines) == 1
    assert llmtr_lines[0].split("  --")[0] == f'local LLMTR = "{path}"'
    assert sb.module.read_text().endswith("end)\n")


def test_install_creates_init_lua_when_missing(sandbox: Sandbox) -> None:
    assert not sandbox.hs_dir.exists()
    result = sandbox.run([])
    assert result.returncode == 0, result.stderr
    assert sandbox.init_lua.read_text() == REQUIRE_LINE + "\n"


def test_install_keeps_existing_init_lua_content(sandbox: Sandbox) -> None:
    sandbox.hs_dir.mkdir()
    # No trailing newline on purpose: our line must still start on its own line.
    sandbox.init_lua.write_text('hs.alert.show("mine")\nrequire("other")')
    result = sandbox.run([])
    assert result.returncode == 0, result.stderr
    assert (
        sandbox.init_lua.read_text() == f'hs.alert.show("mine")\nrequire("other")\n{REQUIRE_LINE}\n'
    )


def test_install_adds_require_once_over_two_runs(sandbox: Sandbox) -> None:
    sandbox.hs_dir.mkdir()
    sandbox.init_lua.write_text('print("hi")\n')
    for _ in range(2):
        result = sandbox.run([])
        assert result.returncode == 0, result.stderr
    lines = sandbox.init_lua.read_text().splitlines()
    assert lines.count(REQUIRE_LINE) == 1
    assert lines[0] == 'print("hi")'


def test_install_opens_hammerspoon_and_three_settings_panes(sandbox: Sandbox) -> None:
    result = sandbox.run([])
    assert result.returncode == 0, result.stderr
    open_log = sandbox.log("open")
    assert "open -a Hammerspoon" in open_log
    assert "Privacy_Accessibility" in open_log
    assert "Privacy_Automation" in open_log
    assert "Notifications" in open_log
    assert "Device Control and Data Access" in result.stdout


def test_install_tells_to_reload_when_hammerspoon_is_running(sandbox: Sandbox) -> None:
    _write_fake(sandbox.bin_dir / "pgrep", PGREP_FAKE)
    result = sandbox.run([])
    assert result.returncode == 0, result.stderr
    assert "Reload Config" in result.stdout
    assert "open -a Hammerspoon" not in sandbox.log("open")


def test_dry_run_changes_nothing(sandbox: Sandbox) -> None:
    result = sandbox.run(["--dry-run"])
    assert result.returncode == 0, result.stderr
    assert "+ uv tool install --force --reinstall" in result.stdout
    assert not sandbox.hs_dir.exists()
    assert "tool install" not in sandbox.log("uv")
    assert sandbox.log("open") == ""


def test_missing_uv_gives_clear_message(sandbox: Sandbox) -> None:
    (sandbox.bin_dir / "uv").unlink()
    result = sandbox.run([])
    assert result.returncode != 0
    assert "brew install uv" in result.stderr
    assert not sandbox.hs_dir.exists()


def test_missing_hammerspoon_gives_clear_message(sandbox: Sandbox) -> None:
    if Path("/Applications/Hammerspoon.app").is_dir():
        pytest.skip("real Hammerspoon installed on this machine")
    shutil.rmtree(sandbox.home / "Applications" / "Hammerspoon.app")
    result = sandbox.run([])
    assert result.returncode != 0
    assert "brew install --cask hammerspoon" in result.stderr
    assert sandbox.log("uv") == ""


def test_unknown_option_is_a_usage_error(sandbox: Sandbox) -> None:
    result = sandbox.run(["--bogus"])
    assert result.returncode == 2


def test_uninstall_removes_only_llmtr_line_and_file(sandbox: Sandbox) -> None:
    sandbox.hs_dir.mkdir()
    sandbox.init_lua.write_text(f'print("hi")\n{REQUIRE_LINE}\nrequire("other")\n')
    sandbox.run([])  # install: line already there, module written
    assert sandbox.module.exists()
    other = sandbox.hs_dir / "other.lua"
    other.write_text("return {}\n")

    result = sandbox.run(["--uninstall"])
    assert result.returncode == 0, result.stderr
    assert not sandbox.module.exists()
    assert other.exists()
    assert sandbox.init_lua.read_text() == 'print("hi")\nrequire("other")\n'
    assert "tool uninstall llmtr" in sandbox.log("uv")


def test_uninstall_keeps_init_lua_even_if_empty(sandbox: Sandbox) -> None:
    sandbox.run([])
    assert sandbox.init_lua.read_text() == REQUIRE_LINE + "\n"
    result = sandbox.run(["--uninstall"])
    assert result.returncode == 0, result.stderr
    assert sandbox.init_lua.exists()
    assert sandbox.init_lua.read_text() == ""


def test_uninstall_keeps_trailing_blank_lines(sandbox: Sandbox) -> None:
    sandbox.hs_dir.mkdir()
    sandbox.init_lua.write_text(f'print("hi")\n{REQUIRE_LINE}\n\n\n')
    result = sandbox.run(["--uninstall"])
    assert result.returncode == 0, result.stderr
    assert sandbox.init_lua.read_text() == 'print("hi")\n\n\n'
    assert not (sandbox.hs_dir / "init.lua.tmp").exists()


def test_uninstall_writes_through_symlinked_init_lua(sandbox: Sandbox, tmp_path: Path) -> None:
    sandbox.hs_dir.mkdir()
    target = tmp_path / "dotfiles-init.lua"
    target.write_text(f'print("hi")\n{REQUIRE_LINE}\n')
    sandbox.init_lua.symlink_to(target)
    result = sandbox.run(["--uninstall"])
    assert result.returncode == 0, result.stderr
    assert sandbox.init_lua.is_symlink()
    assert target.read_text() == 'print("hi")\n'


def test_uninstall_without_anything_installed_succeeds(sandbox: Sandbox) -> None:
    result = sandbox.run(["--uninstall"])
    assert result.returncode == 0, result.stderr
    assert not sandbox.hs_dir.exists()


def test_uninstall_dry_run_keeps_files(sandbox: Sandbox) -> None:
    sandbox.run([])
    result = sandbox.run(["--uninstall", "--dry-run"])
    assert result.returncode == 0, result.stderr
    assert sandbox.module.exists()
    assert REQUIRE_LINE in sandbox.init_lua.read_text()
    assert "tool uninstall" not in sandbox.log("uv")


# --- install.sh dispatch ---------------------------------------------------------------------


def test_install_sh_dispatches_to_macos_script_on_darwin(sandbox: Sandbox) -> None:
    result = sandbox.run([], script=INSTALL_SH, LLMTR_UNAME="Darwin")
    assert result.returncode == 0, result.stderr
    assert sandbox.module.exists()
    assert REQUIRE_LINE in sandbox.init_lua.read_text()


def test_install_sh_passes_flags_to_macos_script(sandbox: Sandbox) -> None:
    result = sandbox.run(["--dry-run"], script=INSTALL_SH, LLMTR_UNAME="Darwin")
    assert result.returncode == 0, result.stderr
    assert not sandbox.hs_dir.exists()


def test_install_sh_rejects_unknown_system(sandbox: Sandbox) -> None:
    result = sandbox.run([], script=INSTALL_SH, LLMTR_UNAME="Plan9")
    assert result.returncode != 0
    assert "unsupported system" in result.stderr


# --- the Lua template, checked as text --------------------------------------------------------


def test_lua_template_has_placeholder_and_five_release_bindings() -> None:
    text = LUA_TEMPLATE.read_text()
    assert text.count("@LLMTR_BIN@") == 1
    assert 'local LLMTR = "@LLMTR_BIN@"' in text
    for line in (
        '{ { "ctrl", "alt" },          "t", { "translate" } }',
        '{ { "ctrl", "alt" },          "g", { "fix" } }',
        '{ { "ctrl", "alt" },          "r", { "tone" } }',
        '{ { "shift", "ctrl", "alt" }, "r", { "tone", "--next" } }',
        '{ { "shift", "ctrl", "alt" }, "t", { "tone", "--show" } }',
    ):
        assert line in text
    # pressedfn = nil, releasedfn = fn
    assert "hs.hotkey.bind(b[1], b[2], nil, function()" in text


def test_lua_template_sets_env_and_handles_url_events() -> None:
    text = LUA_TEMPLATE.read_text()
    assert 'env["LLMTR_RUN_ID"] = id' in text
    assert 'env["LC_CTYPE"] = "UTF-8"' in text
    assert 'hs.urlevent.bind("llmtr"' in text
    assert 'params.action == "notify"' in text
    assert 'params.action == "withdraw"' in text
    assert "WITHDRAW_AFTER = 8" in text
    assert "WITHDRAW_AFTER_ERROR = 15" in text


def test_lua_template_keeps_withdraw_timers_referenced() -> None:
    # An unreferenced hs.timer can be garbage collected and then never fires.
    text = LUA_TEMPLATE.read_text()
    assert "local timers = {}" in text
    assert "timers[id] = hs.timer.doAfter(delay, function()" in text
    assert "timers[id] = nil" in text
