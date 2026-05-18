from __future__ import annotations

import json
import re
from typing import Any

from core.metadata_model import normalize_ai_draft
from core.utils import safe_json_dumps


SYSTEM_PROMPT = """You are drafting geospatial metadata from extracted dataset facts.

Use only the provided facts.
Fill as many required ArcGIS metadata fields as can be reasonably inferred from file names, field names, formats, counts, coordinates, and dates.
Do not invent a real person, organization, license, collection method, update frequency, spatial accuracy, attribute accuracy, data source, or lineage.
If a required value cannot be inferred, use a conservative generic value such as "Needs review" instead of leaving it blank.
Use ISO language code "eng" and character set "utf8" unless the facts clearly indicate another value.
Use metadata scope "dataset" unless the facts clearly indicate another scope.
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
        "topic_categories": {"type": "array", "items": {"type": "string"}},
        "resource_language": {"type": "string"},
        "resource_character_set": {"type": "string"},
        "citation_created": {"type": "string"},
        "format_name": {"type": "string"},
        "format_version": {"type": "string"},
        "metadata_language": {"type": "string"},
        "metadata_scope": {"type": "string"},
        "metadata_contact_organization": {"type": "string"},
        "metadata_contact_individual_name": {"type": "string"},
        "metadata_contact_position": {"type": "string"},
        "metadata_contact_role": {"type": "string"},
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
        "topic_categories",
        "resource_language",
        "resource_character_set",
        "citation_created",
        "format_name",
        "format_version",
        "metadata_language",
        "metadata_scope",
        "metadata_contact_organization",
        "metadata_contact_individual_name",
        "metadata_contact_position",
        "metadata_contact_role",
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
        "topic_categories": [],
        "resource_language": "eng",
        "resource_character_set": "utf8",
        "citation_created": "",
        "format_name": "",
        "format_version": "",
        "metadata_language": "eng",
        "metadata_scope": "dataset",
        "metadata_contact_organization": "Needs review",
        "metadata_contact_individual_name": "Needs review",
        "metadata_contact_position": "Needs review",
        "metadata_contact_role": "pointOfContact",
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
