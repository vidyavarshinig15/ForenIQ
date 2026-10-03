from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, DataQualityStatus, TimestampPrecision, TimestampStatus


@dataclass
class NormalizedRecordDTO:
    """Internal data transfer object holding normalized artifact attributes before database persistence."""
    artifact_type: ArtifactType
    source_file: str
    source_path: str
    record_identifier: str
    event_timestamp: Optional[datetime] = None
    timestamp_precision: TimestampPrecision = TimestampPrecision.UNKNOWN
    timestamp_status: TimestampStatus = TimestampStatus.UNKNOWN
    original_timestamp: Optional[str] = None
    original_timezone: Optional[str] = None
    device_id: Optional[str] = None
    application: Optional[str] = None
    original_application: Optional[str] = None
    content: Optional[str] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    data_quality_status: DataQualityStatus = DataQualityStatus.VALID
    validation_warnings: List[Dict[str, Any]] = field(default_factory=list)
    parser_version: str = "1.0.0"
    normalizer_version: str = "1.0.0"
