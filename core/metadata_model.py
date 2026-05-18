from __future__ import annotations

from copy import deepcopy
from typing import Any


def empty_bbox() -> dict[str, float | None]:
    return {"west": None, "south": None, "east": None, "north": None}


def empty_raster_metadata() -> dict[str, Any]:
    return {
        "width": None,
        "height": None,
        "band_count": None,
        "resolution": [],
        "nodata": None,
        "data_type": "",
    }


def empty_ai_draft() -> dict[str, Any]:
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
        "metadata_contact_organization": "",
        "metadata_contact_individual_name": "",
        "metadata_contact_position": "",
        "metadata_contact_role": "pointOfContact",
        "attribute_descriptions": [],
        "lineage_draft": "Needs review.",
        "use_constraints_draft": "Needs review.",
    }


def empty_human_review() -> dict[str, Any]:
    return {
        "final_title": "",
        "final_abstract": "",
        "final_purpose": "",
        "final_keywords": [],
        "topic_category": "",
        "topic_categories": [],
        "resource_language": "",
        "resource_character_set": "",
        "citation_created": "",
        "format_name": "",
        "format_version": "",
        "metadata_language": "",
        "metadata_scope": "",
        "metadata_contact_organization": "",
        "metadata_contact_individual_name": "",
        "metadata_contact_position": "",
        "metadata_contact_role": "",
        "attribute_descriptions": [],
        "creator": "",
        "publisher": "",
        "contact_name": "",
        "contact_email": "",
        "license": "",
        "access_constraints": "",
        "use_constraints": "",
        "lineage": "",
        "data_source": "",
        "publication_date": "",
        "temporal_start": "",
        "temporal_end": "",
    }


def create_empty_metadata() -> dict[str, Any]:
    return {
        "title": "",
        "file_name": "",
        "data_format": "",
        "geometry_type": "",
        "feature_count": None,
        "row_count": None,
        "crs_name": "",
        "crs_wkt": "",
        "epsg_code": "",
        "bbox": empty_bbox(),
        "fields": [],
        "temporal_fields": [],
        "date_range": {"start": "", "end": ""},
        "raster": empty_raster_metadata(),
        "warnings": [],
        "ai_draft": empty_ai_draft(),
        "human_review": empty_human_review(),
    }


def normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    normalized = create_empty_metadata()
    if metadata:
        deep_update(normalized, metadata)

    normalized["bbox"] = normalize_bbox(normalized.get("bbox"))
    normalized["raster"] = normalize_raster(normalized.get("raster"))
    normalized["fields"] = normalize_fields(normalized.get("fields", []))
    normalized["ai_draft"] = normalize_ai_draft(normalized.get("ai_draft"))
    normalized["human_review"] = normalize_human_review(normalized.get("human_review"))
    normalized["warnings"] = list(dict.fromkeys(normalized.get("warnings", [])))
    return normalized


def normalize_ai_draft(draft: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_ai_draft()
    if draft:
        deep_update(normalized, draft)
    normalized["keywords"] = ensure_string_list(normalized.get("keywords"))
    normalized["topic_categories"] = ensure_string_list(normalized.get("topic_categories"))
    if not normalized["topic_categories"] and normalized.get("topic_category"):
        normalized["topic_categories"] = ensure_string_list(normalized.get("topic_category"))
    if normalized["topic_categories"] and not normalized.get("topic_category"):
        normalized["topic_category"] = normalized["topic_categories"][0]
    normalized["attribute_descriptions"] = normalize_attribute_descriptions(
        normalized.get("attribute_descriptions", [])
    )
    return normalized


def normalize_human_review(review: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_human_review()
    if review:
        deep_update(normalized, review)
    normalized["final_keywords"] = ensure_string_list(normalized.get("final_keywords"))
    normalized["topic_categories"] = ensure_string_list(normalized.get("topic_categories"))
    if not normalized["topic_categories"] and normalized.get("topic_category"):
        normalized["topic_categories"] = ensure_string_list(normalized.get("topic_category"))
    if normalized["topic_categories"] and not normalized.get("topic_category"):
        normalized["topic_category"] = normalized["topic_categories"][0]
    normalized["attribute_descriptions"] = normalize_attribute_descriptions(
        normalized.get("attribute_descriptions", [])
    )
    return normalized


def normalize_fields(fields: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_fields = []
    for field in fields or []:
        normalized_fields.append(
            {
                "name": str(field.get("name", "")),
                "type": str(field.get("type", "")),
                "sample_values": ensure_string_list(field.get("sample_values", [])),
                "null_count": field.get("null_count"),
            }
        )
    return normalized_fields


def normalize_attribute_descriptions(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    normalized = []
    for item in items or []:
        field = str(item.get("field", "")).strip()
        description = str(item.get("description", "")).strip()
        if field or description:
            normalized.append({"field": field, "description": description})
    return normalized


def normalize_bbox(bbox: dict[str, Any] | None) -> dict[str, float | None]:
    normalized = empty_bbox()
    if not bbox:
        return normalized
    for key in normalized:
        value = bbox.get(key)
        try:
            normalized[key] = None if value in ("", None) else float(value)
        except (TypeError, ValueError):
            normalized[key] = None
    return normalized


def normalize_raster(raster: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_raster_metadata()
    if raster:
        deep_update(normalized, raster)
    return normalized


def ensure_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def deep_update(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = deepcopy(value)
    return target
