from __future__ import annotations

from datetime import datetime, timezone

from ai.base_provider import BaseAIProvider
from core.metadata_model import normalize_ai_draft


class NoAIProvider(BaseAIProvider):
    def generate_metadata_draft(self, extracted_metadata: dict) -> dict:
        file_name = extracted_metadata.get("file_name") or "Untitled Dataset"
        title = extracted_metadata.get("title") or file_name.rsplit(".", 1)[0].replace("_", " ")
        keywords = [
            extracted_metadata.get("data_format", ""),
            extracted_metadata.get("geometry_type", ""),
            "GIS",
            "geospatial data",
        ]
        draft = {
            "suggested_title": title,
            "abstract": (
                "This geospatial dataset was uploaded for metadata generation. "
                "The abstract requires human review."
            ),
            "purpose": "Needs review.",
            "keywords": [keyword for keyword in keywords if keyword],
            "topic_category": "location",
            "topic_categories": ["location"],
            "resource_language": "eng",
            "resource_character_set": "utf8",
            "citation_created": datetime.now(timezone.utc).date().isoformat(),
            "format_name": extracted_metadata.get("data_format", "") or "Unknown",
            "format_version": infer_format_version(extracted_metadata.get("data_format", "")),
            "metadata_language": "eng",
            "metadata_scope": "dataset",
            "metadata_contact_organization": "Needs review",
            "metadata_contact_individual_name": "Needs review",
            "metadata_contact_position": "Needs review",
            "metadata_contact_role": "pointOfContact",
            "attribute_descriptions": [
                {"field": field.get("name", ""), "description": "Needs review."}
                for field in extracted_metadata.get("fields", [])
            ],
            "lineage_draft": "Needs review.",
            "use_constraints_draft": "Needs review.",
        }
        return normalize_ai_draft(draft)


def infer_format_version(data_format: str) -> str:
    versions = {
        "CSV": "RFC 4180",
        "GeoJSON": "RFC 7946",
        "GeoPackage": "1.3",
        "GeoTIFF": "1.0",
        "Shapefile ZIP": "1.0",
    }
    return versions.get(str(data_format or ""), "Not versioned")
