import hashlib
import uuid
from typing import List, Optional

from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.registry import NormalizationRegistry, get_default_registry


class NormalizationPipeline:
    """
    Orchestrates modular normalization stages:
    Artifact Type Dispatch -> Normalizer Execution -> Deterministic Stable Identity -> Canonical Model Creation.
    """

    def __init__(self, registry: Optional[NormalizationRegistry] = None) -> None:
        self.registry = registry or get_default_registry()

    def normalize(
        self,
        raw_artifact: RawArtifact,
        processing_job_id: Optional[uuid.UUID] = None,
    ) -> CanonicalEvidence:
        """
        Transforms a single RawArtifact into a CanonicalEvidence model instance
        with deterministic UUIDv5 identifier and cryptographic fingerprint.
        """
        normalizer = self.registry.get_normalizer(raw_artifact.artifact_type)
        dto = normalizer.normalize(raw_artifact)

        # Stable, deterministic identity key derivation
        identity_key = (
            f"{raw_artifact.evidence_id}:{dto.artifact_type.value}:"
            f"{dto.source_file}:{dto.source_path}:{dto.record_identifier}"
        )
        canonical_fingerprint = hashlib.sha256(identity_key.encode("utf-8")).hexdigest()
        deterministic_id = uuid.uuid5(raw_artifact.evidence_id, identity_key)

        return CanonicalEvidence(
            id=deterministic_id,
            case_id=raw_artifact.case_id,
            evidence_id=raw_artifact.evidence_id,
            raw_artifact_id=raw_artifact.id,
            processing_job_id=processing_job_id,
            artifact_type=dto.artifact_type,
            canonical_fingerprint=canonical_fingerprint,
            source_file=dto.source_file,
            source_path=dto.source_path,
            record_identifier=dto.record_identifier,
            event_timestamp=dto.event_timestamp,
            timestamp_precision=dto.timestamp_precision,
            timestamp_status=dto.timestamp_status,
            original_timestamp=dto.original_timestamp,
            original_timezone=dto.original_timezone,
            device_id=dto.device_id,
            application=dto.application,
            original_application=dto.original_application,
            content=dto.content,
            entities=dto.entities,
            metadata_=dto.metadata,
            data_quality_status=dto.data_quality_status,
            validation_warnings=dto.validation_warnings,
            parser_version=dto.parser_version,
            normalizer_version=dto.normalizer_version,
        )

    def normalize_batch(
        self,
        raw_artifacts: List[RawArtifact],
        processing_job_id: Optional[uuid.UUID] = None,
    ) -> List[CanonicalEvidence]:
        """Normalizes a collection of RawArtifacts into CanonicalEvidence models."""
        return [self.normalize(art, processing_job_id=processing_job_id) for art in raw_artifacts]
