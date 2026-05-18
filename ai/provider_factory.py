from __future__ import annotations

from ai.base_provider import BaseAIProvider
from ai.claude_provider import ClaudeCompatibleProvider, ClaudeProvider
from ai.no_ai_provider import NoAIProvider
from ai.openai_compatible_provider import OpenAICompatibleProvider
from ai.openai_provider import OpenAIProvider


NO_AI = "No AI / rule-based only"
OPENAI = "OpenAI"
CLAUDE = "Claude / Anthropic"
OPENAI_COMPATIBLE = "OpenAI-compatible third-party API"
CLAUDE_COMPATIBLE = "Claude-compatible third-party API"


def get_ai_provider(provider_name: str, config: dict | None = None) -> BaseAIProvider:
    if provider_name == OPENAI:
        return OpenAIProvider(config)
    if provider_name == CLAUDE:
        return ClaudeProvider(config)
    if provider_name == OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(config)
    if provider_name == CLAUDE_COMPATIBLE:
        return ClaudeCompatibleProvider(config)
    return NoAIProvider(config)


def provider_options() -> list[str]:
    return [NO_AI, OPENAI, CLAUDE, OPENAI_COMPATIBLE, CLAUDE_COMPATIBLE]
