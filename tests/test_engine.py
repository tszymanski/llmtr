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
