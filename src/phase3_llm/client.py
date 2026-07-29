"""LLM API client with retry logic and structured output."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from src.phase1_data.models import Restaurant
from src.phase2_input.schemas import UserPreference
from src.phase3_llm.config import LLMConfig, RETRY_BASE_DELAY_SEC
from src.phase3_llm.exceptions import (
    LLMAuthError,
    LLMEmptyCandidatesError,
    LLMError,
    LLMRateLimitError,
    LLMResponseParseError,
    LLMTimeoutError,
)
from src.phase3_llm.prompt_builder import DEFAULT_TOP_N, build_prompt
from src.phase3_llm.prompt_templates import STRICT_JSON_REMINDER
from src.phase3_llm.response_parser import parse_llm_response
from src.phase3_llm.schemas import LLMResponse, PromptPayload

logger = logging.getLogger(__name__)


class ChatCompleter(Protocol):
    """Protocol for the underlying chat completion API."""

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: float,
        response_format: Optional[dict[str, str]] = None,
    ) -> object: ...


class LLMClient:
    """Groq LLM client via the OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        completer: Optional[ChatCompleter] = None,
    ) -> None:
        self._config = config
        if completer is not None:
            self._completer = completer
        else:
            client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=config.timeout_sec,
            )
            self._completer = client.chat.completions

    @classmethod
    def from_env(cls) -> LLMClient:
        return cls(LLMConfig.from_env())

    def complete(self, payload: PromptPayload, *, strict_json: bool = False) -> str:
        """
        Send a prompt to the LLM and return raw text content.

        Retries on rate limits, server errors, timeouts, and connection errors.
        Does not retry on authentication failures.
        """
        messages = payload.to_messages()
        if strict_json:
            messages = messages + [{"role": "user", "content": STRICT_JSON_REMINDER}]

        last_error: Optional[Exception] = None

        for attempt in range(1, self._config.max_retries + 1):
            try:
                kwargs: dict = {
                    "model": self._config.model,
                    "messages": messages,
                    "temperature": self._config.temperature,
                    "max_tokens": self._config.max_tokens,
                    "timeout": self._config.timeout_sec,
                }
                # JSON mode supported by OpenAI and some compatible providers
                if strict_json:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self._completer.create(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise LLMError("LLM returned empty content.")
                return content.strip()

            except APIStatusError as exc:
                if exc.status_code == 401:
                    raise LLMAuthError(
                        "LLM service authentication failed. Check your API key."
                    ) from exc
                if exc.status_code == 429:
                    last_error = LLMRateLimitError("Rate limit exceeded.")
                elif exc.status_code >= 500:
                    last_error = LLMError(f"LLM provider error ({exc.status_code}).")
                else:
                    raise LLMError(f"LLM request failed: {exc}") from exc

            except APITimeoutError as exc:
                last_error = LLMTimeoutError(
                    f"LLM request timed out after {self._config.timeout_sec}s."
                )
                logger.warning("LLM timeout on attempt %d", attempt)
                if attempt == self._config.max_retries:
                    raise last_error from exc

            except APIConnectionError as exc:
                last_error = LLMError("Network error connecting to LLM service.")
                logger.warning("LLM connection error on attempt %d", attempt)

            except LLMError:
                raise

            except Exception as exc:
                raise LLMError(f"Unexpected LLM error: {exc}") from exc

            if attempt < self._config.max_retries:
                delay = RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1))
                logger.info("Retrying LLM request in %.1fs...", delay)
                time.sleep(delay)

        raise last_error or LLMError("LLM request failed after retries.")

    def recommend(
        self,
        preferences: UserPreference,
        candidates: list[Restaurant],
        *,
        top_n: int = DEFAULT_TOP_N,
    ) -> LLMResponse:
        """
        Build a prompt, call the LLM, and return a parsed LLMResponse.

        Raises:
            LLMEmptyCandidatesError: If candidates is empty.
            LLMResponseParseError: If response cannot be parsed (after one retry).
        """
        if not candidates:
            raise LLMEmptyCandidatesError(
                "Cannot call LLM with zero candidates. Run the filter engine first."
            )

        payload = build_prompt(preferences, candidates, top_n=top_n)
        return self._complete_and_parse(payload)

    def _complete_and_parse(self, payload: PromptPayload) -> LLMResponse:
        try:
            raw = self.complete(payload, strict_json=False)
            return parse_llm_response(raw)
        except LLMResponseParseError as first_error:
            logger.warning("Parse failed, retrying with strict JSON mode: %s", first_error)
            raw = self.complete(payload, strict_json=True)
            try:
                return parse_llm_response(raw)
            except LLMResponseParseError as second_error:
                raise LLMResponseParseError(
                    f"Failed to parse LLM response after retry: {second_error}"
                ) from second_error


class MockLLMClient(LLMClient):
    """Test double that returns a canned response without calling an API."""

    def __init__(
        self,
        responder: Callable[[PromptPayload], str],
        config: Optional[LLMConfig] = None,
    ) -> None:
        mock_config = config or LLMConfig(
            api_key="test-key",
            base_url="http://localhost:9999/v1",
        )
        super().__init__(mock_config)
        self._responder = responder

    def complete(self, payload: PromptPayload, *, strict_json: bool = False) -> str:
        return self._responder(payload)
