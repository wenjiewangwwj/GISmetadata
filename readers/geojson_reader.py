from __future__ import annotations

from pathlib import Path

from core.metadata_model import create_empty_metadata, normalize_metadata
from core.utils import (
    bounds_to_bbox,
    crs_to_metadata,
    dataframe_fields,
    detect_date_range,
    detect_temporal_fields,
    geometry_type_summary,
    read_geojson_has_explicit_crs,
)
from readers.base_reader import BaseGISReader, ReaderError


class GeoJSONReader(BaseGISReader):
    def extract_metadata(self, file_path: str, **kwargs) -> dict:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise ReaderError("GeoPandas is required to read GeoJSON uploads.") from exc

        explicit_crs = read_geojson_has_explicit_crs(file_path)
        gdf = gpd.read_file(file_path)
        metadata = create_empty_metadata()
        metadata.update(
            {
                "title": Path(file_path).stem.replace("_", " "),
                "file_name": Path(file_path).name,
                "data_format": "GeoJSON",
                "geometry_type": geometry_type_summary(gdf.geometry),
                "feature_count": int(len(gdf)),
                "row_count": int(len(gdf)),
                "bbox": bounds_to_bbox(gdf.total_bounds),
                "fields": dataframe_fields(gdf, exclude_geometry=True),
            }
        )
        if explicit_crs:
            metadata.update(crs_to_metadata(gdf.crs))
        else:
            metadata["warnings"].append("CRS not explicitly defined. Needs review.")

        plain_df = gdf.drop(columns="geometry", errors="ignore")
        temporal_fields = detect_temporal_fields(plain_df)
        metadata["temporal_fields"] = temporal_fields
        metadata["date_range"] = detect_date_range(plain_df, temporal_fields)
        return normalize_metadata(metadata)
