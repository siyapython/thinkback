"""LLM client: one interface, a fake (offline, deterministic) and a real (Anthropic) version."""

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.prompts.extract_concepts import RETRY_SUFFIX
from app.services.fake_replies import fake_reply

FAKE_MODEL_NAME = "fake-llm-v1"
T = TypeVar("T", bound=BaseModel)
Tier = Literal["strong", "fast"]  # strong -> MODEL_STRONG, fast -> MODEL_FAST


class LLMError(Exception):
    """The LLM could not give us a usable answer."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str


class LLMClient(Protocol):
    def complete(
        self, *, system: str, user: str, max_tokens: int = 4096, tier: Tier = "strong"
    ) -> LLMResult: ...


class FakeLLMClient:
    """Deterministic canned output so everything is testable offline.

    With no `script` it answers the concept-extraction prompt with 10 concepts that point at
    chunk indexes found in the prompt. Tests can pass `script` (a list of raw replies, used
    in order) to simulate malformed or unusual model output.
    """

    def __init__(self, script: list[str] | None = None):
        self._script = list(script) if script is not None else None
        self.calls: list[dict[str, str]] = []

    def complete(
        self, *, system: str, user: str, max_tokens: int = 4096, tier: Tier = "strong"
    ) -> LLMResult:
        self.calls.append({"system": system, "user": user, "tier": tier})
        if self._script is not None:
            if not self._script:
                raise LLMError("FakeLLMClient script is exhausted")
            return LLMResult(text=self._script.pop(0), model=FAKE_MODEL_NAME)
        return LLMResult(text=fake_reply(system, user), model=FAKE_MODEL_NAME)


class AnthropicLLMClient:
    """Real calls through the anthropic SDK: MODEL_STRONG or MODEL_FAST depending on tier."""

    def __init__(self, api_key: str, model_strong: str, model_fast: str):
        if not api_key:
            raise LLMError("LLM_MODE=real but ANTHROPIC_API_KEY is not set in .env")
        import anthropic  # imported lazily so fake mode never needs it

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._models = {"strong": model_strong, "fast": model_fast}

    def complete(
        self, *, system: str, user: str, max_tokens: int = 4096, tier: Tier = "strong"
    ) -> LLMResult:
        model = self._models[tier]
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic API request failed: {type(exc).__name__}") from exc
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(text=text, model=model)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.LLM_MODE == "real":
        return AnthropicLLMClient(
            settings.ANTHROPIC_API_KEY, settings.MODEL_STRONG, settings.MODEL_FAST
        )
    return FakeLLMClient()


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> object:
    """Parse model output as JSON, tolerating markdown fences or a little surrounding prose."""
    cleaned = _FENCE_RE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def complete_json(
    client: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int = 4096,
    tier: Tier = "strong",
) -> tuple[T, LLMResult]:
    """Ask for JSON and validate it. Malformed output gets one retry, then a clear error."""
    problem = ""
    for attempt in (1, 2):
        result = client.complete(
            system=system,
            user=user if attempt == 1 else user + RETRY_SUFFIX,
            max_tokens=max_tokens,
            tier=tier,
        )
        try:
            return schema.model_validate(parse_json_object(result.text)), result
        except (json.JSONDecodeError, ValidationError) as exc:
            problem = type(exc).__name__
    raise LLMError(f"The model returned malformed JSON twice in a row ({problem}); giving up.")
