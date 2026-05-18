from __future__ import annotations

import json
import re
from typing import Any

from core.metadata_model import normalize_ai_draft
from core.utils import safe_json_dumps


SYSTEM_PROMPT = """You are drafting geospatial metadata from extracted dataset facts.

Use only the provided facts.
Do not invent creator, publisher, license, collection method, update frequency, spatial accuracy, attribute accuracy, data source, or lineage.
If information is missing or uncertain, write "Needs review."
Return valid JSON only.
The output must match the requested schema exactly."""


AI_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "suggested_title": {"type": "string"},
        "abstract": {"type": "string"},
        "purpose": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "topic_category": {"type": "string"},
        "attribute_descriptions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["field", "description"],
            },
        },
        "lineage_draft": {"type": "string"},
        "use_constraints_draft": {"type": "string"},
    },
    "required": [
        "suggested_title",
        "abstract",
        "purpose",
        "keywords",
        "topic_category",
        "attribute_descriptions",
        "lineage_draft",
        "use_constraints_draft",
    ],
}


def build_user_prompt(extracted_metadata: dict) -> str:
    return (
        "Extracted dataset facts:\n"
        f"{safe_json_dumps(extracted_metadata)}\n\n"
        "Return only this JSON object shape:\n"
        f"{safe_json_dumps(example_ai_draft())}"
    )


def build_chat_messages(extracted_metadata: dict) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(extracted_metadata)},
    ]


def example_ai_draft() -> dict[str, Any]:
    return {
        "suggested_title": "",
        "abstract": "",
        "purpose": "",
        "keywords": [],
        "topic_category": "",
        "attribute_descriptions": [{"field": "", "description": ""}],
        "lineage_draft": "Needs review.",
        "use_constraints_draft": "Needs review.",
    }


def parse_ai_json(text: str) -> dict[str, Any]:
    cleaned = strip_code_fence(text or "")
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = extract_first_json_object(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("AI response was not a JSON object.")
    return normalize_ai_draft(parsed)


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def extract_first_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
    raise ValueError("AI response was not valid JSON.")
