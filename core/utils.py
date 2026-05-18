from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile


TEMPORAL_NAME_HINTS = (
    "date",
    "time",
    "year",
    "created",
    "updated",
    "modified",
    "start",
    "end",
)


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    return cleaned or "uploaded_dataset"


def make_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            return make_json_safe(value.item())
        except Exception:
            pass
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def safe_json_dumps(value: Any, *, indent: int = 2) -> str:
    return json.dumps(make_json_safe(value), indent=indent, ensure_ascii=False)


def bounds_to_bbox(bounds: Any) -> dict[str, float | None]:
    try:
        west, south, east, north = [float(item) for item in bounds]
    except (TypeError, ValueError):
        return {"west": None, "south": None, "east": None, "north": None}
    return {"west": west, "south": south, "east": east, "north": north}


def dataframe_fields(df: Any, *, exclude_geometry: bool = True, sample_size: int = 5) -> list[dict[str, Any]]:
    fields = []
    for column in df.columns:
        if exclude_geometry and str(column).lower() == "geometry":
            continue
        series = df[column]
        non_null = series.dropna()
        samples = [stringify_sample(value) for value in non_null.head(sample_size).tolist()]
        fields.append(
            {
                "name": str(column),
                "type": str(series.dtype),
                "sample_values": samples,
                "null_count": int(series.isna().sum()),
            }
        )
    return fields


def stringify_sample(value: Any) -> str:
    safe_value = make_json_safe(value)
    if safe_value is None:
        return ""
    text = str(safe_value)
    return text[:250]


def detect_temporal_fields(df: Any) -> list[str]:
    import pandas as pd

    candidates = []
    for column in df.columns:
        if str(column).lower() == "geometry":
            continue
        series = df[column]
        name_has_hint = any(hint in str(column).lower() for hint in TEMPORAL_NAME_HINTS)
        if pd.api.types.is_datetime64_any_dtype(series):
            candidates.append(str(column))
            continue
        if not name_has_hint:
            continue
        non_null = series.dropna().head(100)
        if non_null.empty:
            candidates.append(str(column))
            continue
        parsed = pd.to_datetime(non_null, errors="coerce", utc=True)
        if parsed.notna().mean() >= 0.5:
            candidates.append(str(column))
        elif _looks_like_year_values(non_null):
            candidates.append(str(column))
    return candidates


def detect_date_range(df: Any, temporal_fields: list[str]) -> dict[str, str]:
    import pandas as pd

    parsed_values = []
    for column in temporal_fields:
        if column not in df.columns:
            continue
        series = df[column].dropna()
        if series.empty:
            continue
        if _looks_like_year_values(series):
            series = series.astype(str) + "-01-01"
        parsed = pd.to_datetime(series, errors="coerce", utc=True).dropna()
        if not parsed.empty:
            parsed_values.append(parsed)
    if not parsed_values:
        return {"start": "", "end": ""}
    combined = pd.concat(parsed_values)
    return {
        "start": combined.min().date().isoformat(),
        "end": combined.max().date().isoformat(),
    }


def _looks_like_year_values(series: Any) -> bool:
    values = [str(value).strip() for value in series.dropna().head(100).tolist()]
    if not values:
        return False
    matching = [value for value in values if re.fullmatch(r"(18|19|20|21)\d{2}", value)]
    return len(matching) / len(values) >= 0.7


def crs_to_metadata(crs: Any) -> dict[str, str]:
    if not crs:
        return {"crs_name": "", "crs_wkt": "", "epsg_code": ""}
    crs_name = ""
    crs_wkt = ""
    epsg_code = ""
    try:
        crs_name = str(getattr(crs, "name", "") or crs)
    except Exception:
        crs_name = str(crs)
    try:
        crs_wkt = crs.to_wkt()
    except Exception:
        crs_wkt = ""
    try:
        epsg = crs.to_epsg()
        epsg_code = str(epsg) if epsg else ""
    except Exception:
        epsg_code = ""
    return {"crs_name": crs_name, "crs_wkt": crs_wkt, "epsg_code": epsg_code}


def geometry_type_summary(geometry_series: Any) -> str:
    try:
        unique_types = sorted(
            str(item)
            for item in geometry_series.geom_type.dropna().unique().tolist()
            if str(item) and str(item).lower() != "none"
        )
    except Exception:
        return ""
    return unique_types[0] if len(unique_types) == 1 else ", ".join(unique_types)


def safe_extract_zip(zip_path: str | Path, destination: str | Path) -> None:
    destination_path = Path(destination).resolve()
    with ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination_path / member.filename).resolve()
            if not str(target).startswith(str(destination_path)):
                raise ValueError(f"Unsafe path in ZIP archive: {member.filename}")
        archive.extractall(destination_path)


def read_geojson_has_explicit_crs(file_path: str | Path) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return False
    return isinstance(data, dict) and bool(data.get("crs"))
