from __future__ import annotations

import json
import re
from typing import Any

from core.metadata_model import normalize_ai_draft
from core.utils import safe_json_dumps


SYSTEM_PROMPT = """You are drafting geospatial metadata from extracted dataset facts.

Use only the provided Python-extracted dataset profile.
Fill as many required ArcGIS metadata fields as can be reasonably inferred from file names, field names, formats, counts, coordinates, and dates.
Write a substantive Summary/Purpose and Description/Abstract from the profile. Do not copy generic fallback wording such as "uploaded for metadata generation."
Use cautious wording such as "appears to" when the dataset subject is inferred from field names or sample values.
Do not invent a real person, organization, license, collection method, update frequency, spatial accuracy, attribute accuracy, data source, or lineage.
Only use "Needs review" for fields that truly cannot be inferred, especially contact, organization, position, license, source, and lineage.
Do not use "Needs review" for title, abstract, purpose, tags, topic category, format, language, character set, or metadata scope when the profile contains enough information.
Use ISO language code "eng" and character set "utf8" unless the facts clearly indicate another value.
Use metadata scope "dataset" unless the facts clearly indicate another scope.
Return valid JSON only.
The output must match the requested schema exactly."""


MAX_AI_FIELDS = 80
SUBJECT_STOPWORDS = {
    "a",
    "an",
    "and",
    "area",
    "areas",
    "by",
    "code",
    "data",
    "dataset",
    "date",
    "desc",
    "description",
    "field",
    "file",
    "for",
    "from",
    "gis",
    "id",
    "identifier",
    "in",
    "info",
    "information",
    "layer",
    "name",
    "number",
    "objectid",
    "of",
    "on",
    "shape",
    "status",
    "table",
    "the",
    "to",
    "type",
    "value",
}

TOPIC_HINTS = {
    "transportation": {
        "road",
        "roads",
        "route",
        "routes",
        "street",
        "streets",
        "traffic",
        "transit",
        "rail",
        "bridge",
        "highway",
    },
    "planningCadastre": {
        "parcel",
        "parcels",
        "zoning",
        "district",
        "districts",
        "landuse",
        "land_use",
        "address",
        "addresses",
        "lot",
        "lots",
        "tract",
    },
    "boundaries": {
        "boundary",
        "boundaries",
        "county",
        "municipal",
        "city",
        "state",
        "jurisdiction",
        "precinct",
    },
    "inlandWaters": {
        "water",
        "watershed",
        "river",
        "stream",
        "lake",
        "flood",
        "wetland",
        "drainage",
    },
    "environment": {
        "environment",
        "habitat",
        "soil",
        "conservation",
        "contamination",
        "hazard",
        "landcover",
    },
    "utilitiesCommunication": {
        "utility",
        "utilities",
        "sewer",
        "waterline",
        "pipeline",
        "fiber",
        "telecom",
        "electric",
        "power",
    },
    "structure": {
        "building",
        "buildings",
        "structure",
        "structures",
        "facility",
        "facilities",
        "site",
    },
    "society": {
        "school",
        "schools",
        "population",
        "demographic",
        "census",
        "community",
        "public",
    },
    "health": {
        "health",
        "hospital",
        "clinic",
        "medical",
        "ems",
        "disease",
    },
    "economy": {
        "business",
        "economic",
        "employment",
        "income",
        "tax",
        "sales",
    },
}


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
    profile = build_dataset_profile(extracted_metadata)
    return (
        "Python-extracted dataset profile for metadata drafting:\n"
        f"{safe_json_dumps(profile)}\n\n"
        "Drafting expectations:\n"
        "- suggested_title should be a clean dataset title, not a filename with underscores.\n"
        "- abstract should explain what the records appear to represent, the geometry/format, spatial coverage when available, and notable attributes.\n"
        "- purpose should state practical uses such as mapping, inventory, search, planning, analysis, or public information when supported by the profile.\n"
        "- keywords should include specific subject terms from the title, field names, sample values, format, geometry, and place/coverage hints.\n"
        "- topic_category and topic_categories must use ISO topic category names.\n"
        "- attribute_descriptions should be plain-language descriptions inferred from field names, types, ranges, and samples.\n"
        "- lineage_draft, use_constraints_draft, and contact fields should remain Needs review when source facts are absent.\n\n"
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


def build_dataset_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    fields = metadata.get("fields", []) or []
    return {
        "identity": {
            "title": metadata.get("title", ""),
            "file_name": metadata.get("file_name", ""),
            "data_format": metadata.get("data_format", ""),
            "detected_format": metadata.get("detected_format", ""),
        },
        "spatial_profile": {
            "geometry_type": metadata.get("geometry_type", ""),
            "feature_count": metadata.get("feature_count"),
            "row_count": metadata.get("row_count"),
            "bbox": metadata.get("bbox", {}),
            "crs_name": metadata.get("crs_name", ""),
            "epsg_code": metadata.get("epsg_code", ""),
            "coordinate_fields": metadata.get("coordinate_fields", {}),
            "raster": metadata.get("raster", {}),
        },
        "temporal_profile": {
            "temporal_fields": metadata.get("temporal_fields", []),
            "date_range": metadata.get("date_range", {}),
        },
        "attribute_profile": {
            "field_count": len(fields),
            "fields": [summarize_field_for_ai(field) for field in fields[:MAX_AI_FIELDS]],
            "omitted_field_count": max(0, len(fields) - MAX_AI_FIELDS),
        },
        "inferred_subject_hints": infer_subject_hints(metadata),
        "warnings": metadata.get("warnings", []),
    }


def summarize_field_for_ai(field: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "name": field.get("name", ""),
        "type": field.get("type", ""),
        "null_count": field.get("null_count"),
        "unique_count": field.get("unique_count"),
    }
    if field.get("sample_values"):
        summary["sample_values"] = field.get("sample_values")
    if field.get("top_values"):
        summary["top_values"] = field.get("top_values")
    if field.get("min_value") not in ("", None):
        summary["min_value"] = field.get("min_value")
    if field.get("max_value") not in ("", None):
        summary["max_value"] = field.get("max_value")
    if field.get("mean_value") not in ("", None):
        summary["mean_value"] = field.get("mean_value")
    return summary


def infer_subject_hints(metadata: dict[str, Any]) -> dict[str, Any]:
    fields = metadata.get("fields", []) or []
    text_parts = [
        metadata.get("title", ""),
        metadata.get("file_name", ""),
        metadata.get("data_format", ""),
        metadata.get("geometry_type", ""),
    ]
    for field in fields:
        text_parts.append(str(field.get("name", "")))
        text_parts.extend(str(value) for value in field.get("sample_values", [])[:3])
        for item in field.get("top_values", [])[:3]:
            text_parts.append(str(item.get("value", "")))

    tokens = tokenize_subject_words(" ".join(text_parts))
    topic_scores = {
        topic: sum(1 for token in tokens if token in hints)
        for topic, hints in TOPIC_HINTS.items()
    }
    likely_topics = [
        topic
        for topic, score in sorted(topic_scores.items(), key=lambda item: item[1], reverse=True)
        if score > 0
    ][:3]
    if not likely_topics:
        likely_topics = ["location"]

    return {
        "candidate_subject_terms": tokens[:30],
        "likely_topic_categories": likely_topics,
    }


def tokenize_subject_words(text: str) -> list[str]:
    seen = set()
    tokens = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text):
        for part in re.split(r"[_\W]+", raw.lower()):
            if not part or part in SUBJECT_STOPWORDS or part in seen:
                continue
            seen.add(part)
            tokens.append(part)
    return tokens


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
