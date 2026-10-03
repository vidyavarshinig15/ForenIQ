export type EvidenceStatus =
  | 'UPLOADING'
  | 'UPLOADED'
  | 'VALIDATING'
  | 'VALID'
  | 'INVALID'
  | 'FAILED'
  | 'QUARANTINED'
  | 'PROCESSED';

export type IntegrityStatus =
  | 'UNKNOWN'
  | 'VALID'
  | 'MISMATCH'
  | 'MISSING'
  | 'ERROR';

export type CustodyEventType =
  | 'EVIDENCE_UPLOADED'
  | 'EVIDENCE_HASHED'
  | 'EVIDENCE_VALIDATED'
  | 'EVIDENCE_ACCESSED'
  | 'EVIDENCE_DOWNLOADED'
  | 'INTEGRITY_VERIFIED'
  | 'INTEGRITY_MISMATCH'
  | 'EVIDENCE_QUARANTINED'
  | 'EVIDENCE_ARCHIVED';

export interface Evidence {
  id: string;
  case_id: string;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  mime_type: string;
  detected_mime_type: string | null;
  file_extension: string;
  status: EvidenceStatus;
  sha256_hash: string | null;
  integrity_status: IntegrityStatus;
  last_integrity_check_at?: string | null;
  uploaded_by: string;
  uploader_name?: string | null;
  uploader_email?: string | null;
  uploaded_at: string;
  created_at: string;
  updated_at: string;
}

export interface EvidenceCustodyEvent {
  id: string;
  evidence_id: string;
  case_id: string;
  actor_user_id?: string | null;
  actor_name?: string | null;
  actor_email?: string | null;
  event_type: CustodyEventType;
  timestamp: string;
  sequence_number: number;
  previous_event_id?: string | null;
  previous_event_hash?: string | null;
  event_hash: string;
  metadata?: Record<string, any> | null;
}

export interface CustodyChainVerificationResult {
  evidence_id: string;
  case_id: string;
  status: 'VALID' | 'INVALID';
  events_checked: number;
  details?: string | null;
  verified_at: string;
}

export interface IntegrityVerificationResult {
  evidence_id: string;
  case_id: string;
  original_filename: string;
  stored_hash: string;
  calculated_hash?: string | null;
  integrity_status: IntegrityStatus;
  match: boolean;
  details?: string | null;
  verified_at: string;
}

export interface EvidenceUploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export type JobStatus =
  | 'QUEUED'
  | 'STARTING'
  | 'RUNNING'
  | 'PAUSED'
  | 'RETRYING'
  | 'COMPLETED'
  | 'PARTIAL'
  | 'FAILED'
  | 'CANCEL_REQUESTED'
  | 'CANCELLED';

export type JobPriority = 'HIGH' | 'NORMAL' | 'LOW';

export type ProcessingStage =
  | 'VALIDATING'
  | 'INSPECTING_ARCHIVE'
  | 'PARSING'
  | 'PERSISTING'
  | 'FINALIZING'
  | 'COMPLETED';

export type JobType = 'UFDR_PARSE' | 'NORMALIZATION' | 'INDEXING' | 'EMBEDDING' | 'ANALYSIS' | 'REPORT_GENERATION';
export type ArtifactType =
  | 'CALL'
  | 'MESSAGE'
  | 'CONTACT'
  | 'LOCATION'
  | 'BROWSER'
  | 'APPLICATION'
  | 'FILESYSTEM'
  | 'CALENDAR'
  | 'SOCIAL'
  | 'DEVICE_EVENT';

export type TimestampPrecision =
  | 'YEAR'
  | 'MONTH'
  | 'DAY'
  | 'HOUR'
  | 'MINUTE'
  | 'SECOND'
  | 'MILLISECOND'
  | 'UNKNOWN';

export type TimestampStatus = 'VALID' | 'INVALID' | 'UNKNOWN';

export type DataQualityStatus = 'VALID' | 'PARTIAL' | 'INVALID' | 'UNKNOWN';

export interface EntityReference {
  entity_type: string;
  entity_value: string;
  normalized_value?: string | null;
  role: string;
}

export interface ValidationWarning {
  field?: string | null;
  code: string;
  message: string;
  severity: 'WARNING' | 'ERROR';
}

export interface CanonicalEvidence {
  id: string;
  case_id: string;
  evidence_id: string;
  raw_artifact_id: string;
  processing_job_id?: string | null;
  artifact_type: ArtifactType;
  canonical_fingerprint: string;
  source_file: string;
  source_path: string;
  record_identifier: string;
  event_timestamp?: string | null;
  timestamp_precision: TimestampPrecision;
  timestamp_status: TimestampStatus;
  original_timestamp?: string | null;
  original_timezone?: string | null;
  device_id?: string | null;
  application?: string | null;
  original_application?: string | null;
  content?: string | null;
  entities: EntityReference[];
  metadata: Record<string, any>;
  data_quality_status: DataQualityStatus;
  validation_warnings: ValidationWarning[];
  parser_version: string;
  normalizer_version: string;
  created_at: string;
  updated_at: string;
}

export interface CanonicalEvidenceListResponse {
  items: CanonicalEvidence[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ProcessingJobSummary {
  files_total: number;
  files_processed: number;
  files_failed: number;
  artifacts_extracted: number;
  counts_by_type: Record<string, number>;
  warnings: string[];
  errors: string[];
}

export interface ProcessingJob {
  id: string;
  case_id: string;
  evidence_id: string;
  job_type: JobType;
  priority: JobPriority;
  status: JobStatus;
  current_stage?: string | null;
  current_file?: string | null;
  worker_id?: string | null;
  progress: number;
  files_total: number;
  files_processed: number;
  artifacts_total: number;
  records_processed: number;
  records_failed: number;
  bytes_processed: number;
  bytes_total: number;
  processing_rate?: number | null;
  estimated_remaining_seconds?: number | null;
  retry_count: number;
  max_retries: number;
  warnings_count: number;
  errors_count: number;
  summary_json?: ProcessingJobSummary | null;
  checkpoint_data?: Record<string, any> | null;
  error_message?: string | null;
  created_by: string;
  started_at?: string | null;
  completed_at?: string | null;
  last_heartbeat_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RawArtifact {
  id: string;
  case_id: string;
  evidence_id: string;
  processing_job_id: string;
  artifact_type: ArtifactType;
  source_file: string;
  source_path: string;
  record_identifier: string;
  raw_data: Record<string, any>;
  parsed_at: string;
  created_at: string;
}

export interface RawArtifactListResponse {
  items: RawArtifact[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

