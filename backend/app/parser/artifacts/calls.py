import os
from typing import Any, Dict, Generator
import uuid

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class CallArtifactParser(BaseArtifactParser):
    """
    Parser for telephonic call log records from UFDR forensic archives.
    Accommodates multiple XML layouts (Cellebrite, Oxygen, XRY, generic).
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CALL

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        call_indicators = ["call", "calls", "call_log", "callhistory", "voice"]
        return any(ind in path_lower for ind in call_indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"call", "call_record", "callrecord", "callitem", "item", "entry"}
        idx = 0

        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("record_id")
                or raw_dict.get("call_id")
                or f"{item.path}#call_{idx}"
            )

            # Heuristic field normalization into canonical container while preserving raw_data
            parsed_payload = {
                "caller": raw_dict.get("caller") or raw_dict.get("from") or raw_dict.get("from_number"),
                "receiver": raw_dict.get("receiver") or raw_dict.get("to") or raw_dict.get("to_number"),
                "phone_number": raw_dict.get("phone_number") or raw_dict.get("number") or raw_dict.get("phone"),
                "direction": raw_dict.get("direction") or raw_dict.get("type"),
                "timestamp": raw_dict.get("timestamp") or raw_dict.get("time") or raw_dict.get("date"),
                "duration": raw_dict.get("duration") or raw_dict.get("duration_seconds") or raw_dict.get("length"),
                "status": raw_dict.get("status") or raw_dict.get("result"),
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
