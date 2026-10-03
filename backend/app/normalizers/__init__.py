"""
Evidence Normalization Subsystem (Phase 7).
Transforms heterogeneous RawArtifact records into unified CanonicalEvidence records
preserving stable IDs, normalized timestamps, entity references, and complete provenance.
"""

from backend.app.normalizers.dto import NormalizedRecordDTO
from backend.app.normalizers.pipeline import NormalizationPipeline
from backend.app.normalizers.registry import NormalizationRegistry, get_default_registry

__all__ = [
    "NormalizedRecordDTO",
    "NormalizationPipeline",
    "NormalizationRegistry",
    "get_default_registry",
]
