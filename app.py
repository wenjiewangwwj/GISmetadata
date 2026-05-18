from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from ai.base_provider import AIProviderError
from ai.no_ai_provider import NoAIProvider
from ai.provider_factory import (
    CLAUDE,
    NO_AI,
    OPENAI,
    OPENAI_COMPATIBLE,
    get_ai_provider,
    provider_options,
)
from core.metadata_model import normalize_metadata
from core.metadata_pipeline import (
    detect_dataset_format,
    extract_metadata,
    list_available_layers,
    list_csv_columns,
)
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
    initialize_state()

    st.title("GIS Metadata Assistant")
    st.caption("AI-assisted ArcGIS metadata XML drafting for GIS datasets before ArcGIS or Geoportal upload.")

    sidebar_state = render_sidebar()
    render_upload_status(sidebar_state)

    if sidebar_state["extract_clicked"]:
        handle_extract(sidebar_state)
    if sidebar_state["ai_clicked"]:
        handle_ai_draft(sidebar_state)
    if sidebar_state["xml_clicked"]:
        handle_xml_generation()

    render_main_sections()


def initialize_state() -> None:
    defaults = {
        "uploaded_signature": None,
        "uploaded_path": "",
        "detected_format": "",
        "available_layers": [],
        "selected_layer": "",
        "csv_columns": [],
        "extracted_metadata": None,
        "xml_text": "",
        "summary_json": "",
        "validation_result": None,
        "ai_draft_ready": False,
        "messages": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_sidebar() -> dict[str, Any]:
    st.sidebar.header("Workflow")
    uploaded_file = st.sidebar.file_uploader(
        "Dataset upload",
        type=["zip", "geojson", "json", "gpkg", "csv", "tif", "tiff"],
    )
    if uploaded_file:
        register_upload(uploaded_file)

    detected_format = st.session_state.get("detected_format", "")
    selected_layer = render_layer_selector(detected_format)
    x_column, y_column = render_csv_coordinate_selectors(detected_format)

    provider_name = st.sidebar.selectbox("AI provider", provider_options(), index=0)
    provider_config = render_provider_config(provider_name)

    st.sidebar.divider()
    extract_clicked = st.sidebar.button(
        "Extract metadata",
        disabled=not bool(st.session_state.get("uploaded_path")),
        use_container_width=True,
    )
    ai_clicked = st.sidebar.button(
        "Generate AI draft",
        disabled=not bool(st.session_state.get("extracted_metadata")),
        use_container_width=True,
    )
    xml_clicked = st.sidebar.button(
        "Generate ArcGIS Metadata XML",
        disabled=not bool(st.session_state.get("extracted_metadata"))
        or not bool(st.session_state.get("ai_draft_ready")),
        use_container_width=True,
    )

    render_sidebar_downloads()

    return {
        "provider_name": provider_name,
        "provider_config": provider_config,
        "extract_clicked": extract_clicked,
        "ai_clicked": ai_clicked,
        "xml_clicked": xml_clicked,
        "selected_layer": selected_layer,
        "x_column": x_column,
        "y_column": y_column,
    }


def register_upload(uploaded_file: Any) -> None:
    signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state.get("uploaded_signature") == signature:
        return

    reset_workflow_state()
    upload_name = f"{uuid.uuid4().hex}_{safe_filename(uploaded_file.name)}"
    upload_path = UPLOAD_DIR / upload_name
    with open(upload_path, "wb") as handle:
        handle.write(uploaded_file.getbuffer())

    detected_format = detect_dataset_format(str(upload_path))
    st.session_state["uploaded_signature"] = signature
    st.session_state["uploaded_path"] = str(upload_path)
    st.session_state["detected_format"] = detected_format
    st.session_state["messages"].append(f"Detected format: {detected_format}")

    if detected_format in {"shapefile", "geopackage"}:
        try:
            st.session_state["available_layers"] = list_available_layers(str(upload_path), detected_format)
        except ReaderError as exc:
            st.session_state["messages"].append(str(exc))
    elif detected_format == "csv":
        try:
            st.session_state["csv_columns"] = list_csv_columns(str(upload_path))
        except ReaderError as exc:
            st.session_state["messages"].append(str(exc))


def reset_workflow_state() -> None:
    for key in (
        "uploaded_path",
        "detected_format",
        "available_layers",
        "selected_layer",
        "csv_columns",
        "extracted_metadata",
        "xml_text",
        "summary_json",
        "validation_result",
        "ai_draft_ready",
        "messages",
    ):
        if key in {"available_layers", "csv_columns", "messages"}:
            st.session_state[key] = []
        elif key == "ai_draft_ready":
            st.session_state[key] = False
        else:
            st.session_state[key] = "" if key != "extracted_metadata" else None


def render_layer_selector(detected_format: str) -> str:
    layers = st.session_state.get("available_layers", [])
    if detected_format not in {"shapefile", "geopackage"} or not layers:
        return ""
    label = "Shapefile layer" if detected_format == "shapefile" else "GeoPackage layer"
    selected = st.sidebar.selectbox(label, layers, index=0)
    st.session_state["selected_layer"] = selected
    return selected


def render_csv_coordinate_selectors(detected_format: str) -> tuple[str, str]:
    if detected_format != "csv":
        return "", ""
    columns = st.session_state.get("csv_columns", [])
    options = ["Auto-detect"] + columns
    x_column = st.sidebar.selectbox("CSV X / longitude field", options, index=0)
    y_column = st.sidebar.selectbox("CSV Y / latitude field", options, index=0)
    return x_column, y_column


def render_provider_config(provider_name: str) -> dict[str, str]:
    if provider_name == NO_AI:
        st.sidebar.info("No API key required.")
        return {}

    if provider_name == OPENAI:
        api_key = st.sidebar.text_input(
            "OpenAI API key",
            type="password",
            placeholder="Uses Streamlit secrets or environment if blank",
        )
        model = st.sidebar.text_input("OpenAI model", value=get_config_value("OPENAI_MODEL", "gpt-5.5-mini"))
        return {"api_key": api_key or get_config_value("OPENAI_API_KEY", ""), "model": model}

    if provider_name == CLAUDE:
        api_key = st.sidebar.text_input(
            "Anthropic API key",
            type="password",
            placeholder="Uses Streamlit secrets or environment if blank",
        )
        model = st.sidebar.text_input(
            "Anthropic model",
            value=get_config_value("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        )
        return {"api_key": api_key or get_config_value("ANTHROPIC_API_KEY", ""), "model": model}

    api_key = st.sidebar.text_input(
        "Third-party API key",
        type="password",
        placeholder="Uses Streamlit secrets or environment if blank",
    )
    base_url = st.sidebar.text_input(
        "Third-party API base URL",
        value=get_config_value("THIRD_PARTY_BASE_URL", ""),
        help=(
            "Use an OpenAI-compatible API root, such as https://provider.example.com/v1. "
            "For Anthropic URLs ending in /messages, choose the Claude / Anthropic provider instead."
        ),
    )
    model = st.sidebar.text_input("Third-party model", value=get_config_value("THIRD_PARTY_MODEL", ""))
    return {
        "api_key": api_key or get_config_value("THIRD_PARTY_API_KEY", ""),
        "base_url": base_url,
        "model": model,
    }


def get_config_value(name: str, default: str = "") -> str:
    try:
        secret_value = st.secrets.get(name)
        if secret_value:
            return str(secret_value)
    except Exception:
        pass
    return os.getenv(name, default)


def render_sidebar_downloads() -> None:
    if st.session_state.get("xml_text"):
        st.sidebar.download_button(
            "Download metadata.xml",
            data=st.session_state["xml_text"],
            file_name="metadata.xml",
            mime="application/xml",
            use_container_width=True,
        )
    if st.session_state.get("summary_json"):
        st.sidebar.download_button(
            "Download metadata_summary.json",
            data=st.session_state["summary_json"],
            file_name="metadata_summary.json",
            mime="application/json",
            use_container_width=True,
        )


def render_upload_status(sidebar_state: dict[str, Any]) -> None:
    uploaded_path = st.session_state.get("uploaded_path")
    detected_format = st.session_state.get("detected_format")
    if not uploaded_path:
        st.info("Upload a GIS dataset to begin.")
        return

    with st.expander("Uploaded File Information", expanded=True):
        st.write(
            {
                "file_name": Path(uploaded_path).name.split("_", 1)[-1],
                "stored_path": uploaded_path,
                "detected_format": detected_format,
                "selected_layer": sidebar_state.get("selected_layer") or None,
            }
        )
        if detected_format == "unknown":
            st.error("Unsupported file format. Upload a shapefile ZIP, GeoJSON, GeoPackage, CSV, or GeoTIFF.")


def handle_extract(sidebar_state: dict[str, Any]) -> None:
    file_path = st.session_state.get("uploaded_path")
    detected_format = st.session_state.get("detected_format")
    if not file_path or detected_format == "unknown":
        st.session_state["messages"].append("Cannot extract metadata from an unsupported file format.")
        return

    try:
        metadata = extract_metadata(
            file_path,
            detected_format,
            selected_layer=sidebar_state.get("selected_layer"),
            x_column=sidebar_state.get("x_column"),
            y_column=sidebar_state.get("y_column"),
        )
        st.session_state["extracted_metadata"] = metadata
        st.session_state["xml_text"] = ""
        st.session_state["summary_json"] = ""
        st.session_state["validation_result"] = None
        st.session_state["ai_draft_ready"] = False
        st.session_state["messages"].append("Metadata extraction completed.")
    except ReaderSelectionRequired as exc:
        st.session_state["available_layers"] = exc.options
        st.session_state["messages"].append(str(exc))
    except ReaderError as exc:
        st.session_state["messages"].append(str(exc))
    except Exception as exc:
        st.session_state["messages"].append(f"Metadata extraction error: {exc}")


def handle_ai_draft(sidebar_state: dict[str, Any]) -> None:
    metadata = st.session_state.get("extracted_metadata")
    if not metadata:
        return

    provider_name = sidebar_state["provider_name"]
    try:
        provider = get_ai_provider(provider_name, sidebar_state["provider_config"])
        draft = provider.generate_metadata_draft(metadata)
        metadata["ai_draft"] = draft
        st.session_state["extracted_metadata"] = normalize_metadata(metadata)
        st.session_state["ai_draft_ready"] = True
        st.session_state["messages"].append(f"Metadata draft generated with {provider_name}.")
        st.rerun()
    except AIProviderError as exc:
        fallback = NoAIProvider({}).generate_metadata_draft(metadata)
        metadata["ai_draft"] = fallback
        st.session_state["extracted_metadata"] = normalize_metadata(metadata)
        st.session_state["ai_draft_ready"] = True
        st.session_state["messages"].append(str(exc))
        st.rerun()
    except Exception as exc:
        fallback = NoAIProvider({}).generate_metadata_draft(metadata)
        metadata["ai_draft"] = fallback
        st.session_state["extracted_metadata"] = normalize_metadata(metadata)
        st.session_state["ai_draft_ready"] = True
        st.session_state["messages"].append(f"AI draft error: {exc}. Falling back to No AI mode.")
        st.rerun()


def handle_xml_generation() -> None:
    metadata = st.session_state.get("extracted_metadata")
    if not metadata:
        return

    try:
        metadata = normalize_metadata(metadata)
        if not metadata.get("ai_draft"):
            metadata["ai_draft"] = NoAIProvider({}).generate_metadata_draft(metadata)
        xml_text = build_iso19139_xml(metadata)
        if not is_xml_text(xml_text):
            raise ValueError("ISO XML builder returned non-XML output.")
        summary_json = safe_json_dumps(metadata)
        validation_result = validate_xml(xml_text)

        (OUTPUT_DIR / "metadata.xml").write_text(xml_text, encoding="utf-8")
        (OUTPUT_DIR / "metadata_summary.json").write_text(summary_json, encoding="utf-8")

        st.session_state["xml_text"] = xml_text
        st.session_state["summary_json"] = summary_json
        st.session_state["validation_result"] = validation_result
        st.session_state["messages"].append("ArcGIS metadata XML generated.")
    except Exception as exc:
        st.session_state["messages"].append(f"XML generation error: {exc}")


def render_main_sections() -> None:
    metadata = st.session_state.get("extracted_metadata")
    if metadata:
        metadata = normalize_metadata(metadata)
        st.session_state["extracted_metadata"] = metadata
        render_extracted_facts(metadata)
        if st.session_state.get("ai_draft_ready"):
            render_ai_draft(metadata)
            render_review_form(metadata)
        else:
            st.info("Generate an AI draft before reviewing fields and creating the XML.")

    render_xml_preview()
    render_warnings_and_errors(metadata)


def render_extracted_facts(metadata: dict[str, Any]) -> None:
    with st.expander("Extracted Dataset Facts", expanded=True):
        st.json(factual_metadata_view(metadata), expanded=2)


def factual_metadata_view(metadata: dict[str, Any]) -> dict[str, Any]:
    hidden = {"ai_draft", "human_review", "crs_wkt"}
    return {key: value for key, value in metadata.items() if key not in hidden}


def render_ai_draft(metadata: dict[str, Any]) -> None:
    with st.expander("AI Metadata Draft", expanded=True):
        st.json(metadata.get("ai_draft", {}), expanded=2)


def render_review_form(metadata: dict[str, Any]) -> None:
    ai_draft = metadata.get("ai_draft", {})
    review = metadata.get("human_review", {})
    topic_categories = sorted(TOPIC_CATEGORIES)
    current_topics = review.get("topic_categories") or review.get("topic_category") or ai_draft.get("topic_categories") or ai_draft.get("topic_category") or ["location"]
    if isinstance(current_topics, str):
        current_topics = [current_topics]
    current_topics = [topic for topic in current_topics if topic in topic_categories] or ["location"]

    with st.expander("Human Review Fields", expanded=True):
        with st.form("human_review_form"):
            final_title = st.text_input(
                "Final title",
                value=review.get("final_title") or ai_draft.get("suggested_title") or metadata.get("title", ""),
            )
            final_abstract = st.text_area(
                "Abstract",
                value=review.get("final_abstract") or ai_draft.get("abstract", ""),
                height=120,
            )
            final_purpose = st.text_area(
                "Purpose",
                value=review.get("final_purpose") or ai_draft.get("purpose", ""),
                height=90,
            )
            final_keywords = st.text_input(
                "Keywords",
                value=", ".join(review.get("final_keywords") or ai_draft.get("keywords", [])),
            )
            selected_topic_categories = st.multiselect(
                "Topic categories",
                topic_categories,
                default=current_topics,
            )

            col1, col2 = st.columns(2)
            with col1:
                creator = st.text_input("Creator", value=review.get("creator", ""))
                contact_name = st.text_input("Contact name", value=review.get("contact_name", ""))
                license_value = st.text_input("License", value=review.get("license", ""))
                publication_date = st.text_input(
                    "Publication date",
                    value=review.get("publication_date", ""),
                    placeholder="YYYY-MM-DD",
                )
                temporal_start = st.text_input(
                    "Temporal start date",
                    value=review.get("temporal_start") or metadata.get("date_range", {}).get("start", ""),
                    placeholder="YYYY-MM-DD",
                )
            with col2:
                publisher = st.text_input("Publisher", value=review.get("publisher", ""))
                contact_email = st.text_input("Contact email", value=review.get("contact_email", ""))
                access_constraints = st.text_input(
                    "Access constraints",
                    value=review.get("access_constraints", ""),
                )
                data_source = st.text_input("Data source", value=review.get("data_source", ""))
                temporal_end = st.text_input(
                    "Temporal end date",
                    value=review.get("temporal_end") or metadata.get("date_range", {}).get("end", ""),
                    placeholder="YYYY-MM-DD",
                )

            st.subheader("ArcGIS Metadata Fields")
            item_col, meta_col, contact_col = st.columns(3)
            with item_col:
                resource_language = st.text_input(
                    "Resource language",
                    value=review.get("resource_language") or ai_draft.get("resource_language", "eng"),
                )
                resource_character_set = st.text_input(
                    "Resource character set",
                    value=review.get("resource_character_set")
                    or ai_draft.get("resource_character_set", "utf8"),
                )
                citation_created = st.text_input(
                    "Citation created",
                    value=review.get("citation_created") or ai_draft.get("citation_created", ""),
                    placeholder="YYYY-MM-DD",
                )
                format_name = st.text_input(
                    "Format name",
                    value=review.get("format_name") or ai_draft.get("format_name") or metadata.get("data_format", ""),
                )
                format_version = st.text_input(
                    "Format version",
                    value=review.get("format_version") or ai_draft.get("format_version", ""),
                )
            with meta_col:
                metadata_language = st.text_input(
                    "Metadata language",
                    value=review.get("metadata_language") or ai_draft.get("metadata_language", "eng"),
                )
                metadata_scope = st.text_input(
                    "Metadata scope",
                    value=review.get("metadata_scope") or ai_draft.get("metadata_scope", "dataset"),
                )
            with contact_col:
                metadata_contact_organization = st.text_input(
                    "Metadata contact organization",
                    value=review.get("metadata_contact_organization")
                    or ai_draft.get("metadata_contact_organization", ""),
                )
                metadata_contact_individual_name = st.text_input(
                    "Metadata contact individual name",
                    value=review.get("metadata_contact_individual_name")
                    or ai_draft.get("metadata_contact_individual_name", ""),
                )
                metadata_contact_position = st.text_input(
                    "Metadata contact position",
                    value=review.get("metadata_contact_position")
                    or ai_draft.get("metadata_contact_position", ""),
                )
                metadata_contact_role = st.text_input(
                    "Metadata contact role",
                    value=review.get("metadata_contact_role")
                    or ai_draft.get("metadata_contact_role", "pointOfContact"),
                )

            use_constraints = st.text_area(
                "Use constraints",
                value=review.get("use_constraints") or ai_draft.get("use_constraints_draft", ""),
                height=90,
            )
            lineage = st.text_area(
                "Lineage",
                value=review.get("lineage") or ai_draft.get("lineage_draft", ""),
                height=90,
            )

            attribute_rows = review.get("attribute_descriptions") or ai_draft.get("attribute_descriptions", [])
            edited_attributes = st.data_editor(
                attribute_rows,
                column_config={
                    "field": st.column_config.TextColumn("Field", disabled=True),
                    "description": st.column_config.TextColumn("Description"),
                },
                num_rows="dynamic",
                use_container_width=True,
                key="attribute_descriptions_editor",
            )

            saved = st.form_submit_button("Save review fields", use_container_width=True)
            if saved:
                metadata["human_review"] = {
                    "final_title": final_title,
                    "final_abstract": final_abstract,
                    "final_purpose": final_purpose,
                    "final_keywords": [item.strip() for item in final_keywords.split(",") if item.strip()],
                    "topic_category": selected_topic_categories[0] if selected_topic_categories else "location",
                    "topic_categories": selected_topic_categories or ["location"],
                    "resource_language": resource_language,
                    "resource_character_set": resource_character_set,
                    "citation_created": citation_created,
                    "format_name": format_name,
                    "format_version": format_version,
                    "metadata_language": metadata_language,
                    "metadata_scope": metadata_scope,
                    "metadata_contact_organization": metadata_contact_organization,
                    "metadata_contact_individual_name": metadata_contact_individual_name,
                    "metadata_contact_position": metadata_contact_position,
                    "metadata_contact_role": metadata_contact_role,
                    "attribute_descriptions": data_editor_records(edited_attributes),
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
                st.session_state["extracted_metadata"] = normalize_metadata(metadata)
                st.session_state["xml_text"] = ""
                st.session_state["summary_json"] = ""
                st.session_state["validation_result"] = None
                st.success("Review fields saved.")


def data_editor_records(value: Any) -> list[dict[str, str]]:
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    if isinstance(value, list):
        return value
    return []


def is_xml_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.lstrip()
    return stripped.startswith("<?xml") or stripped.startswith("<metadata")


def render_xml_preview() -> None:
    with st.expander("Generated ArcGIS Metadata XML Preview", expanded=bool(st.session_state.get("xml_text"))):
        xml_text = st.session_state.get("xml_text")
        if xml_text:
            if not is_xml_text(xml_text):
                st.session_state["xml_text"] = ""
                st.error("Generated XML preview was cleared because it did not contain XML text.")
                return
            st.code(xml_text, language="xml")
            st.download_button(
                "Download metadata.xml",
                data=xml_text,
                file_name="metadata.xml",
                mime="application/xml",
                use_container_width=True,
            )
            if st.session_state.get("summary_json"):
                st.download_button(
                    "Download metadata_summary.json",
                    data=st.session_state["summary_json"],
                    file_name="metadata_summary.json",
                    mime="application/json",
                    use_container_width=True,
                )
        else:
            st.write("Generate ArcGIS metadata XML after extraction, AI drafting, and review.")


def render_warnings_and_errors(metadata: dict[str, Any] | None) -> None:
    with st.expander("Warnings and Errors", expanded=bool(st.session_state.get("messages"))):
        messages = list(dict.fromkeys(st.session_state.get("messages", [])))
        warnings = collect_metadata_warnings(metadata) if metadata else []
        validation_result = st.session_state.get("validation_result")

        for message in messages:
            st.info(message)
        for warning in warnings:
            st.warning(warning)
        if validation_result:
            if validation_result.get("is_well_formed"):
                st.success("XML is well-formed.")
            for warning in validation_result.get("warnings", []):
                st.warning(warning)
            for error in validation_result.get("errors", []):
                st.error(error)
        if not messages and not warnings and not validation_result:
            st.write("No warnings or errors yet.")


if __name__ == "__main__":
    main()
