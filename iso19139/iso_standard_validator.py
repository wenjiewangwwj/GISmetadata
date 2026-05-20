from __future__ import annotations

from urllib.request import urlopen

from lxml import etree

from iso19139.iso_standard_builder import GMD, ISO19139_GMD_SCHEMA


NSMAP = {"gmd": GMD}
REQUIRED_XPATHS = {
    "ISO metadata root": "/gmd:MD_Metadata",
    "file identifier": "gmd:fileIdentifier/gco:CharacterString",
    "metadata language": "gmd:language/gmd:LanguageCode",
    "metadata character set": "gmd:characterSet/gmd:MD_CharacterSetCode",
    "metadata scope": "gmd:hierarchyLevel/gmd:MD_ScopeCode",
    "metadata contact": "gmd:contact/gmd:CI_ResponsibleParty",
    "metadata date stamp": "gmd:dateStamp/gco:Date",
    "identification info": "gmd:identificationInfo/gmd:MD_DataIdentification",
    "resource title": "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd:CI_Citation/gmd:title/gco:CharacterString",
    "resource abstract": "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:abstract/gco:CharacterString",
    "resource language": "gmd:identificationInfo/gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode",
}
REQUIRED_XPATH_NS = {
    "gmd": GMD,
    "gco": "http://www.isotc211.org/2005/gco",
}


def validate_iso19115_xml(xml_text: str) -> dict[str, list[str] | bool | None]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        return {
            "is_well_formed": False,
            "is_schema_valid": False,
            "warnings": warnings,
            "errors": [str(exc)],
        }

    if root.tag != f"{{{GMD}}}MD_Metadata":
        errors.append("XML root must be ISO 19139 metadata: <gmd:MD_Metadata>.")
        return {
            "is_well_formed": False,
            "is_schema_valid": False,
            "warnings": warnings,
            "errors": errors,
        }

    for label, xpath in REQUIRED_XPATHS.items():
        matches = root.xpath(xpath, namespaces=REQUIRED_XPATH_NS)
        if not matches or all(not element_has_value(match) for match in matches):
            warnings.append(f"Missing or empty ISO metadata field: {label}.")

    schema_valid = validate_against_official_schema(root, warnings, errors)
    return {
        "is_well_formed": True,
        "is_schema_valid": schema_valid,
        "warnings": warnings,
        "errors": errors,
    }


def validate_against_official_schema(
    root: etree._Element,
    warnings: list[str],
    errors: list[str],
) -> bool | None:
    try:
        parser = etree.XMLParser(no_network=False)
        parser.resolvers.add(OfficialSchemaResolver())
        schema_doc = etree.parse(ISO19139_GMD_SCHEMA, parser)
        schema = etree.XMLSchema(schema_doc)
    except (OSError, etree.XMLSchemaParseError, etree.XMLSyntaxError) as exc:
        warnings.append(f"Official ISO 19139 XSD validation was skipped: {exc}")
        return None

    is_valid = schema.validate(root)
    if not is_valid:
        errors.extend(str(item) for item in schema.error_log)
    return is_valid


class OfficialSchemaResolver(etree.Resolver):
    def resolve(self, url: str, pubid: str, context: object) -> object:
        trusted_hosts = (
            "https://schemas.isotc211.org/",
            "http://schemas.isotc211.org/",
            "https://www.w3.org/",
            "http://www.w3.org/",
            "https://schemas.opengis.net/",
            "http://schemas.opengis.net/",
        )
        if url.startswith(trusted_hosts):
            with urlopen(url, timeout=20) as response:
                return self.resolve_string(response.read(), context, base_url=url)
        return None


def element_has_value(element: object) -> bool:
    if isinstance(element, etree._Element):
        return bool((element.text or "").strip() or element.attrib or len(element))
    return bool(str(element).strip())
