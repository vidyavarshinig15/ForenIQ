from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from backend.app.core.errors import EntityNotFoundException
from backend.app.models.base import BaseDomainModel
from backend.app.repositories.base import BaseRepository

ModelType = TypeVar("ModelType", bound=BaseDomainModel)


class BaseService(Generic[ModelType]):
    """
    Abstract Service Layer pattern.
    Encapsulates core business rules, audit triggers, and orchestrates repository calls.
    """

    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository

    async def get(self, entity_id: UUID) -> ModelType:
        entity = await self.repository.get_by_id(entity_id)
        if not entity:
            raise EntityNotFoundException(f"Resource with ID {entity_id} was not found.")
        return entity

    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return await self.repository.list_all(skip=skip, limit=limit)

    async def create(self, entity: ModelType) -> ModelType:
        return await self.repository.create(entity)

    async def update(self, entity_id: UUID, values: dict[str, Any]) -> ModelType:
        updated = await self.repository.update(entity_id, values)
        if not updated:
            raise EntityNotFoundException(f"Resource with ID {entity_id} was not found to update.")
        return updated

    async def delete(self, entity_id: UUID) -> bool:
        deleted = await self.repository.delete(entity_id)
        if not deleted:
            raise EntityNotFoundException(f"Resource with ID {entity_id} was not found to delete.")
        return True
