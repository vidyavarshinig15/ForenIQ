import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class ApplicationArtifactParser(BaseArtifactParser):
    """
    Parser for installed applications and app execution/usage history.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.APPLICATION

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        indicators = ["app", "apps", "application", "applications", "installed_apps", "app_usage"]
        return any(ind in path_lower for ind in indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"application", "app", "installed_app", "usage_event", "item", "entry"}
        idx = 0

        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("package_name")
                or raw_dict.get("app_id")
                or f"{item.path}#app_{idx}"
            )

            app_name = (
                raw_dict.get("name")
                or raw_dict.get("application")
                or raw_dict.get("app_name")
                or raw_dict.get("package_name")
                or raw_dict.get("bundle_id")
            )

            parsed_payload = {
                "application": app_name,
                "package_name": raw_dict.get("package_name") or raw_dict.get("bundle_id"),
                "version": raw_dict.get("version") or raw_dict.get("app_version"),
                "event_type": raw_dict.get("event_type") or raw_dict.get("event") or raw_dict.get("action") or "INSTALLED",
                "timestamp": raw_dict.get("timestamp") or raw_dict.get("install_time") or raw_dict.get("time"),
                "duration": raw_dict.get("duration") or raw_dict.get("duration_seconds"),
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
