import logging
from dataclasses import dataclass
from typing import List, Set

from backend.app.parser.errors import UnsupportedUFDRFormatError
from backend.app.parser.models import ArchiveInventoryItem

logger = logging.getLogger(__name__)


@dataclass
class UFDRDetectionResult:
    """Forensic container detection assessment."""
    is_supported: bool
    format_name: str
    has_manifest: bool
    detected_categories: Set[str]
    candidate_files: List[str]
    reason: str = ""


class UFDRDetector:
    """
    Forensic container format detector.
    Inspects archive structure and member characteristics rather than relying solely on file extensions.
    """

    KNOWN_MANIFEST_NAMES = {
        "manifest.xml", "report.xml", "info.xml", "device.xml", "summary.xml"
    }

    CATEGORY_INDICATORS = {
        "calls": ["call", "calls", "call_log", "callhistory"],
        "messages": ["message", "messages", "chat", "chats", "sms", "mms", "whatsapp", "telegram", "im"],
        "contacts": ["contact", "contacts", "addressbook", "people", "phonebook"],
        "location": ["location", "locations", "gps", "geo", "waypoint", "coordinates", "places"],
        "browser": ["browser", "history", "bookmarks", "searches", "web_history", "chrome", "safari"],
        "applications": ["app", "apps", "application", "applications", "installed_apps", "usage"],
        "filesystem": ["file", "files", "filesystem", "metadata", "file_list", "directory"],
    }

    def detect(self, inventory: List[ArchiveInventoryItem]) -> UFDRDetectionResult:
        """
        Examine archive inventory to detect UFDR extraction structure.
        """
        if not inventory:
            raise UnsupportedUFDRFormatError("Evidence archive contains no inspectable files.")

        xml_files = [item for item in inventory if item.extension == ".xml"]
        candidate_paths = [item.path for item in inventory]

        has_manifest = any(
            any(item.path.lower().endswith(m) for m in self.KNOWN_MANIFEST_NAMES)
            for item in xml_files
        )

        detected_categories: Set[str] = set()

        for item in inventory:
            path_lower = item.path.lower()
            for cat, keywords in self.CATEGORY_INDICATORS.items():
                if any(kw in path_lower for kw in keywords):
                    detected_categories.add(cat)

        # Even if not in path, if XML files exist, filesystem metadata is always available
        if inventory:
            detected_categories.add("filesystem")

        # Must have at least one structured XML or recognized artifact layout
        if not xml_files and len(detected_categories) <= 1:
            raise UnsupportedUFDRFormatError(
                "UNSUPPORTED_UFDR_STRUCTURE: Archive does not contain any recognized forensic XML structures or artifact catalogs."
            )

        format_name = "UFDR Forensic XML Container"
        if has_manifest:
            format_name = "Cellebrite/Standard UFDR Extraction Archive"

        return UFDRDetectionResult(
            is_supported=True,
            format_name=format_name,
            has_manifest=has_manifest,
            detected_categories=detected_categories,
            candidate_files=[item.path for item in xml_files] if xml_files else candidate_paths,
            reason="Supported UFDR forensic structure confirmed",
        )
