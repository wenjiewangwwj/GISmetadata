from __future__ import annotations

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
            "attribute_descriptions": [
                {"field": field.get("name", ""), "description": "Needs review."}
                for field in extracted_metadata.get("fields", [])
            ],
            "lineage_draft": "Needs review.",
            "use_constraints_draft": "Needs review.",
        }
        return normalize_ai_draft(draft)
