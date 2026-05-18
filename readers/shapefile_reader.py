from __future__ import annotations

import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from core.metadata_model import create_empty_metadata, normalize_metadata
from core.utils import (
    bounds_to_bbox,
    crs_to_metadata,
    dataframe_fields,
    detect_date_range,
    detect_temporal_fields,
    geometry_type_summary,
    safe_extract_zip,
)
from readers.base_reader import BaseGISReader, ReaderError, ReaderSelectionRequired


class ShapefileReader(BaseGISReader):
    REQUIRED_EXTENSIONS = {".shp", ".shx", ".dbf"}

    @staticmethod
    def list_shapefiles(zip_path: str) -> list[str]:
        try:
            with ZipFile(zip_path) as archive:
                return sorted(
                    name
                    for name in archive.namelist()
                    if name.lower().endswith(".shp") and not name.endswith("/")
                )
        except BadZipFile as exc:
            raise ReaderError("Invalid shapefile ZIP archive.") from exc

    def extract_metadata(self, file_path: str, **kwargs) -> dict:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise ReaderError("GeoPandas is required to read shapefile ZIP uploads.") from exc

        selected_layer = kwargs.get("selected_layer")
        shapefiles = self.list_shapefiles(file_path)
        if not shapefiles:
            raise ReaderError("No .shp file was found in the ZIP archive.")
        if len(shapefiles) > 1 and not selected_layer:
            raise ReaderSelectionRequired(
                "Multiple shapefiles were found. Select one layer to extract metadata.",
                shapefiles,
            )

        selected_layer = selected_layer or shapefiles[0]
        if selected_layer not in shapefiles:
            raise ReaderError(f"Selected shapefile was not found in the ZIP: {selected_layer}")

        with tempfile.TemporaryDirectory() as temp_dir:
            safe_extract_zip(file_path, temp_dir)
            shp_path = (Path(temp_dir) / selected_layer).resolve()
            self._validate_required_files(shp_path)

            gdf = gpd.read_file(shp_path)
            metadata = create_empty_metadata()
            metadata.update(
                {
                    "title": shp_path.stem.replace("_", " "),
                    "file_name": Path(file_path).name,
                    "data_format": "Shapefile ZIP",
                    "geometry_type": geometry_type_summary(gdf.geometry),
                    "feature_count": int(len(gdf)),
                    "row_count": int(len(gdf)),
                    "bbox": bounds_to_bbox(gdf.total_bounds),
                    "fields": dataframe_fields(gdf, exclude_geometry=True),
                }
            )
            metadata.update(crs_to_metadata(gdf.crs))

            plain_df = gdf.drop(columns="geometry", errors="ignore")
            temporal_fields = detect_temporal_fields(plain_df)
            metadata["temporal_fields"] = temporal_fields
            metadata["date_range"] = detect_date_range(plain_df, temporal_fields)

            prj_path = shp_path.with_suffix(".prj")
            if not prj_path.exists():
                metadata["warnings"].append(
                    "Coordinate reference system file (.prj) is missing. CRS requires review."
                )
            if not metadata["crs_name"]:
                metadata["warnings"].append("Coordinate reference system is missing. CRS requires review.")

            return normalize_metadata(metadata)

    def _validate_required_files(self, shp_path: Path) -> None:
        missing = [
            ext
            for ext in sorted(self.REQUIRED_EXTENSIONS)
            if not shp_path.with_suffix(ext).exists()
        ]
        if missing:
            missing_text = ", ".join(missing)
            raise ReaderError(f"Invalid shapefile ZIP. Missing required file(s): {missing_text}.")
