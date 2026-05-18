# GIS Metadata Assistant

Streamlit prototype for AI-assisted ArcGIS metadata XML generation before GIS datasets are uploaded to ArcGIS Online, ArcGIS Enterprise, or a Geoportal.

The app extracts factual metadata with Python libraries, optionally asks an AI provider to draft descriptive fields, lets a human reviewer edit the record, and generates downloadable `metadata.xml` and `metadata_summary.json` files.

## Version 1 Features

- Shapefile ZIP, GeoJSON, GeoPackage, CSV, and GeoTIFF format detection
- Shapefile ZIP metadata extraction with `.shp`, `.shx`, `.dbf`, and `.prj` checks
- GeoJSON, GeoPackage, CSV coordinate, and GeoTIFF readers
- Standardized metadata dictionary model
- No AI rule-based draft mode
- OpenAI, Claude / Anthropic, and OpenAI-compatible provider modules
- Claude-compatible third-party provider configuration
- Human review form for descriptive, contact, license, lineage, and temporal fields
- ArcGIS metadata XML generation with ISO 19139-style required fields
- Basic XML well-formedness and high-level section validation
- Streamlit downloads for XML and JSON summary

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
streamlit run app.py
```

API keys are optional. The app works with `No AI / rule-based only` selected.

Streamlit Community Cloud selects the Python version in the app's Advanced settings, not from `runtime.txt`. The dependency set is pinned to versions with Python 3.14 wheels, and using Python 3.12 or 3.13 in Advanced settings is also fine.

## API Key Handling

Do not hardcode API keys. Provide them through one of:

- Streamlit sidebar password inputs
- `.streamlit/secrets.toml`
- Environment variables or `.env`

The app does not write API keys to output files.

## Supported Uploads

- `.zip` containing a shapefile
- `.geojson` or `.json`
- `.gpkg`
- `.csv` with coordinate columns or tabular-only metadata
- `.tif` or `.tiff`

## Architecture

`app.py` only controls the Streamlit interface. Extraction, AI drafting, and XML generation live in separate modules:

- `core/` for detection, metadata model, validation, and pipeline orchestration
- `readers/` for dataset-specific extraction
- `ai/` for provider-specific draft generation
- `iso19139/` for XML template, builder, and validator

New formats can be added by creating a new reader that implements `BaseGISReader`. New AI providers can be added by creating a new provider that implements `BaseAIProvider` and registering it in `ai/provider_factory.py`.
