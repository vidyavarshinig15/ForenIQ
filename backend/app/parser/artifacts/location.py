import os
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord
from backend.app.parser.xml_parser import stream_xml_records


class LocationArtifactParser(BaseArtifactParser):
    """
    Parser for forensic geospatial fixes, waypoints, and location tracking entries.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.LOCATION

    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        if item.extension != ".xml":
            return False
        path_lower = item.path.lower()
        indicators = ["location", "locations", "gps", "geo", "waypoint", "coordinates", "places"]
        return any(ind in path_lower for ind in indicators)

    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        if not os.path.exists(extracted_file_path):
            return

        target_tags = {"location", "waypoint", "point", "gps_record", "entry", "item", "fix"}
        idx = 0

        for tag_name, raw_dict in stream_xml_records(extracted_file_path, target_tags=target_tags):
            idx += 1
            record_id = (
                raw_dict.get("id")
                or raw_dict.get("@id")
                or raw_dict.get("loc_id")
                or f"{item.path}#loc_{idx}"
            )

            # Extract latitude/longitude
            lat = raw_dict.get("latitude") or raw_dict.get("lat")
            lon = raw_dict.get("longitude") or raw_dict.get("lon") or raw_dict.get("lng")

            # Try to safely cast to float if valid
            try:
                lat_val = float(lat) if lat is not None else None
            except (ValueError, TypeError):
                lat_val = lat

            try:
                lon_val = float(lon) if lon is not None else None
            except (ValueError, TypeError):
                lon_val = lon

            parsed_payload = {
                "latitude": lat_val,
                "longitude": lon_val,
                "timestamp": raw_dict.get("timestamp") or raw_dict.get("time") or raw_dict.get("date"),
                "source": raw_dict.get("source") or raw_dict.get("provider") or "GPS",
                "accuracy": raw_dict.get("accuracy") or raw_dict.get("precision"),
                "altitude": raw_dict.get("altitude") or raw_dict.get("alt"),
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
