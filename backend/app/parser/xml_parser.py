import logging
from typing import Any, Dict, Generator, Optional, Set, Tuple
import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException

from backend.app.parser.errors import MalformedXMLError, ParserSecurityError

logger = logging.getLogger(__name__)


def element_to_dict(elem: Any) -> Any:
    """
    Safely converts an XML ElementTree element and its children to a JSON-compatible Python dictionary.
    Preserves all attributes and textual leaves without data loss.
    """
    data: Dict[str, Any] = {}
    if elem.attrib:
        data.update(elem.attrib)

    text = elem.text.strip() if elem.text else ""
    children = list(elem)

    if not children:
        if text:
            if data:
                data["_value"] = text
                return data
            return text
        return data

    for child in children:
        child_tag = child.tag
        # Strip namespace if present e.g. {http://...}tag -> tag
        if "}" in child_tag:
            child_tag = child_tag.split("}", 1)[1]

        child_val = element_to_dict(child)

        if child_tag in data:
            if not isinstance(data[child_tag], list):
                data[child_tag] = [data[child_tag]]
            data[child_tag].append(child_val)
        else:
            data[child_tag] = child_val

    if text and text not in ["\n", "\r\n", " "]:
        data["_value"] = text

    return data


def stream_xml_records(
    file_path: str,
    target_tags: Optional[Set[str]] = None,
) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
    """
    Streams XML records safely using defusedxml iterparse.
    Blocks XXE, DTDs, and entity expansions.
    Clears processed elements immediately to bound memory to O(1) per record.
    """
    normalized_targets = {t.lower() for t in target_tags} if target_tags else None

    try:
        context = ET.iterparse(file_path, events=("start", "end"))
        root = None

        for event, elem in context:
            if event == "start" and root is None:
                root = elem
                continue

            if event == "end":
                tag_name = elem.tag
                if "}" in tag_name:
                    tag_name = tag_name.split("}", 1)[1]

                tag_lower = tag_name.lower()
                if normalized_targets is None or tag_lower in normalized_targets:
                    parsed_dict = element_to_dict(elem)
                    yield (tag_name, parsed_dict if isinstance(parsed_dict, dict) else {"value": parsed_dict})
                    if root is not None:
                        root.clear()
                    else:
                        elem.clear()

    except (ET.EntitiesForbidden, ET.DTDForbidden, ET.ExternalReferenceForbidden) as e:
        logger.error(f"Security violation parsing XML '{file_path}': {e}")
        raise ParserSecurityError(f"Malicious XML detected (XXE/DTD injection): {e}")
    except (ET.ParseError, DefusedXmlException) as e:
        logger.warning(f"Malformed XML syntax encountered in '{file_path}': {e}")
        raise MalformedXMLError(f"Malformed XML syntax in '{file_path}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error while streaming XML '{file_path}': {e}")
        raise MalformedXMLError(f"Failed to stream XML '{file_path}': {e}")
