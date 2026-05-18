from __future__ import annotations

from typing import Any


def collect_metadata_warnings(metadata: dict[str, Any]) -> list[str]:
    warnings = list(metadata.get("warnings", []))
    if not metadata.get("file_name"):
        warnings.append("File name is missing.")
    if not metadata.get("data_format"):
        warnings.append("Data format is missing.")
    bbox = metadata.get("bbox", {})
    if any(bbox.get(key) is None for key in ("west", "south", "east", "north")):
        warnings.append("Bounding box is incomplete or unavailable.")
    if not metadata.get("crs_name") and metadata.get("data_format") != "CSV":
        warnings.append("Coordinate reference system is missing or unavailable.")
    return list(dict.fromkeys(warnings))
