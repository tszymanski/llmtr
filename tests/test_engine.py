"""Unit tests for llmtr.engine (owner: M2). Uses FakeChatClient, never calls Ollama."""

from __future__ import annotations

import dataclasses
import os

import pytest

from llmtr.config import Config, TonePreset, normalize_ollama_url
from llmtr.engine import Mode, plan_job, progress_text, run_job
from llmtr.errors import EmptySelection, OllamaError, TextTooLong
from llmtr.fakes import FakeChatClient
from llmtr.ollama_client import OllamaClient

# --- plan_job --------------------------------------------------------------------------------


def test_plan_job_translate_picks_default_model_and_direction() -> None:
    cfg = Config()
    job = plan_job(Mode.TRANSLATE, "Cześć, jak się masz?", cfg)
    assert job.model == cfg.models.translate
    assert (job.source_lang, job.target_lang) == ("pl", "en")
    assert job.original == "Cześć, jak się masz?"


def test_plan_job_translate_quality_picks_quality_model() -> None:
    cfg = Config()
    job = plan_job(Mode.TRANSLATE, "Cześć", cfg, quality=True)
    assert job.model == cfg.models.translate_quality


def test_plan_job_translate_explicit_model_wins() -> None:
    cfg = Config()
    job = plan_job(Mode.TRANSLATE, "Cześć", cfg, quality=True, model="custom-model")
    assert job.model == "custom-model"


def test_plan_job_fix_uses_fix_model_and_builds_messages() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    assert job.model == cfg.models.fix
    assert job.messages[-1]["content"].strip().endswith("</text>")


def test_plan_job_tone_requires_tone() -> None:
    cfg = Config()
    with pytest.raises(ValueError):
        plan_job(Mode.TONE, "some text", cfg)


def test_plan_job_tone_uses_tone_model_and_preset() -> None:
    cfg = Config()
    preset = TonePreset(name="formal", instruction="Be formal.")
    job = plan_job(Mode.TONE, "some text", cfg, tone=preset)
    assert job.model == cfg.models.tone
    assert job.tone == preset


def test_plan_job_empty_text_raises_empty_selection() -> None:
    cfg = Config()
    with pytest.raises(EmptySelection):
        plan_job(Mode.FIX, "   \n  ", cfg)


def test_plan_job_too_long_text_raises_text_too_long() -> None:
    cfg = Config()
    text = "a" * (cfg.ollama.max_chars + 1)
    with pytest.raises(TextTooLong):
        plan_job(Mode.FIX, text, cfg)


# --- progress_text -----------------------------------------------------------------------------


def test_progress_text_translate() -> None:
    cfg = Config()
    job = plan_job(Mode.TRANSLATE, "Cześć", cfg)
    summary, body = progress_text(job)
    assert summary == "Translating PL → EN…"
    assert body == cfg.models.translate


def test_progress_text_fix() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    summary, body = progress_text(job)
    assert summary == "Fixing grammar…"
    assert body == cfg.models.fix


def test_progress_text_tone() -> None:
    cfg = Config()
    preset = TonePreset(name="formal", instruction="Be formal.")
    job = plan_job(Mode.TONE, "some text", cfg, tone=preset)
    summary, body = progress_text(job)
    assert summary == "Rewriting: formal…"
    assert body == cfg.models.tone


# --- run_job -------------------------------------------------------------------------------


def test_run_job_returns_cleaned_result() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    client = FakeChatClient("Here is the corrected text:\nSome text.")
    result = run_job(job, client, cfg)
    assert result == "Some text."


def test_run_job_sends_temperature_and_num_ctx_options() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    client = FakeChatClient("Some text.")
    run_job(job, client, cfg)
    call = client.calls[0]
    assert call.model == cfg.models.fix
    assert call.options == {"temperature": cfg.ollama.temperature, "num_ctx": cfg.ollama.num_ctx}
    assert call.keep_alive == cfg.ollama.keep_alive


def test_run_job_empty_result_raises_ollama_error() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    client = FakeChatClient("   ")
    with pytest.raises(OllamaError):
        run_job(job, client, cfg)


def test_run_job_propagates_client_errors() -> None:
    cfg = Config()
    job = plan_job(Mode.FIX, "some text", cfg)
    client = FakeChatClient(ConnectionError("boom"))
    with pytest.raises(ConnectionError):
        run_job(job, client, cfg)


# --- real Ollama (skipped unless LLMTR_OLLAMA_TESTS=1) --------------------------------------


@pytest.mark.ollama
@pytest.mark.skipif(
    os.environ.get("LLMTR_OLLAMA_TESTS") != "1", reason="set LLMTR_OLLAMA_TESTS=1 to run"
)
def test_translate_pl_to_en_with_real_ollama() -> None:
    url = normalize_ollama_url(os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    cfg = dataclasses.replace(Config(), ollama=dataclasses.replace(Config().ollama, url=url))
    job = plan_job(Mode.TRANSLATE, "Dzień dobry, jak się masz?", cfg)
    client = OllamaClient(cfg.ollama.url, cfg.ollama.timeout)
    result = run_job(job, client, cfg)
    assert result.strip()


# --- v3: cursor engine (M15) -------------------------------------------------------------------


def _cursor_config(**cursor) -> Config:
    return dataclasses.replace(
        Config(), engine="cursor", cursor=dataclasses.replace(Config().cursor, **cursor)
    )


def test_plan_job_cursor_picks_model_limit_and_one_message() -> None:
    from llmtr.prompts import build_cursor_messages

    job = plan_job(Mode.TRANSLATE, "Cześć, jak się masz?", Config(), engine="cursor")
    assert job.engine == "cursor"
    assert job.model == "gpt-5.4-nano"
    assert (job.source_lang, job.target_lang) == ("pl", "en")
    assert list(job.messages) == build_cursor_messages(
        "translate", "Cześć, jak się masz?", source="pl", target="en"
    )
    assert len(job.messages) == 1 and job.messages[0]["role"] == "user"


def test_plan_job_cursor_quality_ignored_and_model_override() -> None:
    assert plan_job(Mode.TRANSLATE, "Hi", Config(), engine="cursor", quality=True).model == (
        "gpt-5.4-nano"
    )
    assert plan_job(Mode.FIX, "Hi", Config(), engine="cursor", model="auto").model == "auto"


def test_plan_job_cursor_tone_and_fix_messages() -> None:
    from llmtr.config import TEAM_TONE
    from llmtr.prompts import build_cursor_messages

    tone = plan_job(Mode.TONE, "Hi all", Config(), engine="cursor", tone=TEAM_TONE)
    assert list(tone.messages) == build_cursor_messages("tone", "Hi all", tone=TEAM_TONE)
    fix = plan_job(Mode.FIX, "Hi all", Config(), engine="cursor")
    assert list(fix.messages) == build_cursor_messages("fix", "Hi all")


def test_plan_job_cursor_uses_cursor_max_chars() -> None:
    cfg = dataclasses.replace(_cursor_config(max_chars=5), ollama=Config().ollama)
    with pytest.raises(TextTooLong) as info:
        plan_job(Mode.FIX, "123456", cfg)
    assert info.value.limit == 5
    # Ollama's limit does not apply to the cursor engine, and vice versa.
    big = "x" * 9000
    ollama_small = dataclasses.replace(
        _cursor_config(max_chars=10000),
        ollama=dataclasses.replace(Config().ollama, max_chars=10),
    )
    assert plan_job(Mode.FIX, big, ollama_small).engine == "cursor"


def test_plan_job_engine_none_follows_config() -> None:
    assert plan_job(Mode.FIX, "Hi", _cursor_config()).engine == "cursor"
    assert plan_job(Mode.FIX, "Hi", _cursor_config(model="m1")).model == "m1"
    assert plan_job(Mode.FIX, "Hi", Config()).engine == "ollama"
    assert plan_job(Mode.FIX, "Hi", _cursor_config(), engine="ollama").model == "gemma3"


def test_progress_text_cursor_body() -> None:
    job = plan_job(Mode.TRANSLATE, "Cześć, jak się masz?", Config(), engine="cursor")
    assert progress_text(job) == ("Translating PL → EN…", "gpt-5.4-nano (Cursor)")
    fix = plan_job(Mode.FIX, "Hi", Config(), engine="cursor")
    assert progress_text(fix) == ("Fixing grammar…", "gpt-5.4-nano (Cursor)")
    assert progress_text(plan_job(Mode.FIX, "Hi", Config()))[1] == "gemma3"


def test_run_job_with_cursor_client_and_fake_transport() -> None:
    from llmtr.cursor_client import CursorClient
    from llmtr.fakes import FakeCursorTransport

    created = {"agent": {"id": "bc-1"}, "run": {"id": "run-1"}}
    result = '{"status": "FINISHED", "text": "Sure, here is the text:\\nHello"}'
    transport = FakeCursorTransport(
        {("POST", "/v1/agents"): created},
        {"/v1/agents/bc-1/runs/run-1/stream": [("result", result)]},
    )
    cleaned: list[str] = []
    cfg = _cursor_config()
    client = CursorClient(cfg.cursor, transport, spawn_cleanup=cleaned.append)
    job = plan_job(Mode.TRANSLATE, "Cześć\n", cfg)
    assert run_job(job, client, cfg) == "Hello\n"
    assert cleaned == ["bc-1"]
