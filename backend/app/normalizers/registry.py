import logging
from typing import Dict, Optional

from backend.app.models.enums import ArtifactType
from backend.app.normalizers.applications import ApplicationNormalizer
from backend.app.normalizers.base import BaseArtifactNormalizer
from backend.app.normalizers.browser import BrowserNormalizer
from backend.app.normalizers.calls import CallNormalizer
from backend.app.normalizers.contacts import ContactNormalizer
from backend.app.normalizers.filesystem import FilesystemNormalizer
from backend.app.normalizers.generic import GenericNormalizer
from backend.app.normalizers.location import LocationNormalizer
from backend.app.normalizers.messages import MessageNormalizer

logger = logging.getLogger(__name__)


class NormalizationRegistry:
    """
    Central dispatch registry for artifact normalizers.
    Allows dynamic lookup and registration without hard-coded conditional chains.
    """

    def __init__(self) -> None:
        self._normalizers: Dict[ArtifactType, BaseArtifactNormalizer] = {}
        self._fallback_normalizer = GenericNormalizer()

    def register(self, normalizer: BaseArtifactNormalizer) -> None:
        """Register a normalizer for its target artifact type."""
        self._normalizers[normalizer.artifact_type] = normalizer
        logger.debug(f"[NormalizationRegistry] Registered normalizer for {normalizer.artifact_type.value}")

    def get_normalizer(self, artifact_type: ArtifactType) -> BaseArtifactNormalizer:
        """Retrieve the appropriate normalizer or fall back to GenericNormalizer."""
        return self._normalizers.get(artifact_type, self._fallback_normalizer)


_global_registry: Optional[NormalizationRegistry] = None


def get_default_registry() -> NormalizationRegistry:
    """Factory returning the globally configured NormalizationRegistry populated with core domain normalizers."""
    global _global_registry
    if _global_registry is not None:
        return _global_registry

    registry = NormalizationRegistry()
    registry.register(CallNormalizer())
    registry.register(MessageNormalizer())
    registry.register(ContactNormalizer())
    registry.register(LocationNormalizer())
    registry.register(BrowserNormalizer())
    registry.register(ApplicationNormalizer())
    registry.register(FilesystemNormalizer())

    _global_registry = registry
    return _global_registry
