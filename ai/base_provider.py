from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProviderError(Exception):
    """Raised when an AI provider cannot generate a metadata draft."""


class BaseAIProvider(ABC):
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        pass
