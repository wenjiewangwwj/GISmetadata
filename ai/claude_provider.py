from __future__ import annotations

from ai.base_provider import AIProviderError, BaseAIProvider
from ai.prompt_builder import SYSTEM_PROMPT, build_user_prompt, parse_ai_json


class ClaudeProvider(BaseAIProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        api_key = self.config.get("api_key")
        model = self.config.get("model") or "claude-sonnet-4-6"
        if not api_key:
            raise AIProviderError("Anthropic API key is missing. Falling back to No AI mode.")

        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=1800,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(extracted_metadata)}],
            )
            text = "\n".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            )
            return parse_ai_json(text)
        except Exception as exc:
            raise AIProviderError(f"Claude provider error: {exc}") from exc
