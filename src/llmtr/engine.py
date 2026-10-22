"""Model-side pipeline: text in, cleaned result out (owner: M2).

No desktop code here. ``cli.py`` (M4) calls ``plan_job`` -> notify(``progress_text``) ->
``run_job``. Both ``--stdin`` mode and the shortcut flow use exactly this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from llmtr import langdetect, prompts
from llmtr.config import Config, TonePreset
from llmtr.errors import EmptySelection, OllamaError, TextTooLong
from llmtr.ollama_client import ChatClient
from llmtr.prompts import Message


class Mode(StrEnum):
    """The three text modes (``tone --next`` is not a text mode; it has no job)."""

    TRANSLATE = "translate"
    FIX = "fix"
    TONE = "tone"


@dataclass(frozen=True)
class Job:
    """Everything needed for one model call, decided before the call (pure data)."""

    mode: Mode
    model: str
    messages: tuple[Message, ...]
    original: str
    """The captured text, unchanged; used by the post-filter."""
    source_lang: str | None = None
    """translate only: e.g. ``"pl"``."""
    target_lang: str | None = None
    """translate only: e.g. ``"en"``."""
    tone: TonePreset | None = None
    """tone only."""


def plan_job(
    mode: Mode,
    text: str,
    config: Config,
    *,
    tone: TonePreset | None = None,
    quality: bool = False,
    model: str | None = None,
) -> Job:
    """Choose the model and build the prompt (pure, no I/O).

    - model: ``model`` if given, else ``models.translate_quality`` when ``quality`` and mode is
      translate, else ``models.<mode>``;
    - translate: direction from ``langdetect.choose_direction(text, languages.native,
      languages.other)``, messages from ``prompts.build_translate_messages``;
    - fix: ``prompts.build_fix_messages``;
    - tone: ``prompts.build_tone_messages(text, tone)``; ``tone`` is required for this mode
      (``ValueError`` if None; the CLI passes ``config.current_tone(...)``).

    Raises:
        EmptySelection: ``text.strip()`` is empty.
        TextTooLong: ``len(text) > config.ollama.max_chars``.
    """
    if not text.strip():
        raise EmptySelection()
    if len(text) > config.ollama.max_chars:
        raise TextTooLong(len(text), config.ollama.max_chars)

    source_lang: str | None = None
    target_lang: str | None = None
    chosen_tone: TonePreset | None = None

    if mode == Mode.TRANSLATE:
        chosen_model = model or (
            config.models.translate_quality if quality else config.models.translate
        )
        source_lang, target_lang = langdetect.choose_direction(
            text, config.languages.native, config.languages.other
        )
        messages = prompts.build_translate_messages(text, source_lang, target_lang)
    elif mode == Mode.FIX:
        chosen_model = model or config.models.fix
        messages = prompts.build_fix_messages(text)
    elif mode == Mode.TONE:
        if tone is None:
            raise ValueError("tone is required for Mode.TONE")
        chosen_model = model or config.models.tone
        chosen_tone = tone
        messages = prompts.build_tone_messages(text, tone)
    else:
        raise ValueError(f"unknown mode: {mode}")

    return Job(
        mode=mode,
        model=chosen_model,
        messages=tuple(messages),
        original=text,
        source_lang=source_lang,
        target_lang=target_lang,
        tone=chosen_tone,
    )


def progress_text(job: Job) -> tuple[str, str]:
    """``(summary, body)`` for the progress notification, e.g.
    ``("Translating PL → EN…", "translategemma:12b")``, ``("Fixing grammar…", "gemma3")``,
    ``("Rewriting: team…", "gemma3")``.
    """
    if job.mode == Mode.TRANSLATE:
        source = (job.source_lang or "").upper()
        target = (job.target_lang or "").upper()
        return f"Translating {source} → {target}…", job.model
    if job.mode == Mode.FIX:
        return "Fixing grammar…", job.model
    if job.mode == Mode.TONE:
        name = job.tone.name if job.tone else ""
        return f"Rewriting: {name}…", job.model
    raise ValueError(f"unknown mode: {job.mode}")


def run_job(job: Job, client: ChatClient, config: Config) -> str:
    """Call ``client.chat`` with ``options={"temperature", "num_ctx"}`` and ``keep_alive`` from
    ``config.ollama``, then ``prompts.strip_preamble(output, job.original)``.

    Raises whatever the client raises, and ``OllamaError("The model returned no text.")`` if the
    filtered result is empty.
    """
    options = {"temperature": config.ollama.temperature, "num_ctx": config.ollama.num_ctx}
    output = client.chat(
        job.model, job.messages, options=options, keep_alive=config.ollama.keep_alive
    )
    result = prompts.strip_preamble(output, job.original)
    if not result:
        raise OllamaError("The model returned no text.")
    return result


__all__ = ["Job", "Mode", "plan_job", "progress_text", "run_job"]
