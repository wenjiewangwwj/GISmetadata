from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from ai.base_provider import AIProviderError, BaseAIProvider
from ai.prompt_builder import SYSTEM_PROMPT, build_user_prompt, parse_ai_json


class ClaudeProvider(BaseAIProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        api_key = self.config.get("api_key")
        model = self.config.get("model") or "claude-sonnet-4-6"
        base_url = normalize_claude_base_url(self.config.get("base_url", ""))
        if not api_key:
            raise AIProviderError("Anthropic API key is missing. Falling back to No AI mode.")

        try:
            from anthropic import Anthropic

            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            client = Anthropic(**client_kwargs)
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


class ClaudeCompatibleProvider(ClaudeProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        if not self.config.get("base_url"):
            raise AIProviderError("Claude-compatible API base URL is missing. Falling back to No AI mode.")
        if not self.config.get("model"):
            raise AIProviderError("Claude-compatible model name is missing. Falling back to No AI mode.")
        return super().generate_metadata_draft(extracted_metadata)


def normalize_claude_base_url(base_url: str) -> str:
    cleaned = str(base_url or "").strip().rstrip("/")
    if not cleaned:
        return ""

    parsed = urlsplit(cleaned)
    normalized_path = parsed.path.rstrip("/")
    lowered_path = normalized_path.lower()
    for suffix in ("/v1/messages", "/messages", "/v1"):
        if lowered_path.endswith(suffix):
            normalized_path = normalized_path[: -len(suffix)] or "/"
            break
    return urlunsplit(parsed._replace(path=normalized_path, query="", fragment="")).rstrip("/")
