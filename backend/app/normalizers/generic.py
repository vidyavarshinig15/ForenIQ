from typing import Any, Dict, List

from backend.app.models.enums import ArtifactType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.timestamps import normalize_timestamp


class GenericNormalizer(BaseArtifactNormalizer):
    """Fallback normalizer for extensible, emerging, or generic forensic artifact types."""

    def __init__(self, target_type: ArtifactType = ArtifactType.DEVICE_EVENT) -> None:
        self._target_type = target_type

    @property
    def artifact_type(self) -> ArtifactType:
        return self._target_type

    def can_normalize(self, raw_artifact: RawArtifact) -> bool:
        return True

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        raw_ts = data.get("timestamp") or data.get("time") or data.get("date")
        ts_res = normalize_timestamp(raw_ts)
        if raw_ts and ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {raw_ts}"))

        content = data.get("content") or data.get("title") or data.get("description") or f"Record {raw_artifact.record_identifier}"

        quality_status = self.calculate_quality_status(warnings)

        return NormalizedRecordDTO(
            artifact_type=raw_artifact.artifact_type,
            source_file=raw_artifact.source_file,
            source_path=raw_artifact.source_path,
            record_identifier=raw_artifact.record_identifier,
            event_timestamp=ts_res.normalized_utc,
            timestamp_precision=ts_res.precision,
            timestamp_status=ts_res.status,
            original_timestamp=ts_res.original_timestamp,
            original_timezone=ts_res.original_timezone,
            application=data.get("application") or data.get("app"),
            original_application=data.get("application") or data.get("app"),
            content=str(content),
            entities=[],
            metadata=dict(data),
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )
