from __future__ import annotations

from lxml import etree


REQUIRED_XPATHS = {
    "ArcGIS metadata root": "/metadata",
    "item title": "dataIdInfo/idCitation/resTitle",
    "summary / purpose": "dataIdInfo/idPurp",
    "description / abstract": "dataIdInfo/idAbs",
    "tags": "dataIdInfo/searchKeys/keyword",
    "topic categories": "dataIdInfo/tpCat/TopicCatCd",
    "resource language": "dataIdInfo/dataLang/languageCode",
    "resource character set": "dataIdInfo/dataChar/CharSetCd",
    "citation title": "dataIdInfo/idCitation/resTitle",
    "citation created date": "dataIdInfo/idCitation/date/createDate",
    "format name": "distInfo/distFormat/formatName",
    "format version": "distInfo/distFormat/formatVer",
    "metadata language": "mdLang/languageCode",
    "metadata scope": "mdHrLv/ScopeCd",
    "metadata contact organization": "mdContact/rpOrgName",
    "metadata contact individual": "mdContact/rpIndName",
    "metadata contact position": "mdContact/rpPosName",
    "metadata contact role": "mdContact/role/RoleCd",
    "bounding box west": "dataIdInfo/dataExt/geoEle/GeoBndBox/westBL",
    "bounding box east": "dataIdInfo/dataExt/geoEle/GeoBndBox/eastBL",
    "bounding box south": "dataIdInfo/dataExt/geoEle/GeoBndBox/southBL",
    "bounding box north": "dataIdInfo/dataExt/geoEle/GeoBndBox/northBL",
}


def validate_xml(xml_text: str) -> dict[str, list[str] | bool]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return {"is_well_formed": False, "warnings": warnings, "errors": [str(exc)]}

    if root.tag != "metadata":
        errors.append("XML root must be ArcGIS metadata XML: <metadata>.")
        return {"is_well_formed": False, "warnings": warnings, "errors": errors}

    for label, xpath in REQUIRED_XPATHS.items():
        matches = root.xpath(xpath)
        if not matches or all(not element_has_value(match) for match in matches):
            warnings.append(f"Missing or empty ArcGIS metadata field: {label}.")

    if not root.xpath("dataIdInfo/dataExt/geoEle/GeoBndBox"):
        warnings.append("Geographic bounding box is not present in the XML.")

    return {"is_well_formed": not errors, "warnings": warnings, "errors": errors}


def element_has_value(element: object) -> bool:
    if isinstance(element, etree._Element):
        return bool((element.text or "").strip() or element.attrib)
    return bool(str(element).strip())
