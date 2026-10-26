"""Command line entry point and wiring (owner: M4; ``build_parser`` is final from M1).

The only module that imports both the model side (config, engine, ollama_client) and the desktop
side (clipboard, keys, notify, lock, selection). Call sequences: ``docs/architecture.md``.

Exit codes: 0 success (also: ``tone --next``, ``tone --show``, a second press that cancelled a
running job, and the cancelled job itself), 1 an ``LlmtrError`` was reported, 2 usage error
(argparse, ``tone --next --stdin``, or ``tone --show --next``).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from llmtr import backends, log
from llmtr.backends import Desktop
from llmtr.clipboard import Clipboard
from llmtr.config import (
    Config,
    State,
    current_tone,
    load_config,
    load_state,
    next_tone,
    save_last_result,
    save_state,
)
from llmtr.engine import Mode, plan_job, progress_text, run_job
from llmtr.errors import Cancelled, EmptySelection, LlmtrError, SecureInputActive
from llmtr.keys import KeySender, resolve_key_pair
from llmtr.lock import RunLock, cancel_running, default_lock_path, install_cancel_handler
from llmtr.notify import Notifier
from llmtr.ollama_client import ChatClient, OllamaClient
from llmtr.platforms import detect_platform
from llmtr.selection import Captured, capture_selection, deliver_result, restore_clipboard

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    """``llmtr [--config PATH] {translate,fix,tone} [--stdin] [--model M] ...``."""
    parser = argparse.ArgumentParser(
        prog="llmtr",
        description="Translate (PL<->EN), fix grammar, or rewrite the tone of the selected "
        "text with a local Ollama model, then paste the result over the selection.",
    )
    parser.add_argument("--config", metavar="PATH", help="config file (default: XDG config)")
    sub = parser.add_subparsers(dest="mode", required=True, metavar="MODE")

    def add_mode(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument(
            "--stdin",
            action="store_true",
            help="read text from stdin and print the result; no clipboard, keys, lock or "
            "notifications",
        )
        p.add_argument("--model", metavar="NAME", help="override the configured model")
        return p

    translate = add_mode(Mode.TRANSLATE, "translate PL<->EN (direction detected)")
    translate.add_argument(
        "--quality", action="store_true", help="use the quality model (translategemma:27b)"
    )
    add_mode(Mode.FIX, "fix grammar and spelling, same language")
    tone = add_mode(Mode.TONE, "rewrite in the current tone preset, same language")
    tone_switch = tone.add_mutually_exclusive_group()
    tone_switch.add_argument(
        "--next",
        action="store_true",
        help="switch to the next tone preset and show its name (no text is processed)",
    )
    tone_switch.add_argument(
        "--show",
        action="store_true",
        help="show the current tone preset's name and instruction (no text is processed)",
    )

    log_parser = sub.add_parser(
        "log",
        help="print the log file path and its recent lines",
        description="print the log file path and its recent lines",
    )
    log_parser.add_argument(
        "--tail",
        type=int,
        default=20,
        metavar="N",
        help="number of recent log lines to print (default: 20)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` (default ``sys.argv[1:]``) and run; returns the exit code.

    Flows (see ``docs/architecture.md``): ``--stdin`` (engine only, errors to stderr),
    ``tone --next`` (state only, no lock), and the shortcut flow (lock, capture, engine,
    deliver, restore). ``LlmtrError`` -> notification (or stderr) + ``EXIT_ERROR``.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code is None:
            return EXIT_OK
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE

    if args.mode == "log":
        return _run_log(args)

    # Defaults first, so a config error below (which has no `config.log` yet) is still logged.
    logger = log.setup_logging(None)

    mode = Mode(args.mode)
    next_flag = getattr(args, "next", False)
    show_flag = getattr(args, "show", False)

    if mode == Mode.TONE and next_flag and args.stdin:
        print("llmtr tone: --next cannot be combined with --stdin", file=sys.stderr)
        return EXIT_USAGE

    platform = detect_platform()
    config_path = Path(args.config) if args.config else None
    try:
        config = load_config(config_path, platform=platform)
    except LlmtrError as exc:
        if logger is not None:
            logger.error(
                "%s: %s (%s)", type(exc).__name__, exc.user_message, exc.detail, exc_info=True
            )
        if args.stdin:
            print(exc.user_message, file=sys.stderr)
        else:
            backends.make_notifier(platform).notify(exc.user_message, urgency="critical")
        return EXIT_ERROR

    logger = log.setup_logging(config.log)

    notifier = None if args.stdin else backends.make_notifier(platform, config.notify.backend)

    if mode == Mode.TONE and next_flag:
        return _run_tone_next(config, notifier, logger=logger)

    if mode == Mode.TONE and show_flag:
        return _run_tone_show(config, notifier, stdin=args.stdin, logger=logger)

    quality = getattr(args, "quality", False)
    model = args.model

    if args.stdin:
        return _run_stdin(mode, config, quality=quality, model=model, logger=logger)

    desktop = backends.make_desktop(platform, keys_config=config.keys)
    return run_shortcut(
        mode, config, notifier, quality=quality, model=model, desktop=desktop, logger=logger
    )


def _run_tone_next(
    config: Config, notifier: Notifier, *, logger: logging.Logger | None = None
) -> int:
    """``llmtr tone --next``: cycle the stored preset and show its name (architecture 3.2).

    Never reached with ``--stdin`` (rejected as a usage error in ``main``), so any unexpected
    exception goes through ``notifier``, logged and reported the same way as the shortcut flow.
    """
    outcome = "ok"
    start = time.monotonic()
    try:
        state = load_state()
        preset = next_tone(config, state)
        save_state(State(tone=preset.name))
        suffix = " (only preset)" if len(config.tone.presets) == 1 else ""
        notifier.notify(f"Tone: {preset.name}{suffix}", preset.instruction)
        return EXIT_OK
    except Exception as exc:
        outcome = f"error:{type(exc).__name__}"
        if logger is not None:
            logger.error("Unexpected error: %s", exc, exc_info=True)
        notifier.notify(f"Unexpected error — see {log.log_path()}", urgency="critical")
        return EXIT_ERROR
    finally:
        if logger is not None:
            logger.info(
                str(
                    log.RunRecord(
                        mode=Mode.TONE.value,
                        outcome=outcome,
                        duration=time.monotonic() - start,
                        flags=("next",),
                    )
                )
            )


def _run_tone_show(
    config: Config, notifier: Notifier | None, *, stdin: bool, logger: logging.Logger | None = None
) -> int:
    """``llmtr tone --show``: display the current preset without changing anything.

    No lock, clipboard, keys or Ollama call, and the state file is left untouched.
    """
    outcome = "ok"
    start = time.monotonic()
    try:
        preset = current_tone(config, load_state())
        presets = config.tone.presets
        index = presets.index(preset) + 1
        total = len(presets)
        if stdin:
            print(f"{preset.name} ({index}/{total}): {preset.instruction}")
        else:
            notifier.notify(f"Tone: {preset.name} ({index}/{total})", preset.instruction)
        return EXIT_OK
    except Exception as exc:
        outcome = f"error:{type(exc).__name__}"
        if logger is not None:
            logger.error("Unexpected error: %s", exc, exc_info=True)
        if stdin:
            print(f"Unexpected error — see {log.log_path()}", file=sys.stderr)
        else:
            notifier.notify(f"Unexpected error — see {log.log_path()}", urgency="critical")
        return EXIT_ERROR
    finally:
        if logger is not None:
            logger.info(
                str(
                    log.RunRecord(
                        mode=Mode.TONE.value,
                        outcome=outcome,
                        duration=time.monotonic() - start,
                        flags=("show",),
                    )
                )
            )


def _run_log(args: argparse.Namespace) -> int:
    """``llmtr log``: print the log file path and its last ``--tail`` lines (architecture n/a).

    No lock, clipboard, keys or notifications; reads whatever file ``log.log_path()`` names.
    """
    path = log.log_path()
    print(path)
    if args.tail > 0 and path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-args.tail :]:
            print(line)
    return EXIT_OK


def _run_stdin(
    mode: Mode,
    config: Config,
    *,
    quality: bool,
    model: str | None,
    logger: logging.Logger | None = None,
) -> int:
    """``--stdin``: read text, run the engine, print the result (architecture 3.3)."""
    text = sys.stdin.read()
    outcome = "ok"
    output_length = 0
    job_model = model
    start = time.monotonic()
    try:
        tone = current_tone(config, load_state()) if mode == Mode.TONE else None
        job = plan_job(mode, text, config, tone=tone, quality=quality, model=model)
        job_model = job.model
        client = OllamaClient(config.ollama.url, config.ollama.timeout)
        result = run_job(job, client, config)
        output_length = len(result)
    except LlmtrError as exc:
        outcome = f"error:{type(exc).__name__}"
        if logger is not None:
            logger.error(
                "%s: %s (%s)", type(exc).__name__, exc.user_message, exc.detail, exc_info=True
            )
        print(exc.user_message, file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        outcome = f"error:{type(exc).__name__}"
        if logger is not None:
            logger.error("Unexpected error: %s", exc, exc_info=True)
        print(f"Unexpected error — see {log.log_path()}", file=sys.stderr)
        return EXIT_ERROR
    else:
        sys.stdout.write(result)
        return EXIT_OK
    finally:
        if logger is not None:
            flags = ("stdin", "quality") if quality else ("stdin",)
            logger.info(
                str(
                    log.RunRecord(
                        mode=mode.value,
                        outcome=outcome,
                        model=job_model,
                        duration=time.monotonic() - start,
                        input_length=len(text),
                        output_length=output_length,
                        flags=flags,
                    )
                )
            )


def _is_plain_empty_capture(exc: LlmtrError) -> bool:
    return (
        isinstance(exc, EmptySelection)
        and exc.used_keystrokes
        and not isinstance(exc, SecureInputActive)
    )


def _with_secure_input(exc: LlmtrError, desktop: Desktop) -> LlmtrError:
    """``SecureInputActive(app)`` if the platform names an app holding Secure Input."""
    try:
        app = desktop.empty_selection_hint()
    except Exception:
        return exc
    return SecureInputActive(app) if app else exc


def run_shortcut(
    mode: Mode,
    config: Config,
    notifier: Notifier,
    *,
    quality: bool = False,
    model: str | None = None,
    desktop: Desktop | None = None,
    clipboard: Clipboard | None = None,
    keys: KeySender | None = None,
    client: ChatClient | None = None,
    lock: RunLock | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    kill: Callable[[int, int], None] | None = None,
    logger: logging.Logger | None = None,
) -> int:
    """The shortcut flow for one text mode (lock -> capture -> engine -> deliver).

    ``desktop`` (default ``make_desktop(keys_config=config.keys)``) bundles the platform's
    clipboard, key sender, focused-app query and messages; ``clipboard``/``keys`` override its
    parts. ``client``/``lock`` default to the real ones and may be replaced with fakes in tests;
    ``sleep``/``monotonic`` default to ``time.sleep``/``time.monotonic`` and are forwarded to
    ``capture_selection``/``deliver_result`` for instant, deterministic tests.
    ``kill`` is forwarded to ``cancel_running`` (default ``os.kill``) so a second-press test never
    signals a real process. ``logger`` (from ``log.setup_logging``) gets one INFO summary line
    at the end of every run that reaches the lock, plus an ERROR line (with traceback) for any
    ``LlmtrError`` other than ``Cancelled``, and for any unexpected exception. See
    ``docs/architecture.md`` section 3.1.
    """
    if desktop is None:
        desktop = backends.make_desktop(detect_platform(), keys_config=config.keys)
    run_lock = lock if lock is not None else RunLock(default_lock_path())
    if not run_lock.acquire():
        cancel_running(run_lock, kill=kill)
        return EXIT_OK

    captured: Captured | None = None
    job_model: str | None = None
    outcome = "ok"
    output_length = 0
    start = monotonic()
    with run_lock:
        install_cancel_handler()
        cb = clipboard
        try:
            cb = clipboard if clipboard is not None else desktop.make_clipboard()
            key_sender = keys if keys is not None else desktop.keys
            pair = resolve_key_pair(config.keys, desktop.focused_app_id())
            captured = capture_selection(
                cb, key_sender, pair, config.keys, sleep=sleep, monotonic=monotonic
            )

            tone = current_tone(config, load_state()) if mode == Mode.TONE else None
            job = plan_job(mode, captured.text, config, tone=tone, quality=quality, model=model)
            job_model = job.model

            if config.notify.enabled:
                notifier.notify(*progress_text(job))

            if client is not None:
                chat_client = client
            else:
                chat_client = OllamaClient(config.ollama.url, config.ollama.timeout)
            result = run_job(job, chat_client, config)
            output_length = len(result)
            save_last_result(result)

            pasted = deliver_result(
                result, captured, cb, key_sender, pair, config.keys, sleep=sleep
            )
            if not pasted:
                notifier.notify(desktop.paste_hint)
            return EXIT_OK
        except LlmtrError as exc:
            if captured is not None and cb is not None:
                restore_clipboard(captured, cb)
            if isinstance(exc, Cancelled):
                outcome = "cancelled"
                notifier.notify(exc.user_message, urgency="normal")
                return EXIT_OK
            if _is_plain_empty_capture(exc):
                # The clipboard is already restored; only now pay for the Secure Input probe.
                exc = _with_secure_input(exc, desktop)
            outcome = f"error:{type(exc).__name__}"
            if logger is not None:
                logger.error(
                    "%s: %s (%s)", type(exc).__name__, exc.user_message, exc.detail, exc_info=True
                )
            notifier.notify(exc.user_message, urgency="critical")
            return EXIT_ERROR
        except Exception as exc:
            if captured is not None and cb is not None:
                restore_clipboard(captured, cb)
            outcome = f"error:{type(exc).__name__}"
            if logger is not None:
                logger.error("Unexpected error: %s", exc, exc_info=True)
            notifier.notify(f"Unexpected error — see {log.log_path()}", urgency="critical")
            return EXIT_ERROR
        finally:
            if logger is not None:
                flags = ("quality",) if quality else ()
                logger.info(
                    str(
                        log.RunRecord(
                            mode=mode.value,
                            outcome=outcome,
                            model=job_model,
                            duration=monotonic() - start,
                            input_length=len(captured.text) if captured is not None else 0,
                            output_length=output_length,
                            used_keystrokes=(
                                captured.used_keystrokes if captured is not None else None
                            ),
                            flags=flags,
                        )
                    )
                )


__all__ = ["EXIT_ERROR", "EXIT_OK", "EXIT_USAGE", "build_parser", "main", "run_shortcut"]
