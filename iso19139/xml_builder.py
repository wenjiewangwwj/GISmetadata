from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree

from core.metadata_model import ensure_string_list, normalize_metadata


NS = {
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gco": "http://www.isotc211.org/2005/gco",
    "gml": "http://www.opengis.net/gml",
    "xlink": "http://www.w3.org/1999/xlink",
}
CODELIST_BASE = "https://standards.iso.org/iso/19139/resources/gmxCodelists.xml"
TOPIC_CATEGORIES = {
    "farming", "biota", "boundaries", "climatologyMeteorologyAtmosphere", "economy",
    "elevation", "environment", "geoscientificInformation", "health",
    "imageryBaseMapsEarthCover", "intelligenceMilitary", "inlandWaters", "location",
    "oceans", "planningCadastre", "society", "structure", "transportation",
    "utilitiesCommunication",
}


def build_iso19139_xml(metadata: dict[str, Any]) -> str:
    metadata = normalize_metadata(metadata)
    root = etree.parse(str(Path(__file__).with_name("iso_template.xml"))).getroot()
    values = reviewed_values(metadata)

    set_text(root, "fileIdentifier", values["file_identifier"])
    set_code(root, "language", "LanguageCode", "eng")
    set_code(root, "characterSet", "MD_CharacterSetCode", "utf8")
    set_code(root, "hierarchyLevel", "MD_ScopeCode", "dataset")
    set_contact(root.find("gmd:contact", NS), values)
    set_date(root, "dateStamp", datetime.now(timezone.utc).date().isoformat())
    set_text(root, "metadataStandardName", "ISO 19115 Geographic Information - Metadata")
    set_text(root, "metadataStandardVersion", "ISO 19115:2003/19139")
    set_reference_system(root.find("gmd:referenceSystemInfo", NS), metadata)
    set_identification(root.find("gmd:identificationInfo", NS), metadata, values)
    set_distribution(root.find("gmd:distributionInfo", NS), metadata)
    set_lineage(root.find("gmd:dataQualityInfo", NS), values)

    return etree.tostring(root, encoding="UTF-8", pretty_print=True, xml_declaration=True).decode("utf-8")


def reviewed_values(metadata: dict[str, Any]) -> dict[str, Any]:
    ai_draft = metadata.get("ai_draft", {})
    review = metadata.get("human_review", {})
    title = review.get("final_title") or ai_draft.get("suggested_title") or metadata.get("title") or metadata.get("file_name") or "Untitled Dataset"
    topic = normalize_topic(review.get("topic_category") or ai_draft.get("topic_category") or "location")
    seed = f"{metadata.get('file_name')}|{title}|{metadata.get('bbox')}"
    return {
        "file_identifier": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, seed)}",
        "title": title,
        "abstract": review.get("final_abstract") or ai_draft.get("abstract") or "Needs review.",
        "purpose": review.get("final_purpose") or ai_draft.get("purpose") or "Needs review.",
        "keywords": ensure_string_list(review.get("final_keywords")) or ensure_string_list(ai_draft.get("keywords")) or ["Needs review"],
        "topic_category": topic,
        "publisher": review.get("publisher") or review.get("creator") or "Needs review.",
        "contact_name": review.get("contact_name") or review.get("creator") or "Needs review.",
        "contact_email": review.get("contact_email") or "",
        "publication_date": review.get("publication_date") or datetime.now(timezone.utc).date().isoformat(),
        "access_constraints": review.get("access_constraints") or "Needs review.",
        "use_constraints": review.get("use_constraints") or review.get("license") or ai_draft.get("use_constraints_draft") or "Needs review.",
        "lineage": review.get("lineage") or ai_draft.get("lineage_draft") or "Needs review.",
        "temporal_start": review.get("temporal_start") or metadata.get("date_range", {}).get("start", ""),
        "temporal_end": review.get("temporal_end") or metadata.get("date_range", {}).get("end", ""),
    }


def normalize_topic(value: str) -> str:
    compact = str(value or "location").strip().replace(" ", "").lower()
    for topic in TOPIC_CATEGORIES:
        if topic.lower() == compact:
            return topic
    return "location"


def set_text(root: etree._Element, section: str, value: str) -> None:
    element = clear(root.find(f"gmd:{section}", NS))
    text_child(element, value)


def set_date(root: etree._Element, section: str, value: str) -> None:
    element = clear(root.find(f"gmd:{section}", NS))
    etree.SubElement(element, q("gco", "Date")).text = value


def set_code(root: etree._Element, section: str, code_name: str, value: str) -> None:
    element = clear(root.find(f"gmd:{section}", NS))
    code = etree.SubElement(element, q("gmd", code_name))
    code.set("codeList", f"{CODELIST_BASE}#{code_name}")
    code.set("codeListValue", value)
    code.text = value


def set_contact(section: etree._Element | None, values: dict[str, Any]) -> None:
    section = clear(section)
    party = etree.SubElement(section, q("gmd", "CI_ResponsibleParty"))
    add_text(party, "individualName", values["contact_name"])
    add_text(party, "organisationName", values["publisher"])
    if values.get("contact_email"):
        contact_info = etree.SubElement(party, q("gmd", "contactInfo"))
        contact = etree.SubElement(contact_info, q("gmd", "CI_Contact"))
        address = etree.SubElement(contact, q("gmd", "address"))
        ci_address = etree.SubElement(address, q("gmd", "CI_Address"))
        add_text(ci_address, "electronicMailAddress", values["contact_email"])
    role = etree.SubElement(party, q("gmd", "role"))
    code = etree.SubElement(role, q("gmd", "CI_RoleCode"))
    code.set("codeList", f"{CODELIST_BASE}#CI_RoleCode")
    code.set("codeListValue", "pointOfContact")
    code.text = "pointOfContact"


def set_reference_system(section: etree._Element | None, metadata: dict[str, Any]) -> None:
    section = clear(section)
    code_value = metadata.get("epsg_code") or metadata.get("crs_name") or ""
    if not code_value:
        section.set(q("gco", "nilReason"), "missing")
        return
    ref = etree.SubElement(section, q("gmd", "MD_ReferenceSystem"))
    ident = etree.SubElement(etree.SubElement(ref, q("gmd", "referenceSystemIdentifier")), q("gmd", "RS_Identifier"))
    add_text(ident, "code", f"EPSG:{code_value}" if metadata.get("epsg_code") else code_value)
    if metadata.get("epsg_code"):
        add_text(ident, "codeSpace", "EPSG")


def set_identification(section: etree._Element | None, metadata: dict[str, Any], values: dict[str, Any]) -> None:
    section = clear(section)
    ident = etree.SubElement(section, q("gmd", "MD_DataIdentification"))
    citation = etree.SubElement(etree.SubElement(ident, q("gmd", "citation")), q("gmd", "CI_Citation"))
    add_text(citation, "title", values["title"])
    add_citation_date(citation, values["publication_date"])
    add_text(ident, "abstract", values["abstract"])
    add_text(ident, "purpose", values["purpose"])
    add_spatial_type(ident, "grid" if metadata.get("data_format") == "GeoTIFF" else "vector")
    add_keywords(ident, values["keywords"])
    add_constraints(ident, values)
    add_extent(ident, metadata, values)
    add_text(ident, "language", "eng")
    add_topic(ident, values["topic_category"])


def add_citation_date(parent: etree._Element, value: str) -> None:
    ci_date = etree.SubElement(etree.SubElement(parent, q("gmd", "date")), q("gmd", "CI_Date"))
    date = etree.SubElement(ci_date, q("gmd", "date"))
    etree.SubElement(date, q("gco", "Date")).text = value
    date_type = etree.SubElement(ci_date, q("gmd", "dateType"))
    code = etree.SubElement(date_type, q("gmd", "CI_DateTypeCode"))
    code.set("codeList", f"{CODELIST_BASE}#CI_DateTypeCode")
    code.set("codeListValue", "publication")
    code.text = "publication"


def add_spatial_type(parent: etree._Element, value: str) -> None:
    section = etree.SubElement(parent, q("gmd", "spatialRepresentationType"))
    code = etree.SubElement(section, q("gmd", "MD_SpatialRepresentationTypeCode"))
    code.set("codeList", f"{CODELIST_BASE}#MD_SpatialRepresentationTypeCode")
    code.set("codeListValue", value)
    code.text = value


def add_keywords(parent: etree._Element, keywords: list[str]) -> None:
    md_keywords = etree.SubElement(etree.SubElement(parent, q("gmd", "descriptiveKeywords")), q("gmd", "MD_Keywords"))
    for keyword in keywords:
        add_text(md_keywords, "keyword", keyword)


def add_constraints(parent: etree._Element, values: dict[str, Any]) -> None:
    legal = etree.SubElement(etree.SubElement(parent, q("gmd", "resourceConstraints")), q("gmd", "MD_LegalConstraints"))
    for tag in ("accessConstraints", "useConstraints"):
        section = etree.SubElement(legal, q("gmd", tag))
        code = etree.SubElement(section, q("gmd", "MD_RestrictionCode"))
        code.set("codeList", f"{CODELIST_BASE}#MD_RestrictionCode")
        code.set("codeListValue", "otherRestrictions")
        code.text = "otherRestrictions"
    add_text(legal, "otherConstraints", values["use_constraints"])


def add_extent(parent: etree._Element, metadata: dict[str, Any], values: dict[str, Any]) -> None:
    bbox = metadata.get("bbox", {})
    if not all(bbox.get(key) is not None for key in ("west", "south", "east", "north")):
        return
    extent = etree.SubElement(etree.SubElement(parent, q("gmd", "extent")), q("gmd", "EX_Extent"))
    geo = etree.SubElement(etree.SubElement(extent, q("gmd", "geographicElement")), q("gmd", "EX_GeographicBoundingBox"))
    for tag, key in (("westBoundLongitude", "west"), ("eastBoundLongitude", "east"), ("southBoundLatitude", "south"), ("northBoundLatitude", "north")):
        child = etree.SubElement(geo, q("gmd", tag))
        etree.SubElement(child, q("gco", "Decimal")).text = str(bbox[key])
    if values.get("temporal_start") or values.get("temporal_end"):
        time_period = etree.SubElement(etree.SubElement(etree.SubElement(extent, q("gmd", "temporalElement")), q("gmd", "EX_TemporalExtent")), q("gmd", "extent"))
        period = etree.SubElement(time_period, q("gml", "TimePeriod"))
        period.set(q("gml", "id"), "temporalExtent")
        etree.SubElement(period, q("gml", "beginPosition")).text = values.get("temporal_start") or values.get("temporal_end")
        etree.SubElement(period, q("gml", "endPosition")).text = values.get("temporal_end") or values.get("temporal_start")


def add_topic(parent: etree._Element, value: str) -> None:
    etree.SubElement(etree.SubElement(parent, q("gmd", "topicCategory")), q("gmd", "MD_TopicCategoryCode")).text = value


def set_distribution(section: etree._Element | None, metadata: dict[str, Any]) -> None:
    section = clear(section)
    fmt = etree.SubElement(etree.SubElement(etree.SubElement(section, q("gmd", "MD_Distribution")), q("gmd", "distributionFormat")), q("gmd", "MD_Format"))
    add_text(fmt, "name", metadata.get("data_format") or "Unknown")
    add_text(fmt, "version", "Needs review.")


def set_lineage(section: etree._Element | None, values: dict[str, Any]) -> None:
    section = clear(section)
    quality = etree.SubElement(section, q("gmd", "DQ_DataQuality"))
    lineage = etree.SubElement(etree.SubElement(quality, q("gmd", "lineage")), q("gmd", "LI_Lineage"))
    add_text(lineage, "statement", values["lineage"])


def add_text(parent: etree._Element, tag: str, value: str) -> None:
    text_child(etree.SubElement(parent, q("gmd", tag)), value)


def text_child(parent: etree._Element, value: str) -> None:
    etree.SubElement(parent, q("gco", "CharacterString")).text = str(value or "")


def clear(element: etree._Element | None) -> etree._Element:
    if element is None:
        raise ValueError("ISO template is missing a required section.")
    element.attrib.clear()
    element.text = None
    for child in list(element):
        element.remove(child)
    return element


def q(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"
