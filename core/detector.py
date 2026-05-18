from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile


def detect_format(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".zip":
        return "shapefile" if zip_contains_shapefile(path) else "unknown"
    if suffix == ".geojson":
        return "geojson"
    if suffix == ".json":
        return "geojson"
    if suffix == ".gpkg":
        return "geopackage"
    if suffix == ".csv":
        return "csv"
    if suffix in {".tif", ".tiff"}:
        return "raster"
    return "unknown"


def zip_contains_shapefile(file_path: str | Path) -> bool:
    try:
        with ZipFile(file_path) as archive:
            names = [name.lower() for name in archive.namelist()]
    except BadZipFile:
        return False

    shp_bases = {Path(name).with_suffix("").as_posix() for name in names if name.endswith(".shp")}
    shx_bases = {Path(name).with_suffix("").as_posix() for name in names if name.endswith(".shx")}
    dbf_bases = {Path(name).with_suffix("").as_posix() for name in names if name.endswith(".dbf")}
    return bool(shp_bases & shx_bases & dbf_bases)
