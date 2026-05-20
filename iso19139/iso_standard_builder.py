from __future__ import annotations

from typing import Any

from lxml import etree

from iso19139.xml_builder import resolve_reviewed_values


GMD = "http://www.isotc211.org/2005/gmd"
GCO = "http://www.isotc211.org/2005/gco"
GML = "http://www.opengis.net/gml/3.2"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ISO19139_GMD_SCHEMA = "https://schemas.isotc211.org/19139/-/gmd/1.0/gmd.xsd"
CODE_LIST_BASE = "https://schemas.isotc211.org/19139/-/resources/codelist/ML_gmxCodelists.xml"

NSMAP = {
    "gmd": GMD,
    "gco": GCO,
    "gml": GML,
    "xlink": XLINK,
    "xsi": XSI,
}


def build_iso19115_xml(metadata: dict[str, Any]) -> str:
    """Build standards-style ISO 19115 metadata using the ISO 19139 XML encoding."""
    values = resolve_reviewed_values(metadata)
    root = element("gmd", "MD_Metadata", nsmap=NSMAP)
    root.set(f"{{{XSI}}}schemaLocation", f"{GMD} {ISO19139_GMD_SCHEMA}")

    character_child(root, "fileIdentifier", values["file_identifier"])
    code_list_child(root, "language", "LanguageCode", values["metadata_language"])
    code_list_child(root, "characterSet", "MD_CharacterSetCode", character_set_name(values["resource_character_set"]))
    code_list_child(root, "hierarchyLevel", "MD_ScopeCode", values["metadata_scope"])
    responsible_party_child(root, "contact", values, values["metadata_contact_role"])
    date_child(root, "dateStamp", values["citation_created"])
    character_child(root, "metadataStandardName", "ISO 19115 Geographic Information - Metadata")
    character_child(root, "metadataStandardVersion", "ISO 19115:2003/19139")

    add_reference_system(root, metadata)
    add_identification_info(root, metadata, values)
    add_distribution_info(root, values)
    add_data_quality_info(root, values)

    return etree.tostring(
        root,
        encoding="UTF-8",
        pretty_print=True,
        xml_declaration=True,
    ).decode("utf-8")


def add_reference_system(root: etree._Element, metadata: dict[str, Any]) -> None:
    code_value = metadata.get("epsg_code") or metadata.get("crs_name") or ""
    if not code_value:
        return

    wrapper = element("gmd", "referenceSystemInfo", parent=root)
    ref_system = element("gmd", "MD_ReferenceSystem", parent=wrapper)
    identifier = element("gmd", "referenceSystemIdentifier", parent=ref_system)
    rs_identifier = element("gmd", "RS_Identifier", parent=identifier)
    character_child(rs_identifier, "code", str(code_value))
    if metadata.get("epsg_code"):
        character_child(rs_identifier, "codeSpace", "EPSG")


def add_identification_info(root: etree._Element, metadata: dict[str, Any], values: dict[str, Any]) -> None:
    wrapper = element("gmd", "identificationInfo", parent=root)
    data_id = element("gmd", "MD_DataIdentification", parent=wrapper)

    citation_wrapper = element("gmd", "citation", parent=data_id)
    citation = element("gmd", "CI_Citation", parent=citation_wrapper)
    character_child(citation, "title", values["title"])
    citation_date_wrapper = element("gmd", "date", parent=citation)
    citation_date = element("gmd", "CI_Date", parent=citation_date_wrapper)
    date_child(citation_date, "date", values["citation_created"])
    code_list_child(citation_date, "dateType", "CI_DateTypeCode", "creation")

    character_child(data_id, "abstract", values["abstract"])
    if values.get("purpose"):
        character_child(data_id, "purpose", values["purpose"])
    responsible_party_child(data_id, "pointOfContact", values, "pointOfContact")
    add_keywords(data_id, values["keywords"])
    add_resource_constraints(data_id, values)
    add_spatial_representation_type(data_id, metadata)
    code_list_child(data_id, "language", "LanguageCode", values["resource_language"])
    code_list_child(data_id, "characterSet", "MD_CharacterSetCode", character_set_name(values["resource_character_set"]))

    for category in values["topic_categories"]:
        wrapper = element("gmd", "topicCategory", parent=data_id)
        topic = element("gmd", "MD_TopicCategoryCode", parent=wrapper)
        topic.text = category

    add_extent(data_id, values)


def add_keywords(data_id: etree._Element, keywords: list[str]) -> None:
    if not keywords:
        return

    wrapper = element("gmd", "descriptiveKeywords", parent=data_id)
    keyword_block = element("gmd", "MD_Keywords", parent=wrapper)
    for keyword in keywords:
        character_child(keyword_block, "keyword", keyword)
    code_list_child(keyword_block, "type", "MD_KeywordTypeCode", "theme")


def add_resource_constraints(data_id: etree._Element, values: dict[str, Any]) -> None:
    wrapper = element("gmd", "resourceConstraints", parent=data_id)
    constraints = element("gmd", "MD_LegalConstraints", parent=wrapper)
    code_list_child(constraints, "accessConstraints", "MD_RestrictionCode", "otherRestrictions")
    code_list_child(constraints, "useConstraints", "MD_RestrictionCode", "otherRestrictions")
    character_child(constraints, "otherConstraints", values["use_constraints"])


def add_spatial_representation_type(data_id: etree._Element, metadata: dict[str, Any]) -> None:
    raster = metadata.get("raster", {}) or {}
    representation = ""
    if raster.get("width") or raster.get("height"):
        representation = "grid"
    elif metadata.get("geometry_type") or metadata.get("bbox"):
        representation = "vector"

    if representation:
        code_list_child(data_id, "spatialRepresentationType", "MD_SpatialRepresentationTypeCode", representation)


def add_extent(data_id: etree._Element, values: dict[str, Any]) -> None:
    bbox = values.get("bbox", {})
    has_bbox = all(bbox.get(key) is not None for key in ("west", "south", "east", "north"))
    has_temporal = bool(values.get("temporal_start") or values.get("temporal_end"))
    if not has_bbox and not has_temporal:
        return

    wrapper = element("gmd", "extent", parent=data_id)
    extent = element("gmd", "EX_Extent", parent=wrapper)

    if has_bbox:
        geo_wrapper = element("gmd", "geographicElement", parent=extent)
        geo_box = element("gmd", "EX_GeographicBoundingBox", parent=geo_wrapper)
        decimal_child(geo_box, "westBoundLongitude", bbox["west"])
        decimal_child(geo_box, "eastBoundLongitude", bbox["east"])
        decimal_child(geo_box, "southBoundLatitude", bbox["south"])
        decimal_child(geo_box, "northBoundLatitude", bbox["north"])

    if has_temporal:
        temporal_wrapper = element("gmd", "temporalElement", parent=extent)
        temporal_extent = element("gmd", "EX_TemporalExtent", parent=temporal_wrapper)
        extent_wrapper = element("gmd", "extent", parent=temporal_extent)
        period = element("gml", "TimePeriod", parent=extent_wrapper)
        period.set(f"{{{GML}}}id", "resource-temporal-extent")
        begin = element("gml", "beginPosition", parent=period)
        begin.text = values.get("temporal_start") or values.get("temporal_end")
        end = element("gml", "endPosition", parent=period)
        end.text = values.get("temporal_end") or values.get("temporal_start")


def add_distribution_info(root: etree._Element, values: dict[str, Any]) -> None:
    wrapper = element("gmd", "distributionInfo", parent=root)
    distribution = element("gmd", "MD_Distribution", parent=wrapper)
    format_wrapper = element("gmd", "distributionFormat", parent=distribution)
    data_format = element("gmd", "MD_Format", parent=format_wrapper)
    character_child(data_format, "name", values["format_name"])
    character_child(data_format, "version", values["format_version"])


def add_data_quality_info(root: etree._Element, values: dict[str, Any]) -> None:
    wrapper = element("gmd", "dataQualityInfo", parent=root)
    quality = element("gmd", "DQ_DataQuality", parent=wrapper)
    scope_wrapper = element("gmd", "scope", parent=quality)
    scope = element("gmd", "DQ_Scope", parent=scope_wrapper)
    code_list_child(scope, "level", "MD_ScopeCode", values["metadata_scope"])
    lineage_wrapper = element("gmd", "lineage", parent=quality)
    lineage = element("gmd", "LI_Lineage", parent=lineage_wrapper)
    character_child(lineage, "statement", values["lineage"])


def responsible_party_child(parent: etree._Element, wrapper_name: str, values: dict[str, Any], role: str) -> None:
    wrapper = element("gmd", wrapper_name, parent=parent)
    party = element("gmd", "CI_ResponsibleParty", parent=wrapper)
    if values.get("metadata_contact_individual_name"):
        character_child(party, "individualName", values["metadata_contact_individual_name"])
    if values.get("metadata_contact_organization"):
        character_child(party, "organisationName", values["metadata_contact_organization"])
    if values.get("metadata_contact_position"):
        character_child(party, "positionName", values["metadata_contact_position"])
    code_list_child(party, "role", "CI_RoleCode", role)


def character_child(parent: etree._Element, name: str, value: Any) -> etree._Element:
    wrapper = element("gmd", name, parent=parent)
    text = element("gco", "CharacterString", parent=wrapper)
    text.text = "" if value is None else str(value)
    return wrapper


def date_child(parent: etree._Element, name: str, value: Any) -> etree._Element:
    wrapper = element("gmd", name, parent=parent)
    date = element("gco", "Date", parent=wrapper)
    date.text = "" if value is None else str(value)
    return wrapper


def decimal_child(parent: etree._Element, name: str, value: Any) -> etree._Element:
    wrapper = element("gmd", name, parent=parent)
    decimal = element("gco", "Decimal", parent=wrapper)
    decimal.text = "" if value is None else str(value)
    return wrapper


def code_list_child(parent: etree._Element, wrapper_name: str, code_name: str, value: str) -> etree._Element:
    wrapper = element("gmd", wrapper_name, parent=parent)
    code = element("gmd", code_name, parent=wrapper)
    code.set("codeList", f"{CODE_LIST_BASE}#{code_name}")
    code.set("codeListValue", value)
    code.text = value
    return wrapper


def character_set_name(value: str) -> str:
    return "utf8" if str(value) == "004" else str(value or "utf8")


def element(prefix: str, name: str, parent: etree._Element | None = None, nsmap: dict[str, str] | None = None) -> etree._Element:
    item = etree.Element(f"{{{NSMAP[prefix]}}}{name}", nsmap=nsmap)
    if parent is not None:
        parent.append(item)
    return item
