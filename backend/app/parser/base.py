from abc import ABC, abstractmethod
from typing import Any, Dict, Generator

from backend.app.models.enums import ArtifactType
from backend.app.parser.models import ArchiveInventoryItem, ParsedArtifactRecord


class BaseArtifactParser(ABC):
    """
    Abstract base class for all forensic artifact parsers.
    Parsers are responsible for recognizing target file structures and transforming them
    into streamable ParsedArtifactRecord instances without loss of provenance.
    """

    @property
    @abstractmethod
    def artifact_type(self) -> ArtifactType:
        """The primary artifact category handled by this parser."""
        pass

    @abstractmethod
    def can_parse(self, item: ArchiveInventoryItem) -> bool:
        """Determines if this parser is capable of handling the specified archive member."""
        pass

    @abstractmethod
    def parse(
        self,
        extracted_file_path: str,
        item: ArchiveInventoryItem,
        context: Dict[str, Any],
    ) -> Generator[ParsedArtifactRecord, None, None]:
        """
        Extracts records from the local file and yields ParsedArtifactRecord instances.
        context includes: 'case_id', 'evidence_id', 'job_id'.
        """
        pass
