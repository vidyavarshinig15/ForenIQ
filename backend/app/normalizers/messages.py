from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import (
    create_entity_ref,
    normalize_application_name,
    normalize_email,
    normalize_phone_number,
)
from backend.app.normalizers.timestamps import normalize_timestamp


class MessageNormalizer(BaseArtifactNormalizer):
    """
    Normalizes SMS, MMS, WhatsApp, Telegram, Signal, and Instant Messaging records.
    Preserves exact textual content without lossy transformations or redaction.
    """

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.MESSAGE

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp Normalization
        ts_res = normalize_timestamp(data.get("timestamp"))
        if ts_res.status == TimestampStatus.INVALID:
            warnings.append(self.create_warning("timestamp", "INVALID_TIMESTAMP", f"Unable to parse timestamp: {data.get('timestamp')}"))

        # 2. Entity Normalization (Sender / Receiver)
        entities: List[Dict[str, Any]] = []

        # Sender
        sender_raw = data.get("sender")
        if sender_raw:
            phone_norm, _ = normalize_phone_number(sender_raw)
            email_norm, _ = normalize_email(sender_raw)
            entity_type = EntityType.PHONE_NUMBER if phone_norm else (EntityType.EMAIL if email_norm else EntityType.ACCOUNT)
            norm_val = phone_norm or email_norm or str(sender_raw).strip()
            entities.append(create_entity_ref(entity_type, sender_raw, "sender", norm_val))

        # Receiver
        receiver_raw = data.get("receiver")
        if receiver_raw:
            phone_norm, _ = normalize_phone_number(receiver_raw)
            email_norm, _ = normalize_email(receiver_raw)
            entity_type = EntityType.PHONE_NUMBER if phone_norm else (EntityType.EMAIL if email_norm else EntityType.ACCOUNT)
            norm_val = phone_norm or email_norm or str(receiver_raw).strip()
            entities.append(create_entity_ref(entity_type, receiver_raw, "receiver", norm_val))

        if not sender_raw and not receiver_raw:
            warnings.append(self.create_warning("parties", "MISSING_MESSAGE_PARTIES", "Neither sender nor receiver was specified."))

        # 3. Application Normalization
        canon_app, orig_app = normalize_application_name(data.get("application") or data.get("app") or "Messages")
        if canon_app:
            entities.append(create_entity_ref(EntityType.APPLICATION, orig_app or canon_app, "application", canon_app))

        # 4. Message Content (Verbatim Preservation)
        content_val = data.get("content")
        if content_val is None:
            content_val = data.get("body") or data.get("text") or data.get("message")
        content_str = str(content_val) if content_val is not None else None
        if content_str is None or not content_str.strip():
            warnings.append(self.create_warning("content", "EMPTY_MESSAGE_BODY", "Message content body is empty or null."))

        metadata = {
            "sender": sender_raw,
            "receiver": receiver_raw,
            "direction": str(data.get("direction") or "UNKNOWN").upper(),
            "message_status": str(data.get("status") or "UNKNOWN").upper(),
            "source_tag": data.get("source_tag"),
        }

        has_critical = (not sender_raw and not receiver_raw) or (content_str is None and ts_res.status == TimestampStatus.INVALID)
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
            content=content_str,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )
