"""Custom exceptions for the data layer."""

from __future__ import annotations


class DataLayerError(Exception):
    """Base exception for data layer failures."""


class DatasetLoadError(DataLayerError):
    """Raised when the dataset cannot be loaded from Hugging Face."""


class DatasetSchemaError(DataLayerError):
    """Raised when the dataset schema does not match expectations."""


class DatasetEmptyError(DataLayerError):
    """Raised when the dataset contains zero rows."""


class RepositoryNotReadyError(DataLayerError):
    """Raised when the repository is queried before data is loaded."""
