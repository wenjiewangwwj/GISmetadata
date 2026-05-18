from __future__ import annotations

from pathlib import Path

from core.metadata_model import create_empty_metadata, normalize_metadata
from core.utils import dataframe_fields, detect_date_range, detect_temporal_fields
from readers.base_reader import BaseGISReader, ReaderError


LATITUDE_NAMES = {"lat", "latitude", "y", "y_coord", "ycoord", "y_coordinate"}
LONGITUDE_NAMES = {"lon", "lng", "long", "longitude", "x", "x_coord", "xcoord", "x_coordinate"}


class CSVReader(BaseGISReader):
    @staticmethod
    def list_columns(file_path: str) -> list[str]:
        try:
            import pandas as pd
        except ImportError as exc:
            raise ReaderError("Pandas is required to read CSV uploads.") from exc
        return pd.read_csv(file_path, nrows=0).columns.astype(str).tolist()

    def extract_metadata(self, file_path: str, **kwargs) -> dict:
        try:
            import pandas as pd
        except ImportError as exc:
            raise ReaderError("Pandas is required to read CSV uploads.") from exc

        df = pd.read_csv(file_path)
        x_column = kwargs.get("x_column")
        y_column = kwargs.get("y_column")
        detected_x, detected_y = detect_coordinate_columns(df.columns.astype(str).tolist())
        x_column = None if x_column == "Auto-detect" else x_column
        y_column = None if y_column == "Auto-detect" else y_column
        x_column = x_column or detected_x
        y_column = y_column or detected_y

        metadata = create_empty_metadata()
        metadata.update(
            {
                "title": Path(file_path).stem.replace("_", " "),
                "file_name": Path(file_path).name,
                "data_format": "CSV",
                "row_count": int(len(df)),
                "fields": dataframe_fields(df, exclude_geometry=False),
            }
        )

        if x_column and y_column and x_column in df.columns and y_column in df.columns:
            x_values = pd.to_numeric(df[x_column], errors="coerce")
            y_values = pd.to_numeric(df[y_column], errors="coerce")
            valid = x_values.notna() & y_values.notna()
            if valid.any():
                metadata["geometry_type"] = "Point"
                metadata["feature_count"] = int(valid.sum())
                metadata["bbox"] = {
                    "west": float(x_values[valid].min()),
                    "south": float(y_values[valid].min()),
                    "east": float(x_values[valid].max()),
                    "north": float(y_values[valid].max()),
                }
                metadata["coordinate_fields"] = {"x": x_column, "y": y_column}
                metadata["warnings"].append(
                    "Coordinate fields were detected, but CRS was not supplied. CRS requires review."
                )
            else:
                metadata["warnings"].append(
                    "Coordinate fields were selected, but no valid numeric coordinate pairs were found."
                )
        else:
            metadata["warnings"].append(
                "No coordinate fields were detected. Spatial extent cannot be calculated."
            )

        temporal_fields = detect_temporal_fields(df)
        metadata["temporal_fields"] = temporal_fields
        metadata["date_range"] = detect_date_range(df, temporal_fields)
        return normalize_metadata(metadata)


def detect_coordinate_columns(columns: list[str]) -> tuple[str | None, str | None]:
    normalized = {column.lower().strip(): column for column in columns}
    x_column = next((normalized[name] for name in LONGITUDE_NAMES if name in normalized), None)
    y_column = next((normalized[name] for name in LATITUDE_NAMES if name in normalized), None)
    return x_column, y_column
