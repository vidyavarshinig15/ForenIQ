from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import (
    ExportFormat,
    FindingType,
    ReportStatus,
    ReportType,
)


class EvidenceCitation(BaseModel):
    """Structured verifiable forensic citation reference."""
    citation_id: str
    evidence_id: UUID
    evidence_number: str
    artifact_id: Optional[UUID] = None
    record_identifier: Optional[str] = None
    source_file: Optional[str] = None
    timestamp: Optional[str] = None
    summary: str


class ForensicFinding(BaseModel):
    """Structured verifiable forensic finding object."""
    finding_id: str
    title: str
    description: str
    finding_type: FindingType
    source_type: str
    citations: List[EvidenceCitation] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    model_source: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    created_at: str


class ReportCaseInfo(BaseModel):
    """Case context summary embedded in forensic report."""
    case_id: UUID
    case_number: str
    title: str
    description: Optional[str] = None
    lead_investigator: Optional[str] = None
    created_at: str
    status: str


class ReportEvidenceItem(BaseModel):
    """Evidence container manifest entry."""
    evidence_id: UUID
    evidence_number: str
    original_filename: str
    sha256_hash: str
    integrity_status: str
    artifact_count: int
    ingestion_timestamp: str


class ReportCustodyEvent(BaseModel):
    """Chain of custody audit item."""
    evidence_number: str
    event_type: str
    actor_name: str
    timestamp: str
    action: str
    integrity_verified: bool


class ReportTimelineEntry(BaseModel):
    """Timeline entry within report document."""
    timestamp: str
    event_type: str
    application: Optional[str] = None
    actor: Optional[str] = None
    target: Optional[str] = None
    content_summary: Optional[str] = None
    citation_ref: str


class ReportGraphSummary(BaseModel):
    """Communication graph analysis overview."""
    snapshot_id: Optional[str] = None
    total_nodes: int
    total_edges: int
    density: float
    top_centrality_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    detected_communities_count: int = 0
    algorithm_version: str = "1.0.0"


class ReportAnomalyEntry(BaseModel):
    """Statistical anomaly entry within report."""
    anomaly_id: str
    time_window: str
    anomaly_type: str
    severity: str
    anomaly_score: float
    factual_explanation: str
    observed_vs_baseline: Dict[str, Any] = Field(default_factory=dict)
    citation_refs: List[str] = Field(default_factory=list)


class ReportConflictingEvidence(BaseModel):
    """Documented evidence contradiction or discrepancy."""
    conflict_id: str
    description: str
    record_a_ref: str
    record_b_ref: str
    conflict_type: str


class ForensicReportDocument(BaseModel):
    """Complete, structured, evidence-grounded forensic report."""
    model_config = ConfigDict(from_attributes=True)

    report_id: str
    case_id: UUID
    title: str
    report_type: ReportType
    status: ReportStatus
    version: int = 1
    generated_by_id: UUID
    generated_by_name: str
    generated_at: str
    report_hash: Optional[str] = None

    case_info: ReportCaseInfo
    investigation_scope: Dict[str, Any] = Field(default_factory=dict)
    methodology: List[str] = Field(default_factory=list)
    evidence_inventory: List[ReportEvidenceItem] = Field(default_factory=list)
    chain_of_custody: List[ReportCustodyEvent] = Field(default_factory=list)
    findings: List[ForensicFinding] = Field(default_factory=list)
    timeline_section: Optional[List[ReportTimelineEntry]] = None
    graph_section: Optional[ReportGraphSummary] = None
    anomaly_section: Optional[List[ReportAnomalyEntry]] = None
    rag_narrative_summary: Optional[str] = None
    citations: List[EvidenceCitation] = Field(default_factory=list)
    conflicting_evidence: List[ReportConflictingEvidence] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    analyst_notes: Optional[str] = None
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)
    reproducibility: Dict[str, Any] = Field(default_factory=dict)


class ReportCreateRequest(BaseModel):
    """Parameters for constructing a new forensic investigation report."""
    title: Optional[str] = None
    report_type: ReportType = ReportType.COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT
    include_evidence_inventory: bool = True
    include_custody_chain: bool = True
    include_timeline: bool = True
    include_graph: bool = True
    include_anomalies: bool = True
    include_rag_findings: bool = True
    time_range: Optional[Dict[str, Optional[str]]] = None
    target_entities: Optional[List[str]] = None
    analyst_notes: Optional[str] = None


class ReportUpdateRequest(BaseModel):
    """Parameters for editing analyst notes or advancing review status."""
    title: Optional[str] = None
    status: Optional[ReportStatus] = None
    analyst_notes: Optional[str] = None


class ReportListSummary(BaseModel):
    """Summary item for listing generated reports."""
    report_id: str
    case_id: UUID
    title: str
    report_type: ReportType
    status: ReportStatus
    version: int
    generated_by_name: str
    generated_at: str
    report_hash: Optional[str] = None
    findings_count: int = 0
    citations_count: int = 0


class ReportJobStatusResponse(BaseModel):
    """Status payload for asynchronous report generation jobs."""
    job_id: str
    case_id: UUID
    report_id: Optional[str] = None
    status: str
    progress: float
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    report: Optional[ForensicReportDocument] = None
