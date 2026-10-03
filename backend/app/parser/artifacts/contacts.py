import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class ContactArtifactParser(BaseArtifactParser):
    """
    Parser for address book and device contacts.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CONTACT

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        indicators = ["contact", "contacts", "addressbook", "people", "phonebook"]
        return any(ind in path_lower for ind in indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"contact", "person", "entry", "item", "contactitem"}
        idx = 0

        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("contact_id")
                or f"{item.path}#contact_{idx}"
            )

            # Name normalization
            name = (
                raw_dict.get("name")
                or raw_dict.get("display_name")
                or raw_dict.get("full_name")
            )
            if not name and ("first_name" in raw_dict or "last_name" in raw_dict):
                fn = raw_dict.get("first_name", "") or ""
                ln = raw_dict.get("last_name", "") or ""
                name = f"{fn} {ln}".strip()

            parsed_payload = {
                "name": name,
                "phone": raw_dict.get("phone") or raw_dict.get("phone_number") or raw_dict.get("number"),
                "email": raw_dict.get("email") or raw_dict.get("email_address"),
                "account": raw_dict.get("account") or raw_dict.get("account_type"),
                "notes": raw_dict.get("notes") or raw_dict.get("note"),
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
