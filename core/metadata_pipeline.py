from __future__ import annotations

from typing import Any

from core.detector import detect_format
from core.metadata_model import normalize_metadata
from readers.base_reader import BaseGISReader, ReaderError
from readers.csv_reader import CSVReader
from readers.geojson_reader import GeoJSONReader
from readers.geopackage_reader import GeoPackageReader
from readers.raster_reader import RasterReader
from readers.shapefile_reader import ShapefileReader


READERS: dict[str, type[BaseGISReader]] = {
    "shapefile": ShapefileReader,
    "geojson": GeoJSONReader,
    "geopackage": GeoPackageReader,
    "csv": CSVReader,
    "raster": RasterReader,
}


def detect_dataset_format(file_path: str) -> str:
    return detect_format(file_path)


def list_available_layers(file_path: str, data_format: str | None = None) -> list[str]:
    data_format = data_format or detect_dataset_format(file_path)
    if data_format == "shapefile":
        return ShapefileReader.list_shapefiles(file_path)
    if data_format == "geopackage":
        return GeoPackageReader.list_layers(file_path)
    return []


def list_csv_columns(file_path: str) -> list[str]:
    return CSVReader.list_columns(file_path)


def extract_metadata(file_path: str, data_format: str | None = None, **kwargs: Any) -> dict:
    data_format = data_format or detect_dataset_format(file_path)
    reader_class = READERS.get(data_format)
    if not reader_class:
        raise ReaderError(f"Unsupported file format: {data_format}")
    metadata = reader_class().extract_metadata(file_path, **kwargs)
    metadata["detected_format"] = data_format
    return normalize_metadata(metadata)
