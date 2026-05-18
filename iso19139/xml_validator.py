from __future__ import annotations

from lxml import etree

from iso19139.xml_builder import NS


REQUIRED_XPATHS = {
    "fileIdentifier": "gmd:fileIdentifier/gco:CharacterString",
    "language": "gmd:language",
    "characterSet": "gmd:characterSet",
    "hierarchyLevel": "gmd:hierarchyLevel",
    "contact": "gmd:contact/gmd:CI_ResponsibleParty",
    "dateStamp": "gmd:dateStamp/gco:Date",
    "metadataStandardName": "gmd:metadataStandardName/gco:CharacterString",
    "metadataStandardVersion": "gmd:metadataStandardVersion/gco:CharacterString",
    "referenceSystemInfo": "gmd:referenceSystemInfo",
    "identificationInfo": "gmd:identificationInfo/gmd:MD_DataIdentification",
    "citation title": "gmd:identificationInfo//gmd:CI_Citation/gmd:title/gco:CharacterString",
    "abstract": "gmd:identificationInfo//gmd:abstract/gco:CharacterString",
    "distributionInfo": "gmd:distributionInfo/gmd:MD_Distribution",
    "dataQualityInfo": "gmd:dataQualityInfo/gmd:DQ_DataQuality",
}


def validate_xml(xml_text: str) -> dict[str, list[str] | bool]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return {"is_well_formed": False, "warnings": warnings, "errors": [str(exc)]}

    for label, xpath in REQUIRED_XPATHS.items():
        matches = root.xpath(xpath, namespaces=NS)
        if not matches:
            warnings.append(f"Missing or empty required high-level section: {label}.")

    if not root.xpath("gmd:identificationInfo//gmd:EX_GeographicBoundingBox", namespaces=NS):
        warnings.append("Geographic bounding box is not present in the XML.")

    return {"is_well_formed": not errors, "warnings": warnings, "errors": errors}
