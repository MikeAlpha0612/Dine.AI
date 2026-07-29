"""Configuration for LLM integration (Groq by default)."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Groq OpenAI-compatible API
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_MAX_TOKENS = 2048
MAX_RETRIES = 3
RETRY_BASE_DELAY_SEC = 2.0

# Environment variable names
ENV_API_KEY = "GROQ_API_KEY"
ENV_API_KEY_FALLBACK = "OPENAI_API_KEY"  # accepted for OpenAI-SDK compatibility
ENV_BASE_URL = "LLM_BASE_URL"
ENV_MODEL = "LLM_MODEL"
ENV_TEMPERATURE = "LLM_TEMPERATURE"
ENV_TIMEOUT = "LLM_TIMEOUT_SEC"
ENV_MAX_TOKENS = "LLM_MAX_TOKENS"


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


@dataclass(frozen=True)
class LLMConfig:
    """Runtime configuration for the Groq (OpenAI-compatible) LLM client."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    timeout_sec: float = DEFAULT_TIMEOUT_SEC
    max_tokens: int = DEFAULT_MAX_TOKENS
    max_retries: int = MAX_RETRIES

    @classmethod
    def from_env(cls) -> LLMConfig:
        _load_dotenv_if_available()

        api_key = (
            os.getenv(ENV_API_KEY, "").strip()
            or os.getenv(ENV_API_KEY_FALLBACK, "").strip()
        )
        if not api_key:
            raise ValueError(
                f"{ENV_API_KEY} is not set. "
                "Get a key at https://console.groq.com/keys and set GROQ_API_KEY "
                "in your environment or .env file."
            )

        return cls(
            api_key=api_key,
            base_url=os.getenv(ENV_BASE_URL, DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            model=os.getenv(ENV_MODEL, DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            temperature=float(os.getenv(ENV_TEMPERATURE, str(DEFAULT_TEMPERATURE))),
            timeout_sec=float(os.getenv(ENV_TIMEOUT, str(DEFAULT_TIMEOUT_SEC))),
            max_tokens=int(os.getenv(ENV_MAX_TOKENS, str(DEFAULT_MAX_TOKENS))),
        )
