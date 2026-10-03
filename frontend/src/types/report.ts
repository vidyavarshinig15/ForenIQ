export type ReportType =
  | 'CASE_SUMMARY'
  | 'EVIDENCE_SUMMARY'
  | 'TIMELINE_REPORT'
  | 'COMMUNICATION_ANALYSIS_REPORT'
  | 'ANOMALY_ANALYSIS_REPORT'
  | 'INVESTIGATION_QUERY_REPORT'
  | 'COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT';

export type ReportStatus =
  | 'DRAFT'
  | 'GENERATED'
  | 'REVIEW_REQUIRED'
  | 'APPROVED'
  | 'EXPORTED'
  | 'ARCHIVED';

export type FindingType =
  | 'COMMUNICATION_ACTIVITY'
  | 'TEMPORAL_ANOMALY'
  | 'NETWORK_CENTRALITY'
  | 'KEYWORD_DISCOVERY'
  | 'EVIDENCE_INTEGRITY'
  | 'CROSS_SOURCE_CORRELATION';

export interface EvidenceCitation {
  citation_id: string;
  evidence_id: string;
  evidence_number: string;
  artifact_id?: string | null;
  record_identifier?: string | null;
  timestamp?: string | null;
  source_file?: string | null;
  summary: string;
}

export interface ForensicFinding {
  finding_id: string;
  case_id: string;
  title: string;
  description: string;
  finding_type: FindingType;
  source_type: string;
  citations: EvidenceCitation[];
  confidence_score?: number | null;
  model_source?: string | null;
  limitations: string[];
  created_at: string;
}

export interface ReportCaseInfo {
  case_id: string;
  case_number: string;
  title: string;
  description?: string | null;
  lead_investigator?: string | null;
  created_at: string;
  status: string;
}

export interface ReportEvidenceItem {
  evidence_id: string;
  evidence_number: string;
  original_filename: string;
  sha256_hash: string;
  integrity_status: string;
  artifact_count: number;
  ingestion_timestamp: string;
}

export interface ReportCustodyEvent {
  evidence_number: string;
  event_type: string;
  actor_name: string;
  timestamp: string;
  action: string;
  integrity_verified: boolean;
}

export interface ReportTimelineEntry {
  timestamp: string;
  event_type: string;
  application?: string | null;
  actor?: string | null;
  target?: string | null;
  content_summary?: string | null;
  citation_ref: string;
}

export interface ReportGraphSummary {
  snapshot_id?: string | null;
  total_nodes: number;
  total_edges: number;
  density: number;
  top_centrality_nodes: Record<string, any>[];
  detected_communities_count: number;
}

export interface ReportAnomalyEntry {
  anomaly_id: string;
  window_timestamp: string;
  anomaly_type: string;
  anomaly_score: number;
  baseline_expected_rate: number;
  observed_event_count: number;
  citation_refs: string[];
}

export interface ReportConflictingEvidence {
  conflict_id: string;
  description: string;
  record_a_id: string;
  record_b_id: string;
  source_a_ref: string;
  source_b_ref: string;
  investigator_notes?: string | null;
}

export interface ForensicReportDocument {
  report_id: string;
  case_id: string;
  title: string;
  report_type: ReportType;
  status: ReportStatus;
  version: number;
  generated_by_id: string;
  generated_by_name: string;
  generated_at: string;
  software_version: string;
  report_template_version: string;
  dataset_version?: string | null;
  report_sha256_hash?: string | null;
  case_info: ReportCaseInfo;
  investigation_scope: Record<string, any>;
  evidence_inventory: ReportEvidenceItem[];
  custody_chain: ReportCustodyEvent[];
  methodology_used: string[];
  findings: ForensicFinding[];
  timeline_entries: ReportTimelineEntry[];
  graph_analysis?: ReportGraphSummary | null;
  anomaly_findings: ReportAnomalyEntry[];
  citations: EvidenceCitation[];
  conflicting_evidence: ReportConflictingEvidence[];
  limitations: string[];
  analyst_notes?: string | null;
  reproducibility_manifest: Record<string, any>;
}

export interface ReportCreateRequest {
  case_id: string;
  report_type: ReportType;
  custom_title?: string | null;
  time_range?: string | null;
  target_entities?: string | null;
  include_evidence_inventory?: boolean;
  include_custody_chain?: boolean;
  include_timeline?: boolean;
  include_graph_analysis?: boolean;
  include_anomalies?: boolean;
  include_rag_findings?: boolean;
  analyst_notes?: string | null;
}

export interface ReportUpdateRequest {
  analyst_notes?: string | null;
  limitations?: string[] | null;
  status?: ReportStatus | null;
}

export interface ReportListSummary {
  report_id: string;
  case_id: string;
  title: string;
  report_type: ReportType;
  status: ReportStatus;
  version: number;
  generated_by_name: string;
  generated_at: string;
  findings_count: number;
  citations_count: number;
  report_sha256_hash?: string | null;
}

export interface ReportGenerationJobResponse {
  job_id: string;
  case_id: string;
  report_id?: string | null;
  report_type: ReportType;
  requested_by: string;
  status: string;
  progress: number;
  message?: string | null;
  created_at: string;
  completed_at?: string | null;
  error?: string | null;
}
