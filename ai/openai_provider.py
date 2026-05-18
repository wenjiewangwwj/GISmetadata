from __future__ import annotations

from ai.base_provider import AIProviderError, BaseAIProvider
from ai.prompt_builder import AI_DRAFT_SCHEMA, build_chat_messages, parse_ai_json


class OpenAIProvider(BaseAIProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        api_key = self.config.get("api_key")
        model = self.config.get("model") or "gpt-5.5-mini"
        if not api_key:
            raise AIProviderError("OpenAI API key is missing. Falling back to No AI mode.")

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
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
            message = response.choices[0].message
            content = getattr(message, "content", "") or ""
            if getattr(message, "refusal", None):
                raise AIProviderError(f"OpenAI refused the request: {message.refusal}")
            return parse_ai_json(content)
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"OpenAI provider error: {exc}") from exc
