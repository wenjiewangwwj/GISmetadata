from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from lxml import etree

from core.metadata_model import ensure_string_list, normalize_metadata


XML_NS = "http://www.w3.org/XML/1998/namespace"
ARCGIS_FORMAT_VERSION = "1.0"

TOPIC_CATEGORIES = {
    "farming",
    "biota",
    "boundaries",
    "climatologyMeteorologyAtmosphere",
    "economy",
    "elevation",
    "environment",
    "geoscientificInformation",
    "health",
    "imageryBaseMapsEarthCover",
    "intelligenceMilitary",
    "inlandWaters",
    "location",
    "oceans",
    "planningCadastre",
    "society",
    "structure",
    "transportation",
    "utilitiesCommunication",
}

TOPIC_CATEGORY_CODES = {
    "farming": "001",
    "biota": "002",
    "boundaries": "003",
    "climatologyMeteorologyAtmosphere": "004",
    "economy": "005",
    "elevation": "006",
    "environment": "007",
    "geoscientificInformation": "008",
    "health": "009",
    "imageryBaseMapsEarthCover": "010",
    "intelligenceMilitary": "011",
    "inlandWaters": "012",
    "location": "013",
    "oceans": "014",
    "planningCadastre": "015",
    "society": "016",
    "structure": "017",
    "transportation": "018",
    "utilitiesCommunication": "019",
}

ROLE_CODES = {
    "custodian": "001",
    "owner": "002",
    "user": "003",
    "distributor": "004",
    "originator": "005",
    "pointOfContact": "006",
    "principalInvestigator": "007",
    "processor": "008",
    "publisher": "009",
    "author": "010",
}

SCOPE_CODES = {
    "dataset": "005",
    "series": "006",
    "service": "014",
}

LANGUAGE_ALIASES = {
    "en": "eng",
    "eng": "eng",
    "english": "eng",
}

FORMAT_VERSIONS = {
    "CSV": "RFC 4180",
    "GeoJSON": "RFC 7946",
    "GeoPackage": "1.3",
    "GeoTIFF": "1.0",
    "Shapefile ZIP": "1.0",
}


def build_iso19139_xml(metadata: dict[str, Any]) -> str:
    return build_arcgis_metadata_xml(metadata)


def build_arcgis_metadata_xml(metadata: dict[str, Any]) -> str:
    metadata = normalize_metadata(metadata)
    values = resolve_reviewed_values(metadata)
    root = etree.Element("metadata")
    root.set(f"{{{XML_NS}}}lang", "en")

    add_esri_section(root, values)
    add_metadata_details(root, values)
    add_metadata_contact(root, values)
    add_data_identification(root, metadata, values)
    add_spatial_reference(root, metadata)
    add_distribution(root, values)
    add_data_quality(root, values)

    return etree.tostring(
        root,
        encoding="UTF-8",
        pretty_print=True,
        xml_declaration=True,
    ).decode("utf-8")


def resolve_reviewed_values(metadata: dict[str, Any]) -> dict[str, Any]:
    ai_draft = metadata.get("ai_draft", {})
    review = metadata.get("human_review", {})
    today = datetime.now(timezone.utc).date().isoformat()

    title = first_text(
        review.get("final_title"),
        ai_draft.get("suggested_title"),
        metadata.get("title"),
        metadata.get("file_name"),
        "Untitled Dataset",
    )
    keywords = ensure_string_list(review.get("final_keywords")) or ensure_string_list(ai_draft.get("keywords"))
    if not keywords:
        keywords = default_keywords(metadata)

    topic_categories = (
        ensure_string_list(review.get("topic_categories"))
        or ensure_string_list(review.get("topic_category"))
        or ensure_string_list(ai_draft.get("topic_categories"))
        or ensure_string_list(ai_draft.get("topic_category"))
        or ["location"]
    )
    topic_categories = normalize_topic_categories(topic_categories)

    resource_language = normalize_language(
        first_text(review.get("resource_language"), ai_draft.get("resource_language"), "eng")
    )
    metadata_language = normalize_language(
        first_text(review.get("metadata_language"), ai_draft.get("metadata_language"), resource_language, "eng")
    )
    metadata_scope = normalize_scope(
        first_text(review.get("metadata_scope"), ai_draft.get("metadata_scope"), "dataset")
    )
    role = normalize_role(
        first_text(review.get("metadata_contact_role"), ai_draft.get("metadata_contact_role"), "pointOfContact")
    )

    file_identifier_seed = f"{metadata.get('file_name')}|{title}|{metadata.get('bbox')}"
    format_name = first_text(review.get("format_name"), ai_draft.get("format_name"), metadata.get("data_format"), "Unknown")
    citation_created = first_text(
        review.get("citation_created"),
        review.get("publication_date"),
        ai_draft.get("citation_created"),
        metadata.get("date_range", {}).get("start"),
        today,
    )

    return {
        "file_identifier": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, file_identifier_seed)}",
        "title": title,
        "abstract": first_text(review.get("final_abstract"), ai_draft.get("abstract"), "Needs review"),
        "purpose": first_text(review.get("final_purpose"), ai_draft.get("purpose"), "Needs review"),
        "keywords": keywords,
        "topic_categories": topic_categories,
        "resource_language": resource_language,
        "resource_character_set": normalize_character_set(
            first_text(review.get("resource_character_set"), ai_draft.get("resource_character_set"), "utf8")
        ),
        "citation_created": iso_date(citation_created, today),
        "format_name": format_name,
        "format_version": first_text(
            review.get("format_version"),
            ai_draft.get("format_version"),
            FORMAT_VERSIONS.get(format_name),
            "Not versioned",
        ),
        "metadata_language": metadata_language,
        "metadata_scope": metadata_scope,
        "metadata_contact_organization": first_text(
            review.get("metadata_contact_organization"),
            review.get("publisher"),
            review.get("creator"),
            ai_draft.get("metadata_contact_organization"),
            "Needs review",
        ),
        "metadata_contact_individual_name": first_text(
            review.get("metadata_contact_individual_name"),
            review.get("contact_name"),
            ai_draft.get("metadata_contact_individual_name"),
            "Needs review",
        ),
        "metadata_contact_position": first_text(
            review.get("metadata_contact_position"),
            ai_draft.get("metadata_contact_position"),
            "Needs review",
        ),
        "metadata_contact_role": role,
        "access_constraints": first_text(review.get("access_constraints"), "otherRestrictions"),
        "use_constraints": first_text(
            review.get("use_constraints"),
            review.get("license"),
            ai_draft.get("use_constraints_draft"),
            "Needs review",
        ),
        "lineage": first_text(review.get("lineage"), ai_draft.get("lineage_draft"), "Needs review"),
        "temporal_start": iso_date(
            first_text(review.get("temporal_start"), metadata.get("date_range", {}).get("start")),
            "",
        ),
        "temporal_end": iso_date(
            first_text(review.get("temporal_end"), metadata.get("date_range", {}).get("end")),
            "",
        ),
    }


def add_esri_section(root: etree._Element, values: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    esri = etree.SubElement(root, "Esri")
    text_child(esri, "CreaDate", now.date().isoformat())
    text_child(esri, "CreaTime", now.strftime("%H:%M:%S"))
    text_child(esri, "ArcGISFormat", ARCGIS_FORMAT_VERSION)
    text_child(esri, "ArcGISProfile", "ISO19139")
    text_child(esri, "ArcGISstyle", "ISO 19139 Metadata Implementation Specification")
    text_child(esri, "SyncOnce", "TRUE")
    text_child(esri, "ModDate", now.date().isoformat())
    text_child(esri, "ModTime", now.strftime("%H:%M:%S"))


def add_metadata_details(root: etree._Element, values: dict[str, Any]) -> None:
    text_child(root, "mdFileID", values["file_identifier"])
    md_lang = etree.SubElement(root, "mdLang")
    etree.SubElement(md_lang, "languageCode", value=values["metadata_language"])

    md_char = etree.SubElement(root, "mdChar")
    etree.SubElement(md_char, "CharSetCd", value=values["resource_character_set"])

    md_scope = etree.SubElement(root, "mdHrLv")
    etree.SubElement(md_scope, "ScopeCd", value=SCOPE_CODES[values["metadata_scope"]])

    text_child(root, "mdDateSt", values["citation_created"])
    text_child(root, "mdStanName", "ISO 19115 Geographic Information - Metadata")
    text_child(root, "mdStanVer", "ISO 19115:2003/19139")


def add_metadata_contact(root: etree._Element, values: dict[str, Any]) -> None:
    contact = etree.SubElement(root, "mdContact")
    party = etree.SubElement(contact, "rpIndName")
    party.text = values["metadata_contact_individual_name"]
    org = etree.SubElement(contact, "rpOrgName")
    org.text = values["metadata_contact_organization"]
    position = etree.SubElement(contact, "rpPosName")
    position.text = values["metadata_contact_position"]
    role = etree.SubElement(contact, "role")
    etree.SubElement(role, "RoleCd", value=ROLE_CODES[values["metadata_contact_role"]])


def add_data_identification(root: etree._Element, metadata: dict[str, Any], values: dict[str, Any]) -> None:
    data_info = etree.SubElement(root, "dataIdInfo")
    citation = etree.SubElement(data_info, "idCitation")
    text_child(citation, "resTitle", values["title"])
    date = etree.SubElement(citation, "date")
    text_child(date, "createDate", values["citation_created"])

    text_child(data_info, "idAbs", values["abstract"])
    text_child(data_info, "idPurp", values["purpose"])

    search_keys = etree.SubElement(data_info, "searchKeys")
    for keyword in values["keywords"]:
        text_child(search_keys, "keyword", keyword)

    for topic_category in values["topic_categories"]:
        topic = etree.SubElement(data_info, "tpCat")
        etree.SubElement(topic, "TopicCatCd", value=TOPIC_CATEGORY_CODES[topic_category])

    data_lang = etree.SubElement(data_info, "dataLang")
    etree.SubElement(data_lang, "languageCode", value=values["resource_language"])

    data_char = etree.SubElement(data_info, "dataChar")
    etree.SubElement(data_char, "CharSetCd", value=values["resource_character_set"])

    add_extent(data_info, metadata, values)
    add_resource_constraints(data_info, values)


def add_spatial_reference(root: etree._Element, metadata: dict[str, Any]) -> None:
    code_value = metadata.get("epsg_code") or metadata.get("crs_name") or ""
    if not code_value:
        return

    ref_system = etree.SubElement(root, "refSysInfo")
    ref_id = etree.SubElement(ref_system, "RefSystem")
    identifier = etree.SubElement(ref_id, "refSysID")
    rs_id = etree.SubElement(identifier, "identCode")
    rs_id.text = f"EPSG:{code_value}" if metadata.get("epsg_code") else str(code_value)


def add_distribution(root: etree._Element, values: dict[str, Any]) -> None:
    distribution = etree.SubElement(root, "distInfo")
    dist_format = etree.SubElement(distribution, "distFormat")
    text_child(dist_format, "formatName", values["format_name"])
    text_child(dist_format, "formatVer", values["format_version"])


def add_data_quality(root: etree._Element, values: dict[str, Any]) -> None:
    quality = etree.SubElement(root, "dqInfo")
    dq_data = etree.SubElement(quality, "dqData")
    lineage = etree.SubElement(dq_data, "dataLineage")
    text_child(lineage, "statement", values["lineage"])


def add_extent(parent: etree._Element, metadata: dict[str, Any], values: dict[str, Any]) -> None:
    bbox = metadata.get("bbox", {})
    has_bbox = all(bbox.get(key) is not None for key in ("west", "south", "east", "north"))
    if not has_bbox and not (values.get("temporal_start") or values.get("temporal_end")):
        return

    extent = etree.SubElement(parent, "dataExt")
    if has_bbox:
        geo_ext = etree.SubElement(extent, "geoEle")
        bbox_element = etree.SubElement(geo_ext, "GeoBndBox")
        text_child(bbox_element, "westBL", bbox["west"])
        text_child(bbox_element, "eastBL", bbox["east"])
        text_child(bbox_element, "southBL", bbox["south"])
        text_child(bbox_element, "northBL", bbox["north"])

    if values.get("temporal_start") or values.get("temporal_end"):
        temporal = etree.SubElement(extent, "tempEle")
        temp_extent = etree.SubElement(temporal, "TempExtent")
        text_child(temp_extent, "exTemp", "")
        begin = values.get("temporal_start") or values.get("temporal_end")
        end = values.get("temporal_end") or values.get("temporal_start")
        text_child(temp_extent, "beginDate", begin)
        text_child(temp_extent, "endDate", end)


def add_resource_constraints(parent: etree._Element, values: dict[str, Any]) -> None:
    constraints = etree.SubElement(parent, "resConst")
    legal = etree.SubElement(constraints, "LegConsts")
    access = etree.SubElement(legal, "accessConsts")
    etree.SubElement(access, "RestrictCd", value="008")
    use = etree.SubElement(legal, "useConsts")
    etree.SubElement(use, "RestrictCd", value="008")
    text_child(legal, "othConsts", values["use_constraints"])


def text_child(parent: etree._Element, tag: str, value: Any) -> etree._Element:
    child = etree.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            if not value:
                continue
            value = ", ".join(str(item) for item in value if str(item).strip())
        text = str(value).strip()
        if text:
            return text
    return ""


def default_keywords(metadata: dict[str, Any]) -> list[str]:
    keywords = ensure_string_list(
        [
            metadata.get("data_format", ""),
            metadata.get("geometry_type", ""),
            "GIS",
            "geospatial data",
        ]
    )
    return keywords or ["GIS", "geospatial data"]


def normalize_topic_categories(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        cleaned = str(value or "").strip()
        lowered = cleaned.lower().replace(" ", "")
        category = next(
            (item for item in TOPIC_CATEGORIES if item.lower() == lowered),
            None,
        )
        if category and category not in normalized:
            normalized.append(category)
    return normalized or ["location"]


def normalize_language(value: str) -> str:
    cleaned = str(value or "eng").strip().lower()
    return LANGUAGE_ALIASES.get(cleaned, cleaned[:3] if len(cleaned) >= 3 else "eng")


def normalize_character_set(value: str) -> str:
    cleaned = str(value or "utf8").strip().lower().replace("-", "")
    if cleaned in {"utf8", "utf"}:
        return "004"
    if cleaned == "004":
        return "004"
    return "004"


def normalize_scope(value: str) -> str:
    cleaned = str(value or "dataset").strip().lower()
    return cleaned if cleaned in SCOPE_CODES else "dataset"


def normalize_role(value: str) -> str:
    cleaned = str(value or "pointOfContact").strip()
    lowered = cleaned.lower().replace(" ", "")
    for role in ROLE_CODES:
        if role.lower() == lowered:
            return role
    return "pointOfContact"


def iso_date(value: str, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    match = re.search(r"(18|19|20|21)\d{2}[-/]\d{1,2}[-/]\d{1,2}", text)
    if match:
        parts = re.split(r"[-/]", match.group(0))
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    year = re.search(r"(18|19|20|21)\d{2}", text)
    if year:
        return f"{year.group(0)}-01-01"
    return default
