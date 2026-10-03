import logging
from typing import Dict, List, Optional

from backend.app.models.enums import ArtifactType
from backend.app.parser.artifacts import (
    ApplicationArtifactParser,
    BrowserArtifactParser,
    CallArtifactParser,
    ContactArtifactParser,
    FilesystemArtifactParser,
    LocationArtifactParser,
    MessageArtifactParser,
)
from backend.app.parser.base import BaseArtifactParser
from backend.app.parser.models import ArchiveInventoryItem

logger = logging.getLogger(__name__)


class ArtifactParserRegistry:
    """
    Central registry for extensible forensic artifact parsers.
    Allows independent parsers to be registered, queried, and dispatched dynamically.
    """

    def __init__(self) -> None:
        self._parsers: List[BaseArtifactParser] = []

    def register(self, parser: BaseArtifactParser) -> None:
        """Register a new artifact parser."""
        self._parsers.append(parser)
        logger.debug(f"Registered artifact parser: {parser.__class__.__name__} for {parser.artifact_type}")

    def get_parsers_for_item(self, item: ArchiveInventoryItem) -> List[BaseArtifactParser]:
        """Return all registered parsers capable of handling this archive item."""
        matched = []
        for parser in self._parsers:
            try:
                if parser.can_parse(item):
                    matched.append(parser)
            except Exception as e:
                logger.warning(f"Error checking can_parse on {parser.__class__.__name__}: {e}")
        return matched

    def get_all_parsers(self) -> List[BaseArtifactParser]:
        return list(self._parsers)


# Initialize default registry instance with all standard forensic parsers
default_registry = ArtifactParserRegistry()
default_registry.register(CallArtifactParser())
default_registry.register(MessageArtifactParser())
default_registry.register(ContactArtifactParser())
default_registry.register(LocationArtifactParser())
default_registry.register(BrowserArtifactParser())
default_registry.register(ApplicationArtifactParser())
default_registry.register(FilesystemArtifactParser())


def get_default_registry() -> ArtifactParserRegistry:
    return default_registry
