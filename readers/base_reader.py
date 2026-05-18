from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ReaderError(Exception):
    """Raised when a dataset cannot be read for metadata extraction."""


class ReaderSelectionRequired(ReaderError):
    """Raised when a dataset contains multiple choices and needs user selection."""

    def __init__(self, message: str, options: list[str]):
        super().__init__(message)
        self.options = options


class BaseGISReader(ABC):
    @abstractmethod
    def extract_metadata(self, file_path: str, **kwargs: Any) -> dict:
        pass
