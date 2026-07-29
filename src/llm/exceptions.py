"""Custom exceptions for the LLM layer."""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for LLM failures."""


class LLMAuthError(LLMError):
    """Raised when LLM authentication fails (401)."""


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded after retries."""


class LLMTimeoutError(LLMError):
    """Raised when the LLM request times out."""


class LLMEmptyCandidatesError(LLMError):
    """Raised when recommend() is called with zero candidates."""


class LLMResponseParseError(LLMError):
    """Raised when the LLM response cannot be parsed as valid JSON."""
