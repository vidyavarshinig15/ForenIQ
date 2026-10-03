from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="ok", description="Operational health status of the API")


class ReadyResponse(BaseModel):
    """Readiness probe schema verifying dependent subsystem connections."""
    status: str = Field(default="ready", description="Overall readiness status")
    database: str = Field(default="connected", description="Relational database connectivity")
    storage: str = Field(default="writable", description="Storage subsystem status")
    version: str = Field(default="1.0.0", description="Application version")
    details: Optional[Dict[str, Any]] = None
