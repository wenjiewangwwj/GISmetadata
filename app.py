from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from ai.base_provider import AIProviderError
from ai.no_ai_provider import NoAIProvider
from ai.provider_factory import CLAUDE, NO_AI, OPENAI, OPENAI_COMPATIBLE, get_ai_provider, provider_options
from core.metadata_model import normalize_metadata
from core.metadata_pipeline import detect_dataset_format, extract_metadata, list_available_layers, list_csv_columns
from core.utils import safe_filename, safe_json_dumps
from core.validation import collect_metadata_warnings
from iso19139.xml_builder import TOPIC_CATEGORIES, build_iso19139_xml
from iso19139.xml_validator import validate_xml
from readers.base_reader import ReaderError, ReaderSelectionRequired


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"


def main() -> None:
    load_dotenv()
    UPLOAD_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    st.set_page_config(page_title="GIS Metadata Assistant", layout="wide")
    init_state()

    st.title("GIS Metadata Assistant")
    st.caption("AI-assisted ISO 19139 metadata drafting for GIS datasets before ArcGIS or Geoportal upload.")

    sidebar = render_sidebar()
    if sidebar["extract"]:
        run_extract(sidebar)
    if sidebar["draft"]:
        run_ai_draft(sidebar)
    if sidebar["xml"]:
        run_xml_generation()

    render_upload_info(sidebar)
    render_main()


def init_state() -> None:
    for key, value in {
        "uploaded_signature": None,
        "uploaded_path": "",
        "detected_format": "",
        "layers": [],
        "csv_columns": [],
        "metadata": None,
        "xml_text": "",
        "summary_json": "",
        "validation": None,
        "messages": [],
    }.items():
        st.session_state.setdefault(key, value)


def render_sidebar() -> dict[str, Any]:
    st.sidebar.header("Workflow")
    uploaded = st.sidebar.file_uploader(
        "Dataset upload",
        type=["zip", "geojson", "json", "gpkg", "csv", "tif", "tiff"],
    )
    if uploaded:
        save_upload(uploaded)

    detected = st.session_state.get("detected_format", "")
    selected_layer = ""
    if detected in {"shapefile", "geopackage"} and st.session_state.get("layers"):
        selected_layer = st.sidebar.selectbox("Layer", st.session_state["layers"])

    x_column = y_column = ""
    if detected == "csv":
        options = ["Auto-detect"] + st.session_state.get("csv_columns", [])
        x_column = st.sidebar.selectbox("CSV X / longitude field", options)
        y_column = st.sidebar.selectbox("CSV Y / latitude field", options)

    provider = st.sidebar.selectbox("AI provider", provider_options())
    provider_config = render_provider_config(provider)

    st.sidebar.divider()
    extract = st.sidebar.button("Extract metadata", disabled=not bool(st.session_state.get("uploaded_path")), use_container_width=True)
    draft = st.sidebar.button("Generate AI draft", disabled=not bool(st.session_state.get("metadata")), use_container_width=True)
    xml = st.sidebar.button("Generate ISO 19139 XML", disabled=not bool(st.session_state.get("metadata")), use_container_width=True)

    if st.session_state.get("xml_text"):
        st.sidebar.download_button("Download metadata.xml", st.session_state["xml_text"], "metadata.xml", "application/xml", use_container_width=True)
    if st.session_state.get("summary_json"):
        st.sidebar.download_button("Download metadata_summary.json", st.session_state["summary_json"], "metadata_summary.json", "application/json", use_container_width=True)

    return {
        "provider": provider,
        "provider_config": provider_config,
        "selected_layer": selected_layer,
        "x_column": x_column,
        "y_column": y_column,
        "extract": extract,
        "draft": draft,
        "xml": xml,
    }


def render_provider_config(provider: str) -> dict[str, str]:
    if provider == NO_AI:
        st.sidebar.info("No API key required.")
        return {}
    if provider == OPENAI:
        key = st.sidebar.text_input("OpenAI API key", type="password", placeholder="Uses secrets/env if blank")
        model = st.sidebar.text_input("OpenAI model", value=config_value("OPENAI_MODEL", "gpt-5.5-mini"))
        return {"api_key": key or config_value("OPENAI_API_KEY"), "model": model}
    if provider == CLAUDE:
        key = st.sidebar.text_input("Anthropic API key", type="password", placeholder="Uses secrets/env if blank")
        model = st.sidebar.text_input("Anthropic model", value=config_value("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
        return {"api_key": key or config_value("ANTHROPIC_API_KEY"), "model": model}
    if provider == OPENAI_COMPATIBLE:
        key = st.sidebar.text_input("Third-party API key", type="password", placeholder="Uses secrets/env if blank")
        base_url = st.sidebar.text_input("Third-party API base URL", value=config_value("THIRD_PARTY_BASE_URL"))
        model = st.sidebar.text_input("Third-party model", value=config_value("THIRD_PARTY_MODEL"))
        return {"api_key": key or config_value("THIRD_PARTY_API_KEY"), "base_url": base_url, "model": model}
    return {}


def config_value(name: str, default: str = "") -> str:
    try:
        secret = st.secrets.get(name)
        if secret:
            return str(secret)
    except Exception:
        pass
    return os.getenv(name, default)


def save_upload(uploaded: Any) -> None:
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("uploaded_signature") == signature:
        return
    for key in ("metadata", "xml_text", "summary_json", "validation"):
        st.session_state[key] = None if key == "metadata" else ""
    st.session_state["messages"] = []

    path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_filename(uploaded.name)}"
    with open(path, "wb") as handle:
        handle.write(uploaded.getbuffer())
    detected = detect_dataset_format(str(path))
    st.session_state["uploaded_signature"] = signature
    st.session_state["uploaded_path"] = str(path)
    st.session_state["detected_format"] = detected
    st.session_state["messages"].append(f"Detected format: {detected}")

    try:
        st.session_state["layers"] = list_available_layers(str(path), detected) if detected in {"shapefile", "geopackage"} else []
        st.session_state["csv_columns"] = list_csv_columns(str(path)) if detected == "csv" else []
    except ReaderError as exc:
        st.session_state["messages"].append(str(exc))


def run_extract(sidebar: dict[str, Any]) -> None:
    path = st.session_state.get("uploaded_path")
    detected = st.session_state.get("detected_format")
    if not path or detected == "unknown":
        st.session_state["messages"].append("Unsupported file format.")
        return
    try:
        metadata = extract_metadata(
            path,
            detected,
            selected_layer=sidebar.get("selected_layer"),
            x_column=sidebar.get("x_column"),
            y_column=sidebar.get("y_column"),
        )
        metadata["ai_draft"] = NoAIProvider({}).generate_metadata_draft(metadata)
        st.session_state["metadata"] = normalize_metadata(metadata)
        st.session_state["messages"].append("Metadata extraction completed.")
    except ReaderSelectionRequired as exc:
        st.session_state["layers"] = exc.options
        st.session_state["messages"].append(str(exc))
    except Exception as exc:
        st.session_state["messages"].append(f"Metadata extraction error: {exc}")


def run_ai_draft(sidebar: dict[str, Any]) -> None:
    metadata = st.session_state.get("metadata")
    if not metadata:
        return
    try:
        draft = get_ai_provider(sidebar["provider"], sidebar["provider_config"]).generate_metadata_draft(metadata)
        metadata["ai_draft"] = draft
        st.session_state["metadata"] = normalize_metadata(metadata)
        st.session_state["messages"].append(f"Metadata draft generated with {sidebar['provider']}.")
    except AIProviderError as exc:
        metadata["ai_draft"] = NoAIProvider({}).generate_metadata_draft(metadata)
        st.session_state["metadata"] = normalize_metadata(metadata)
        st.session_state["messages"].append(str(exc))


def run_xml_generation() -> None:
    metadata = st.session_state.get("metadata")
    if not metadata:
        return
    try:
        xml_text = build_iso19139_xml(metadata)
        summary = safe_json_dumps(metadata)
        (OUTPUT_DIR / "metadata.xml").write_text(xml_text, encoding="utf-8")
        (OUTPUT_DIR / "metadata_summary.json").write_text(summary, encoding="utf-8")
        st.session_state["xml_text"] = xml_text
        st.session_state["summary_json"] = summary
        st.session_state["validation"] = validate_xml(xml_text)
        st.session_state["messages"].append("ISO 19139 XML generated.")
    except Exception as exc:
        st.session_state["messages"].append(f"XML generation error: {exc}")


def render_upload_info(sidebar: dict[str, Any]) -> None:
    path = st.session_state.get("uploaded_path")
    if not path:
        st.info("Upload a GIS dataset to begin.")
        return
    with st.expander("Uploaded File Information", expanded=True):
        st.write({
            "file_name": Path(path).name.split("_", 1)[-1],
            "detected_format": st.session_state.get("detected_format"),
            "selected_layer": sidebar.get("selected_layer") or None,
        })


def render_main() -> None:
    metadata = st.session_state.get("metadata")
    if metadata:
        metadata = normalize_metadata(metadata)
        st.session_state["metadata"] = metadata
        with st.expander("Extracted Dataset Facts", expanded=True):
            st.json({k: v for k, v in metadata.items() if k not in {"ai_draft", "human_review", "crs_wkt"}}, expanded=2)
        with st.expander("AI Metadata Draft", expanded=True):
            st.json(metadata.get("ai_draft", {}), expanded=2)
        render_review_form(metadata)

    with st.expander("Generated XML Preview", expanded=bool(st.session_state.get("xml_text"))):
        st.code(st.session_state["xml_text"], language="xml") if st.session_state.get("xml_text") else st.write("Generate ISO 19139 XML after extraction and review.")
    render_warnings(metadata)


def render_review_form(metadata: dict[str, Any]) -> None:
    ai = metadata.get("ai_draft", {})
    review = metadata.get("human_review", {})
    topics = sorted(TOPIC_CATEGORIES)
    topic = review.get("topic_category") or ai.get("topic_category") or "location"
    topic_index = topics.index(topic) if topic in topics else topics.index("location")

    with st.expander("Human Review Fields", expanded=True):
        with st.form("review_form"):
            final_title = st.text_input("Final title", value=review.get("final_title") or ai.get("suggested_title") or metadata.get("title", ""))
            final_abstract = st.text_area("Abstract", value=review.get("final_abstract") or ai.get("abstract", ""), height=120)
            final_purpose = st.text_area("Purpose", value=review.get("final_purpose") or ai.get("purpose", ""), height=80)
            final_keywords = st.text_input("Keywords", value=", ".join(review.get("final_keywords") or ai.get("keywords", [])))
            topic_category = st.selectbox("Topic category", topics, index=topic_index)
            col1, col2 = st.columns(2)
            with col1:
                creator = st.text_input("Creator", value=review.get("creator", ""))
                contact_name = st.text_input("Contact name", value=review.get("contact_name", ""))
                license_value = st.text_input("License", value=review.get("license", ""))
                publication_date = st.text_input("Publication date", value=review.get("publication_date", ""), placeholder="YYYY-MM-DD")
                temporal_start = st.text_input("Temporal start date", value=review.get("temporal_start") or metadata.get("date_range", {}).get("start", ""), placeholder="YYYY-MM-DD")
            with col2:
                publisher = st.text_input("Publisher", value=review.get("publisher", ""))
                contact_email = st.text_input("Contact email", value=review.get("contact_email", ""))
                access_constraints = st.text_input("Access constraints", value=review.get("access_constraints", ""))
                data_source = st.text_input("Data source", value=review.get("data_source", ""))
                temporal_end = st.text_input("Temporal end date", value=review.get("temporal_end") or metadata.get("date_range", {}).get("end", ""), placeholder="YYYY-MM-DD")
            use_constraints = st.text_area("Use constraints", value=review.get("use_constraints") or ai.get("use_constraints_draft", ""), height=80)
            lineage = st.text_area("Lineage", value=review.get("lineage") or ai.get("lineage_draft", ""), height=80)
            attributes = st.data_editor(review.get("attribute_descriptions") or ai.get("attribute_descriptions", []), num_rows="dynamic", use_container_width=True)
            if st.form_submit_button("Save review fields", use_container_width=True):
                metadata["human_review"] = {
                    "final_title": final_title,
                    "final_abstract": final_abstract,
                    "final_purpose": final_purpose,
                    "final_keywords": [item.strip() for item in final_keywords.split(",") if item.strip()],
                    "topic_category": topic_category,
                    "attribute_descriptions": attributes.to_dict("records") if hasattr(attributes, "to_dict") else attributes,
                    "creator": creator,
                    "publisher": publisher,
                    "contact_name": contact_name,
                    "contact_email": contact_email,
                    "license": license_value,
                    "access_constraints": access_constraints,
                    "use_constraints": use_constraints,
                    "lineage": lineage,
                    "data_source": data_source,
                    "publication_date": publication_date,
                    "temporal_start": temporal_start,
                    "temporal_end": temporal_end,
                }
                st.session_state["metadata"] = normalize_metadata(metadata)
                st.session_state["xml_text"] = ""
                st.session_state["summary_json"] = ""
                st.success("Review fields saved.")


def render_warnings(metadata: dict[str, Any] | None) -> None:
    with st.expander("Warnings and Errors", expanded=bool(st.session_state.get("messages"))):
        for message in dict.fromkeys(st.session_state.get("messages", [])):
            st.info(message)
        for warning in collect_metadata_warnings(metadata) if metadata else []:
            st.warning(warning)
        validation = st.session_state.get("validation")
        if validation:
            st.success("XML is well-formed.") if validation.get("is_well_formed") else None
            for warning in validation.get("warnings", []):
                st.warning(warning)
            for error in validation.get("errors", []):
                st.error(error)


if __name__ == "__main__":
    main()
