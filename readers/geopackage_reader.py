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
)
from readers.base_reader import BaseGISReader, ReaderError, ReaderSelectionRequired


class GeoPackageReader(BaseGISReader):
    @staticmethod
    def list_layers(file_path: str) -> list[str]:
        try:
            import pyogrio
        except ImportError as exc:
            raise ReaderError("Pyogrio is required to list GeoPackage layers.") from exc
        try:
            layers = pyogrio.list_layers(file_path)
        except Exception as exc:
            raise ReaderError(f"Unable to list GeoPackage layers: {exc}") from exc
        names = []
        for layer in layers:
            if isinstance(layer, str):
                names.append(layer)
            else:
                try:
                    names.append(str(layer[0]))
                except (TypeError, IndexError):
                    names.append(str(layer))
        return names

    def extract_metadata(self, file_path: str, **kwargs) -> dict:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise ReaderError("GeoPandas is required to read GeoPackage uploads.") from exc

        selected_layer = kwargs.get("selected_layer")
        layers = self.list_layers(file_path)
        if not layers:
            raise ReaderError("No layers were found in the GeoPackage.")
        if len(layers) > 1 and not selected_layer:
            raise ReaderSelectionRequired(
                "Multiple GeoPackage layers were found. Select one layer to extract metadata.",
                layers,
            )
        selected_layer = selected_layer or layers[0]
        if selected_layer not in layers:
            raise ReaderError(f"Selected GeoPackage layer was not found: {selected_layer}")

        gdf = gpd.read_file(file_path, layer=selected_layer)
        metadata = create_empty_metadata()
        metadata.update(
            {
                "title": selected_layer.replace("_", " "),
                "file_name": Path(file_path).name,
                "data_format": "GeoPackage",
                "geometry_type": geometry_type_summary(gdf.geometry),
                "feature_count": int(len(gdf)),
                "row_count": int(len(gdf)),
                "bbox": bounds_to_bbox(gdf.total_bounds),
                "fields": dataframe_fields(gdf, exclude_geometry=True),
            }
        )
        metadata.update(crs_to_metadata(gdf.crs))
        if not metadata["crs_name"]:
            metadata["warnings"].append("Coordinate reference system is missing. CRS requires review.")

        plain_df = gdf.drop(columns="geometry", errors="ignore")
        temporal_fields = detect_temporal_fields(plain_df)
        metadata["temporal_fields"] = temporal_fields
        metadata["date_range"] = detect_date_range(plain_df, temporal_fields)
        return normalize_metadata(metadata)
