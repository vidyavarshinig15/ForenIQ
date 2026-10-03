"""
Phase 11 — Investigation Query Schemas

Defines Pydantic models for natural-language query interpretation, intent classification,
entity extraction, temporal constraints, retrieval plan generation, and investigator responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from backend.app.models.enums import EntityType, InvestigationIntent, SearchMode
from backend.app.schemas.search import SearchFacets, SearchPagination, SearchResultItem


class ExtractedEntity(BaseModel):
    """Forensic entity extracted from investigator natural-language query."""
    type: EntityType
    text: str
    normalized_value: str
    start_pos: int = 0
    end_pos: int = 0
    extraction_method: str = "PATTERN"  # "PATTERN", "RULE", "SPACY"
    confidence: float = 1.0


class TemporalConstraint(BaseModel):
    """Structured time constraint derived from temporal expressions."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    raw_text: str
    timezone: Optional[str] = "UTC"
    precision: str = "SECOND"  # "SECOND", "MINUTE", "HOUR", "DAY", "MONTH", "YEAR"


class InvestigationIntentResult(BaseModel):
    """Categorized investigative intent with parser confidence."""
    type: InvestigationIntent
    confidence: float = Field(ge=0.0, le=1.0, description="Model/rule confidence score (0.0 to 1.0)")
    explanation: str


class InvestigationQueryInterpretation(BaseModel):
    """Complete structured interpretation of natural language input."""
    intent: InvestigationIntentResult
    entities: List[ExtractedEntity] = []
    temporal_constraints: List[TemporalConstraint] = []
    artifact_types: List[str] = []
    filters: Dict[str, Any] = {}
    search_text: str = ""
    recommended_mode: SearchMode = SearchMode.HYBRID


class InvestigationRetrievalPlan(BaseModel):
    """Search/retrieval execution plan generated from query interpretation."""
    mode: SearchMode
    filters: Dict[str, Any] = {}
    search_text: str = ""
    recommended_mode: SearchMode = SearchMode.HYBRID
    explanation: str = ""


class InvestigationQuery(BaseModel):
    """Canonical representation of an parsed investigation query."""
    query_id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    raw_query: str
    normalized_query: str
    intent: InvestigationIntentResult
    entities: List[ExtractedEntity] = []
    temporal_constraints: List[TemporalConstraint] = []
    artifact_types: List[str] = []
    filters: Dict[str, Any] = {}
    search_text: str = ""
    recommended_retrieval_mode: SearchMode = SearchMode.HYBRID
    parser_version: str = "1.0.0"


class InvestigationQueryRequest(BaseModel):
    """Investigator request schema for natural-language evidence inquiry."""
    query: str = Field(min_length=1, max_length=500, description="Natural language forensic search query")
    retrieval_mode: Optional[str] = Field("AUTO", description="'AUTO', 'EXACT', 'LEXICAL', 'SEMANTIC', or 'HYBRID'")
    page_size: int = Field(50, ge=1, le=100)
    cursor: Optional[str] = None
    include_facets: bool = False


class InvestigationQueryResponse(BaseModel):
    """Unified investigation query result returned to the investigator."""
    query_id: UUID
    case_id: UUID
    raw_query: str
    interpretation: InvestigationQueryInterpretation
    retrieval_plan: InvestigationRetrievalPlan
    results: List[SearchResultItem]
    facets: Optional[SearchFacets] = None
    pagination: SearchPagination
    duration_ms: int = 0
