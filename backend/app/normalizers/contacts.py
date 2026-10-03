from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, EntityType, TimestampPrecision, TimestampStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.entities import (
    create_entity_ref,
    normalize_email,
    normalize_phone_number,
)
from backend.app.normalizers.timestamps import normalize_timestamp


class ContactNormalizer(BaseArtifactNormalizer):
    """Normalizes address book contacts, vCards, and phonebook entities."""

    @property
    def artifact_type(self) -> ArtifactType:
        return ArtifactType.CONTACT

    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        data = raw_artifact.raw_data or {}
        warnings: List[Dict[str, Any]] = []

        # 1. Timestamp (contacts may have created/modified timestamps or None)
        ts_res = normalize_timestamp(data.get("timestamp") or data.get("created_time") or data.get("modified_time"))

        # 2. Name & Communication Entities
        name_raw = data.get("name")
        phones_raw = data.get("phone_numbers") or data.get("phone") or data.get("number") or []
        if isinstance(phones_raw, (str, int, float)):
            phones_list = [str(phones_raw)]
        elif isinstance(phones_raw, list):
            phones_list = [str(p) for p in phones_raw if p]
        else:
            phones_list = []

        emails_raw = data.get("emails") or data.get("email") or data.get("email_address") or []
        if isinstance(emails_raw, str):
            emails_list = [emails_raw]
        elif isinstance(emails_raw, list):
            emails_list = [str(e) for e in emails_raw if e]
        else:
            emails_list = []

        account_raw = data.get("account")
        notes_raw = data.get("notes")

        entities: List[Dict[str, Any]] = []

        if name_raw:
            entities.append(create_entity_ref(EntityType.PERSON, name_raw, "contact_name", str(name_raw).strip()))

        phones_normalized = []
        for p in phones_list:
            p_norm, _ = normalize_phone_number(p)
            entities.append(create_entity_ref(EntityType.PHONE_NUMBER, p, "contact_phone", p_norm))
            if p_norm:
                phones_normalized.append(p_norm)

        emails_normalized = []
        for e in emails_list:
            e_norm, _ = normalize_email(e)
            entities.append(create_entity_ref(EntityType.EMAIL, e, "contact_email", e_norm))
            if e_norm:
                emails_normalized.append(e_norm)

        if account_raw:
            entities.append(create_entity_ref(EntityType.ACCOUNT, account_raw, "contact_account", str(account_raw).strip()))

        if not name_raw and not phones_list and not emails_list:
            warnings.append(self.create_warning("contact", "MISSING_CONTACT_DETAILS", "Contact has no name, phone, or email."))

        # 3. Content Synthesis
        parts = []
        if name_raw:
            parts.append(str(name_raw).strip())
        if phones_normalized:
            parts.append(f"Phones: {', '.join(phones_normalized)}")
        elif phones_list:
            parts.append(f"Phones: {', '.join(phones_list)}")
        if emails_normalized:
            parts.append(f"Emails: {', '.join(emails_normalized)}")
        elif emails_list:
            parts.append(f"Emails: {', '.join(emails_list)}")

        content_str = " | ".join(parts) if parts else "Unnamed Contact"

        metadata = {
            "name": name_raw,
            "phone_numbers": phones_list,
            "phone_numbers_normalized": phones_normalized,
            "emails": emails_list,
            "emails_normalized": emails_normalized,
            "account": account_raw,
            "notes": notes_raw,
        }

        has_critical = not name_raw and not phones_list and not emails_list
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
            application="Contacts",
            original_application=None,
            content=content_str,
            entities=entities,
            metadata=metadata,
            data_quality_status=quality_status,
            validation_warnings=warnings,
            parser_version="1.0.0",
            normalizer_version="1.0.0",
        )
