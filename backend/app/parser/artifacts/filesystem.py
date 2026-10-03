import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class FilesystemArtifactParser(BaseArtifactParser):
    """
    Parser for filesystem hierarchy, file entries, and storage metadata.
    Can extract from specialized filesystem XML catalogs or generate metadata from archive inventory entries.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.FILESYSTEM

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        indicators = ["file", "files", "filesystem", "metadata", "file_list", "directory"]
        return any(ind in path_lower for ind in indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"file", "file_record", "filesystem_item", "entry", "item", "node"}
        idx = 0

        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("file_id")
                or f"{item.path}#file_{idx}"
            )

            file_path = raw_dict.get("path") or raw_dict.get("full_path") or raw_dict.get("filepath")
            filename = raw_dict.get("name") or raw_dict.get("filename")
            if not filename and file_path:
                filename = os.path.basename(file_path)

            parsed_payload = {
                "path": file_path,
                "filename": filename,
                "size": raw_dict.get("size") or raw_dict.get("file_size") or raw_dict.get("length"),
                "created_time": raw_dict.get("created") or raw_dict.get("ctime") or raw_dict.get("created_time"),
                "modified_time": raw_dict.get("modified") or raw_dict.get("mtime") or raw_dict.get("modified_time"),
                "access_time": raw_dict.get("accessed") or raw_dict.get("atime") or raw_dict.get("access_time"),
                "md5": raw_dict.get("md5"),
                "sha256": raw_dict.get("sha256"),
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
