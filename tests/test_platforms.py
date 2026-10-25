"""Tests for llmtr.platforms (pure)."""

from __future__ import annotations

import sys

from llmtr import platforms
from llmtr.config import KeysConfig


def test_detect_platform_maps_darwin_to_macos() -> None:
    assert platforms.detect_platform("darwin") == "macos"


def test_detect_platform_everything_else_is_linux() -> None:
    for name in ("linux", "win32", "freebsd14", "cygwin"):
        assert platforms.detect_platform(name) == "linux"


def test_detect_platform_default_is_sys_platform() -> None:
    assert platforms.detect_platform() == platforms.detect_platform(sys.platform)


def test_key_defaults_per_platform() -> None:
    assert platforms.key_defaults("linux") is platforms.LINUX_KEY_DEFAULTS
    assert platforms.key_defaults("macos") is platforms.MACOS_KEY_DEFAULTS
    mac = platforms.key_defaults("macos")
    assert (mac.copy, mac.paste, mac.start_delay) == ("cmd+c", "cmd+v", 0.0)


def test_linux_defaults_equal_keys_config_defaults() -> None:
    linux = platforms.key_defaults("linux")
    keys = KeysConfig()
    assert (linux.copy, linux.paste, linux.start_delay) == (
        keys.copy,
        keys.paste,
        keys.start_delay,
    )
