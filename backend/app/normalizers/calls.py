from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import (
    create_entity_ref,
    normalize_application_name,
    normalize_phone_number,
)
from backend.app.normalizers.timestamps import normalize_timestamp


class CallNormalizer(BaseArtifactNormalizer):
    """Normalizes telephonic call logs and voice sessions into canonical representation."""

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CALL

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization
        ts_res = normalize_timestamp(data.get("timestamp"))
        if ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {data.get('timestamp')}"))

        # 2. Entity & Phone Normalization
        entities: List[Dict[str, Any]] = []

        caller_norm, caller_orig = normalize_phone_number(data.get("caller"))
        if caller_orig:
            entities.append(create_entity_ref(EntityType.PHONE_NUMBER, caller_orig, "caller", caller_norm))

        receiver_norm, receiver_orig = normalize_phone_number(data.get("receiver"))
        if receiver_orig:
            entities.append(create_entity_ref(EntityType.PHONE_NUMBER, receiver_orig, "receiver", receiver_norm))

        phone_norm, phone_orig = normalize_phone_number(data.get("phone_number"))
        if phone_orig and phone_orig not in (caller_orig, receiver_orig):
            entities.append(create_entity_ref(EntityType.PHONE_NUMBER, phone_orig, "party", phone_norm))

        # Check for missing parties
        if not caller_orig and not receiver_orig and not phone_orig:
            warnings.append(self.create_warning("parties", "MISSING_CALL_PARTIES", "Neither caller, receiver, nor phone number was specified."))

        # 3. Application Normalization
        canon_app, orig_app = normalize_application_name(data.get("application") or "Phone")
        if canon_app:
            entities.append(create_entity_ref(EntityType.APPLICATION, orig_app or canon_app, "application", canon_app))

        # 4. Safe Duration Parsing
        duration_raw = data.get("duration")
        duration_sec: Optional[int] = None
        if duration_raw is not None:
            try:
                duration_sec = int(float(str(duration_raw).strip()))
            except (ValueError, TypeError):
                warnings.append(self.create_warning("duration", "INVALID_DURATION", f"Non-numeric duration: {duration_raw}"))

        # 5. Descriptive Content Synthesis (Preserving provenance)
        direction = str(data.get("direction") or "UNKNOWN").upper()
        status_val = str(data.get("status") or "UNKNOWN").upper()
        p1 = caller_norm or caller_orig or "Unknown"
        p2 = receiver_norm or receiver_orig or "Unknown"
        dur_str = f"{duration_sec}s" if duration_sec is not None else "duration unknown"
        content = f"Call ({direction}): {p1} -> {p2} [{dur_str}, Status: {status_val}]"

        metadata = {
            "caller": caller_orig,
            "receiver": receiver_orig,
            "caller_normalized": caller_norm,
            "receiver_normalized": receiver_norm,
            "phone_number": phone_orig,
            "direction": direction,
            "duration_seconds": duration_sec,
            "call_status": status_val,
            "source_tag": data.get("source_tag"),
        }

        has_critical = (not caller_orig and not receiver_orig and not phone_orig) or ts_res.status == TimestampStatus.INVALID
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
