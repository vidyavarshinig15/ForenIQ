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

export type AnomalyType =
  | 'COMMUNICATION_BURST'
  | 'COMMUNICATION_INACTIVITY'
  | 'UNUSUAL_APPLICATION_ACTIVITY'
  | 'UNUSUAL_EVENT_FREQUENCY'
  | 'UNUSUAL_TIME_OF_DAY'
  | 'UNUSUAL_CONTACT_DIVERSITY'
  | 'UNUSUAL_INTER_EVENT_TIMING'
  | 'UNUSUAL_LOCATION_TRANSITION';

export type AnomalyClassification = 'NORMAL' | 'ANOMALOUS';

export type AnomalySeverity = 'LOW_ANOMALY' | 'MODERATE_ANOMALY' | 'HIGH_ANOMALY';

export type AnomalyAlgorithm = 'ISOLATION_FOREST' | 'STATISTICAL_ZSCORE' | 'ROLLING_BASELINE';

export type TemporalWindowSize = '1m' | '5m' | '15m' | '30m' | '1h' | '6h' | '24h';

export interface TimelineEvent {
  event_id: string;
  case_id: string;
  evidence_id: string;
  artifact_id: string;
  raw_artifact_id?: string;
  timestamp?: string;
  timestamp_precision: string;
  timestamp_status: string;
  timezone?: string;
  event_type: ArtifactType;
  application?: string;
  actor?: string;
  target?: string;
  device?: string;
  content_summary?: string;
  source_file: string;
  source_path: string;
  metadata: Record<string, any>;
}

export interface TimelineFilterRequest {
  start_time?: string;
  end_time?: string;
  artifact_types?: ArtifactType[];
  applications?: string[];
  entity_value?: string;
  device_id?: string;
  limit?: number;
  offset?: number;
}

export interface TimelineResponse {
  case_id: string;
  total_events: number;
  events: TimelineEvent[];
  earliest_timestamp?: string;
  latest_timestamp?: string;
  event_distribution: Record<string, number>;
}

export interface BaselineComparisonMetric {
  feature_name: string;
  observed_value: number;
  baseline_median: number;
  baseline_mean: number;
  baseline_std: number;
  z_score: number;
  deviation_factor: number;
}

export interface AnomalyResult {
  anomaly_id: string;
  case_id: string;
  start_time: string;
  end_time: string;
  anomaly_type: AnomalyType;
  anomaly_score: number;
  classification: AnomalyClassification;
  severity: AnomalySeverity;
  algorithm: AnomalyAlgorithm;
  model_parameters: Record<string, any>;
  baseline_metrics: BaselineComparisonMetric[];
  factual_explanation: string;
  supporting_event_ids: string[];
  supporting_artifact_ids: string[];
  supporting_evidence_ids: string[];
  entities_involved: string[];
  applications_involved: string[];
}

export interface AnomalyDetectionRequest {
  time_range?: {
    start?: string;
    end?: string;
  };
  window_size?: TemporalWindowSize;
  baseline_type?: 'FULL_CASE' | 'PREVIOUS_PERIOD' | 'ROLLING_WINDOW' | 'HISTORICAL_ENTITY';
  baseline_range?: {
    start?: string;
    end?: string;
  };
  algorithm?: AnomalyAlgorithm;
  contamination?: number;
  score_threshold?: number;
  target_entity?: string;
  target_device?: string;
  target_application?: string;
}

export interface AnomalyDetectionResponse {
  case_id: string;
  analysis_id: string;
  status: string;
  window_size: string;
  algorithm: string;
  total_windows_analyzed: number;
  anomalies_detected: number;
  anomalies: AnomalyResult[];
  baseline_summary: Record<string, Record<string, number>>;
  model_metadata: Record<string, any>;
}

export interface AnomalyJobStatusResponse {
  job_id: string;
  case_id: string;
  status: string;
  progress: number;
  total_windows: number;
  anomalies_found: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  result?: AnomalyDetectionResponse;
}
