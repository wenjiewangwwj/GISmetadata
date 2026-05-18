from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from ai.base_provider import AIProviderError, BaseAIProvider
from ai.prompt_builder import AI_DRAFT_SCHEMA, build_chat_messages, parse_ai_json


OPENAI_ENDPOINT_SUFFIXES = ("/chat/completions", "/responses")
ANTHROPIC_MESSAGES_SUFFIX = "/messages"


class OpenAICompatibleProvider(BaseAIProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        base_url = normalize_openai_compatible_base_url(self.config.get("base_url", ""))
        model = self.config.get("model")
        api_key = self.config.get("api_key") or "not-needed"
        if not base_url:
            raise AIProviderError("Third-party API base URL is missing. Falling back to No AI mode.")
        if not model:
            raise AIProviderError("Third-party model name is missing. Falling back to No AI mode.")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=build_chat_messages(extracted_metadata),
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "metadata_draft",
                            "strict": True,
                            "schema": AI_DRAFT_SCHEMA,
                        },
                    },
                )
            except Exception:
                response = client.chat.completions.create(
                    model=model,
                    messages=build_chat_messages(extracted_metadata),
                    response_format={"type": "json_object"},
                )
            return parse_ai_json(response.choices[0].message.content or "")
        except Exception as exc:
            raise AIProviderError(f"OpenAI-compatible provider error: {exc}") from exc


def normalize_openai_compatible_base_url(base_url: str) -> str:
    """Return an OpenAI-compatible API root, not a concrete endpoint path."""
    cleaned = str(base_url or "").strip().rstrip("/")
    if not cleaned:
        return ""

    parsed = urlsplit(cleaned)
    normalized_path = parsed.path.rstrip("/")
    lowered_path = normalized_path.lower()

    if lowered_path.endswith(ANTHROPIC_MESSAGES_SUFFIX):
        raise AIProviderError(
            "The third-party base URL points to an Anthropic Messages endpoint. "
            "Use the Claude / Anthropic provider for Anthropic, or enter an "
            "OpenAI-compatible API root such as https://provider.example.com/v1."
        )

    for suffix in OPENAI_ENDPOINT_SUFFIXES:
        if lowered_path.endswith(suffix):
            normalized_path = normalized_path[: -len(suffix)] or "/"
            break

    return urlunsplit(parsed._replace(path=normalized_path, query="", fragment="")).rstrip("/")
