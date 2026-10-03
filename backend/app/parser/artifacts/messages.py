import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class MessageArtifactParser(BaseArtifactParser):
    """
    Parser for SMS, MMS, WhatsApp, Telegram, Instagram, and generic instant messaging records.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.MESSAGE

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        msg_indicators = [
            "message", "messages", "chat", "chats", "sms", "mms",
            "whatsapp", "telegram", "instagram", "im", "conversation"
        ]
        return any(ind in path_lower for ind in msg_indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {
            "message", "chat_message", "sms", "mms", "im_message",
            "whatsapp_message", "telegram_message", "item", "entry", "record"
        }
        path_lower = item.path.lower()

        # Heuristic application identification from source path
        default_app = "SMS"
        if "whatsapp" in path_lower:
            default_app = "WhatsApp"
        elif "telegram" in path_lower:
            default_app = "Telegram"
        elif "instagram" in path_lower:
            default_app = "Instagram"
        elif "signal" in path_lower:
            default_app = "Signal"
        elif "mms" in path_lower:
            default_app = "MMS"

        idx = 0
        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("msg_id")
                or raw_dict.get("record_id")
                or f"{item.path}#msg_{idx}"
            )

            # Extract body/text
            content = (
                raw_dict.get("body")
                or raw_dict.get("text")
                or raw_dict.get("content")
                or raw_dict.get("message")
                or raw_dict.get("message_text")
                or raw_dict.get("_value")
            )

            parsed_payload = {
                "sender": raw_dict.get("sender") or raw_dict.get("from") or raw_dict.get("from_address"),
                "receiver": raw_dict.get("receiver") or raw_dict.get("to") or raw_dict.get("recipient"),
                "timestamp": raw_dict.get("timestamp") or raw_dict.get("time") or raw_dict.get("date"),
                "content": content,
                "direction": raw_dict.get("direction") or raw_dict.get("type"),
                "application": raw_dict.get("app") or raw_dict.get("application") or default_app,
                "status": raw_dict.get("status") or raw_dict.get("read"),
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
