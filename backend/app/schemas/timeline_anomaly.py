from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import (
    AnomalyAlgorithm,
    AnomalyClassification,
    AnomalySeverity,
    AnomalyType,
    ArtifactType,
    BaselineType,
    JobStatus,
    TemporalWindowSize,
    TimestampPrecision,
    TimestampStatus,
)


class TimelineEvent(BaseModel):
    """Normalized unified timeline event representation."""
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    case_id: UUID
    evidence_id: UUID
    artifact_id: UUID
    raw_artifact_id: Optional[UUID] = None
    timestamp: Optional[str] = None
    timestamp_precision: TimestampPrecision = TimestampPrecision.UNKNOWN
    timestamp_status: TimestampStatus = TimestampStatus.UNKNOWN
    timezone: Optional[str] = None
    event_type: ArtifactType
    application: Optional[str] = None
    actor: Optional[str] = None
    target: Optional[str] = None
    device: Optional[str] = None
    content_summary: Optional[str] = None
    source_file: str
    source_path: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineFilterRequest(BaseModel):
    """Query and filter options for unified forensic timeline retrieval."""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    artifact_types: Optional[List[ArtifactType]] = None
    applications: Optional[List[str]] = None
    entity_value: Optional[str] = None
    device_id: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)


class TimelineResponse(BaseModel):
    """Case-scoped response payload containing ordered timeline events."""
    case_id: UUID
    total_events: int
    events: List[TimelineEvent]
    earliest_timestamp: Optional[str] = None
    latest_timestamp: Optional[str] = None
    event_distribution: Dict[str, int] = Field(default_factory=dict)


class TemporalWindowFeature(BaseModel):
    """Computed behavioral and temporal feature vector for a discrete time window."""
    window_id: str
    start_time: str
    end_time: str
    event_count: int = 0
    communication_count: int = 0
    incoming_count: int = 0
    outgoing_count: int = 0
    unique_contacts: int = 0
    app_activity_count: int = 0
    location_change_count: int = 0
    burst_frequency: float = 0.0  # events per minute
    inter_event_time_avg: float = 0.0  # average delta between events in seconds
    time_of_day_hour: int = 0  # 0 to 23
    day_of_week: int = 0  # 0=Monday, 6=Sunday
    supporting_event_ids: List[str] = Field(default_factory=list)
    supporting_artifact_ids: List[UUID] = Field(default_factory=list)
    entities_involved: List[str] = Field(default_factory=list)
    applications_involved: List[str] = Field(default_factory=list)


class BaselineComparisonMetric(BaseModel):
    """Factual statistical comparison between observed feature and calculated baseline."""
    feature_name: str
    observed_value: float
    baseline_median: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    deviation_factor: float


class AnomalyResult(BaseModel):
    """Structured statistical anomaly result with full contextual and evidence traceability."""
    anomaly_id: str
    case_id: UUID
    start_time: str
    end_time: str
    anomaly_type: AnomalyType
    anomaly_score: float = Field(ge=0.0, le=1.0)
    classification: AnomalyClassification = AnomalyClassification.ANOMALOUS
    severity: AnomalySeverity = AnomalySeverity.MODERATE_ANOMALY
    algorithm: AnomalyAlgorithm = AnomalyAlgorithm.ISOLATION_FOREST
    model_parameters: Dict[str, Any] = Field(default_factory=dict)
    baseline_metrics: List[BaselineComparisonMetric] = Field(default_factory=list)
    factual_explanation: str
    supporting_event_ids: List[str] = Field(default_factory=list)
    supporting_artifact_ids: List[UUID] = Field(default_factory=list)
    supporting_evidence_ids: List[UUID] = Field(default_factory=list)
    entities_involved: List[str] = Field(default_factory=list)
    applications_involved: List[str] = Field(default_factory=list)


class AnomalyDetectionRequest(BaseModel):
    """Parameters for initiating statistical anomaly analysis."""
    time_range: Optional[Dict[str, Optional[str]]] = None
    window_size: TemporalWindowSize = TemporalWindowSize.FIFTEEN_MINUTES
    baseline_type: BaselineType = BaselineType.FULL_CASE
    baseline_range: Optional[Dict[str, Optional[str]]] = None
    algorithm: AnomalyAlgorithm = AnomalyAlgorithm.ISOLATION_FOREST
    contamination: float = Field(default=0.05, ge=0.01, le=0.5)
    score_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    target_entity: Optional[str] = None
    target_device: Optional[str] = None
    target_application: Optional[str] = None


class AnomalyDetectionResponse(BaseModel):
    """Response payload containing detected statistical anomalies and metadata."""
    case_id: UUID
    analysis_id: str
    status: str
    window_size: str
    algorithm: str
    total_windows_analyzed: int
    anomalies_detected: int
    anomalies: List[AnomalyResult]
    baseline_summary: Dict[str, Any] = Field(default_factory=dict)
    model_metadata: Dict[str, Any] = Field(default_factory=dict)


class AnomalyJobStatusResponse(BaseModel):
    """Status payload for asynchronous anomaly detection processing jobs."""
    job_id: str
    case_id: UUID
    status: JobStatus
    progress: float
    total_windows: int = 0
    anomalies_found: int = 0
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[AnomalyDetectionResponse] = None
