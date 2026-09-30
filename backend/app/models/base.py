from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class BaseDomainModel(BaseModel):
    """
    Foundational domain entity model.
    Establishes uniform UUID identifiers and UTC timestamps for all entities.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique primary identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="UTC last update timestamp"
    )

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }
