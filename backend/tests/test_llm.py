import json

import pytest
from pydantic import BaseModel

from app.config import Settings
from app.services.llm import (
    FakeLLMClient,
    LLMError,
    complete_json,
    get_llm_client,
    parse_json_object,
)


class Thing(BaseModel):
    n: int


def test_fake_is_deterministic_and_reports_model():
    user = "[chunk 0]\nfoo\n\n[chunk 1]\nbar"
    a = FakeLLMClient().complete(system="s", user=user)
    b = FakeLLMClient().complete(system="s", user=user)
    assert a == b
    assert a.model == "fake-llm-v1"
    concepts = json.loads(a.text)["concepts"]
    assert len(concepts) == 10
    assert {i for c in concepts for i in c["chunk_indexes"]} <= {0, 1}


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json_object('```json\n{"n": 1}\n```') == {"n": 1}
    assert parse_json_object('Sure! {"n": 2} Hope that helps') == {"n": 2}


def test_malformed_then_valid_retries_once():
    fake = FakeLLMClient(script=["not json", '{"n": 3}'])
    parsed, result = complete_json(fake, system="s", user="u", schema=Thing)
    assert parsed.n == 3 and result.model == "fake-llm-v1"
    assert len(fake.calls) == 2
    assert "not valid JSON" in fake.calls[1]["user"]


def test_malformed_twice_raises_clear_error():
    fake = FakeLLMClient(script=["nope", '{"n": "x"}', '{"n": 1}'])
    with pytest.raises(LLMError, match="malformed JSON twice"):
        complete_json(fake, system="s", user="u", schema=Thing)
    assert len(fake.calls) == 2  # exactly one retry


def test_mode_selects_implementation_and_real_needs_key():
    assert isinstance(get_llm_client(Settings(LLM_MODE="fake", _env_file=None)), FakeLLMClient)
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        get_llm_client(Settings(LLM_MODE="real", ANTHROPIC_API_KEY="", _env_file=None))
