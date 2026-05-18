from __future__ import annotations

from pathlib import Path

from core.metadata_model import create_empty_metadata, normalize_metadata
from core.utils import bounds_to_bbox, crs_to_metadata
from readers.base_reader import BaseGISReader, ReaderError


class RasterReader(BaseGISReader):
    def extract_metadata(self, file_path: str, **kwargs) -> dict:
        try:
            import rasterio
        except ImportError as exc:
            raise ReaderError("Rasterio is required to read GeoTIFF uploads.") from exc

        with rasterio.open(file_path) as src:
            metadata = create_empty_metadata()
            metadata.update(
                {
                    "title": Path(file_path).stem.replace("_", " "),
                    "file_name": Path(file_path).name,
                    "data_format": "GeoTIFF",
                    "bbox": bounds_to_bbox(src.bounds),
                    "raster": {
                        "width": int(src.width),
                        "height": int(src.height),
                        "band_count": int(src.count),
                        "resolution": [float(abs(src.res[0])), float(abs(src.res[1]))],
                        "nodata": src.nodata,
                        "data_type": ", ".join(sorted(set(src.dtypes))),
                    },
                }
            )
            metadata.update(crs_to_metadata(src.crs))
            if not metadata["crs_name"]:
                metadata["warnings"].append("Raster CRS is missing. CRS requires review.")
            return normalize_metadata(metadata)
