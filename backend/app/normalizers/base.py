from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType, DataQualityStatus
from backend.app.models.raw_artifact import RawArtifact
from backend.app.normalizers.dto import NormalizedRecordDTO


class BaseArtifactNormalizer(ABC):
    """
    Abstract base class for all forensic artifact normalizers.
    Transforms source-specific RawArtifact payloads into standardized NormalizedRecordDTOs.
    """

    @property
    @abstractmethod
    def artifact_type(self) -> ArtifactType:
        """The canonical artifact type handled by this normalizer."""
        pass

    def can_normalize(self, raw_artifact: RawArtifact) -> bool:
        """Determines whether this normalizer can process the given raw artifact."""
        return raw_artifact.artifact_type == self.artifact_type

    @abstractmethod
    def normalize(self, raw_artifact: RawArtifact) -> NormalizedRecordDTO:
        """Execute normalization logic against a raw artifact."""
        pass

    @staticmethod
    def create_warning(field: str, code: str, message: str, severity: str = "WARNING") -> Dict[str, Any]:
        """Produce a structured validation warning."""
        return {
            "field": field,
            "code": code,
            "message": message,
            "severity": severity,
        }

    @staticmethod
    def calculate_quality_status(warnings: List[Dict[str, Any]], has_critical_missing: bool = False) -> DataQualityStatus:
        """Derive data quality classification from validation findings."""
        has_error = any(w.get("severity") == "ERROR" for w in warnings)
        if has_error:
            return DataQualityStatus.INVALID

        if has_critical_missing:
            return DataQualityStatus.PARTIAL

        if warnings:
            return DataQualityStatus.PARTIAL

        return DataQualityStatus.VALID
