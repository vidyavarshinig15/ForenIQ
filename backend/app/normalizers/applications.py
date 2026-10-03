from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import create_entity_ref, normalize_application_name
from backend.app.normalizers.timestamps import normalize_timestamp


class ApplicationNormalizer(BaseArtifactNormalizer):
    """
    Normalizes installed applications, version catalogs, and runtime usage events.
    Records system events without inferring intent.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.APPLICATION

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization
        ts_res = normalize_timestamp(data.get("timestamp") or data.get("install_time"))
        if ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {data.get('timestamp')}"))

        # 2. Application & Package Entities
        app_raw = data.get("application") or data.get("name")
        pkg_raw = data.get("package_name")

        canon_app, orig_app = normalize_application_name(app_raw or pkg_raw or "Application")
        entities: List[Dict[str, Any]] = []

        if canon_app:
            entities.append(create_entity_ref(EntityType.APPLICATION, orig_app or canon_app, "app_name", canon_app))

        if pkg_raw:
            entities.append(create_entity_ref(EntityType.ACCOUNT, pkg_raw, "package_id", str(pkg_raw).strip()))

        if not app_raw and not pkg_raw:
            warnings.append(self.create_warning("application", "MISSING_APP_NAME", "Neither application name nor package identifier was provided."))

        # 3. Version & Event Type
        version_str = str(data.get("version")).strip() if data.get("version") else None
        event_type = str(data.get("event_type") or "INSTALLED").upper()

        # 4. Content Synthesis
        v_part = f" v{version_str}" if version_str else ""
        pkg_part = f" ({pkg_raw})" if pkg_raw else ""
        content = f"Application {event_type}: {canon_app or 'Unknown'}{v_part}{pkg_part}"

        metadata = {
            "application": canon_app,
            "original_application": orig_app,
            "package_name": pkg_raw,
            "version": version_str,
            "event_type": event_type,
            "duration": data.get("duration"),
            "source_tag": data.get("source_tag"),
        }

        has_critical = not app_raw and not pkg_raw
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
            application=canon_app,
            original_application=orig_app,
            content=content,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )
