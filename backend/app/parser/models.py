from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.models.enums import ArtifactType


@dataclass
class ArchiveInventoryItem:
    """Metadata for an individual member inside an evidence archive."""
    path: str
    file_size: int
    compressed_size: int
    extension: str
    detected_type: str = "binary"
    depth: int = 0
    is_nested_archive: bool = False


@dataclass
class ParsedArtifactRecord:
    """
    In-memory representation of an extracted raw artifact.
    Must preserve full source provenance for downstream evidence grounding.
    """
    artifact_type: ArtifactType
    source_file: str
    source_path: str
    record_identifier: str
    raw_data: Dict[str, Any]
    parsed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ProcessingSummary:
    """Execution summary of an ingestion & parsing run."""
    files_total: int = 0
    files_processed: int = 0
    files_failed: int = 0
    artifacts_extracted: int = 0
    counts_by_type: Dict[str, int] = field(default_factory=lambda: {
        ArtifactType.CALL.value: 0,
        ArtifactType.MESSAGE.value: 0,
        ArtifactType.CONTACT.value: 0,
        ArtifactType.LOCATION.value: 0,
        ArtifactType.BROWSER.value: 0,
        ArtifactType.APPLICATION.value: 0,
        ArtifactType.FILESYSTEM.value: 0,
    })
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_total": self.files_total,
            "files_processed": self.files_processed,
            "files_failed": self.files_failed,
            "artifacts_extracted": self.artifacts_extracted,
            "counts_by_type": self.counts_by_type,
            "warnings": self.warnings,
            "errors": self.errors,
        }
