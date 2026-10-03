from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import create_entity_ref
from backend.app.normalizers.timestamps import normalize_timestamp


class FilesystemNormalizer(BaseArtifactNormalizer):
    """
    Normalizes extracted file catalog entries, filesystem nodes, and file attributes.
    Preserves raw filesystem paths without alteration.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.FILESYSTEM

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization (prioritize modified, then created, then accessed)
        raw_ts = (
            data.get("modified_at")
            or data.get("modified_time")
            or data.get("created_at")
            or data.get("created_time")
            or data.get("accessed_at")
            or data.get("access_time")
            or data.get("timestamp")
        )
        ts_res = normalize_timestamp(raw_ts)
        if raw_ts and ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse file timestamp: {raw_ts}"))

        # 2. Path & Filename
        path_raw = data.get("path")
        filename_raw = data.get("filename")
        if not path_raw and not filename_raw:
            warnings.append(self.create_warning("path", "MISSING_FILE_PATH", "Neither file path nor filename was provided.", severity="ERROR"))

        # 3. Size Parsing
        size_raw = data.get("size_bytes") if data.get("size_bytes") is not None else (data.get("size") if data.get("size") is not None else data.get("file_size"))
        size_bytes: Optional[int] = None
        if size_raw is not None:
            try:
                size_bytes = int(size_raw)
            except (ValueError, TypeError):
                warnings.append(self.create_warning("size", "INVALID_SIZE", f"Non-integer file size: {size_raw}"))

        # 4. Content Synthesis
        content = str(path_raw or filename_raw or "Unnamed File Node")
        if size_bytes is not None:
            content += f" ({size_bytes} bytes)"

        # 5. Entities
        entities: List[Dict[str, Any]] = []
        if filename_raw:
            entities.append(create_entity_ref(EntityType.ACCOUNT, filename_raw, "filename", str(filename_raw)))

        metadata = {
            "path": path_raw,
            "filename": filename_raw,
            "size_bytes": size_bytes,
            "created_time": data.get("created_time"),
            "modified_time": data.get("modified_time"),
            "access_time": data.get("access_time"),
            "md5": data.get("md5"),
            "sha256": data.get("sha256"),
            "source_tag": data.get("source_tag"),
        }

        has_critical = not path_raw and not filename_raw
        quality_status = self.calculate_quality_status(warnings, has_critical_missing=has_critical)

        return NormalizedRecordDTO(
            artifact_type=self.artifact_type,
            source_file=raw_artifact.source_file,
            source_path=raw_artifact.source_path,
            record_identifier=raw_artifact.record_identifier,
            event_timestamp=ts_res.normalized_utc,
            timestamp_precision=ts_res.precision,
            timestamp_status=ts_res.status,
            original_timestamp=ts_res.original_timestamp,
            original_timezone=ts_res.original_timezone,
            application="Filesystem",
            original_application=None,
            content=content,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )
