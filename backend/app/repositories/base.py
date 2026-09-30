from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from backend.app.models.base import BaseDomainModel

ModelType = TypeVar("ModelType", bound=BaseDomainModel)


class BaseRepository(ABC, Generic[ModelType]):
    """
    Abstract Base Repository establishing the data access contract.
    Decouples storage engines (PostgreSQL, MongoDB, In-Memory) from domain logic.
    """

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Optional[ModelType]:
        """Fetch a single record by primary UUID."""
        pass

    @abstractmethod
    async def list_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Fetch paginated records."""
        pass

    @abstractmethod
    async def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity record."""
        pass

    @abstractmethod
    async def update(self, entity_id: UUID, values: dict[str, Any]) -> Optional[ModelType]:
        """Update an existing entity record."""
        pass

    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Remove an entity record."""
        pass
