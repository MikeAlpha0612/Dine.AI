"""Custom exceptions for the input layer."""

from __future__ import annotations


class InputValidationError(ValueError):
    """Raised when user preference input fails validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        self.field = field
        super().__init__(message)
