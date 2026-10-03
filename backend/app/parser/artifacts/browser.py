import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class BrowserArtifactParser(BaseArtifactParser):
    """
    Parser for web history, bookmarks, and browser navigation logs.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.BROWSER

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        indicators = ["browser", "history", "bookmarks", "searches", "web_history", "chrome", "safari"]
        return any(ind in path_lower for ind in indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"history_item", "visit", "bookmark", "browser_record", "entry", "item"}
        path_lower = item.path.lower()
        default_browser = "Browser"
        if "chrome" in path_lower:
            default_browser = "Chrome"
        elif "safari" in path_lower:
            default_browser = "Safari"
        elif "firefox" in path_lower:
            default_browser = "Firefox"

        idx = 0
        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("history_id")
                or f"{item.path}#browser_{idx}"
            )

            url = raw_dict.get("url") or raw_dict.get("uri") or raw_dict.get("address") or raw_dict.get("link")
            if not url and isinstance(raw_dict.get("_value"), str) and raw_dict.get("_value").startswith("http"):
                url = raw_dict.get("_value")

            parsed_payload = {
                "url": url,
                "title": raw_dict.get("title") or raw_dict.get("name"),
                "timestamp": raw_dict.get("timestamp") or raw_dict.get("visit_time") or raw_dict.get("date"),
                "browser": raw_dict.get("browser") or default_browser,
                "visit_count": raw_dict.get("visit_count") or raw_dict.get("count"),
                "source_tag": tag_name,
                "raw": raw_dict,
            }

            yield ParsedArtifactRecord(
                artifact_type=self.artifact_type,
                source_file=os.path.basename(item.path),
                source_path=item.path,
                record_identifier=str(record_id),
                raw_data=parsed_payload,
            )
