/**
 * Phase 11 — Investigation NLP Query Types
 */

import type { SearchMode, SearchPagination, SearchResultItem, SearchFacets } from './search';

export type InvestigationIntent =
  | 'PERSON_LOOKUP'
  | 'EVENT_RETRIEVAL'
  | 'COMMUNICATION_ANALYSIS'
  | 'TEMPORAL_INVESTIGATION'
  | 'DEVICE_LOOKUP'
  | 'LOCATION_LOOKUP'
  | 'APPLICATION_ACTIVITY'
  | 'GENERAL_EVIDENCE_SEARCH'
  | 'UNKNOWN';

export type EntityType =
  | 'PERSON'
  | 'PHONE_NUMBER'
  | 'EMAIL'
  | 'ACCOUNT'
  | 'DEVICE'
  | 'APPLICATION'
  | 'LOCATION'
  | 'DATE'
  | 'TIME'
  | 'DATE_RANGE'
  | 'URL'
  | 'FILE'
  | 'ARTIFACT_TYPE'
  | 'ORGANIZATION';

export interface ExtractedEntity {
  type: EntityType;
  text: string;
  normalized_value: string;
  start_pos: number;
  end_pos: number;
  extraction_method: string;
  confidence: number;
}

export interface TemporalConstraint {
  start_time: string | null;
  end_time: string | null;
  raw_text: string;
  timezone: string | null;
  precision: string;
}

export interface InvestigationIntentResult {
  type: InvestigationIntent;
  confidence: number;
  explanation: string;
}

export interface InvestigationQueryInterpretation {
  intent: InvestigationIntentResult;
  entities: ExtractedEntity[];
  temporal_constraints: TemporalConstraint[];
  artifact_types: string[];
  filters: Record<string, any>;
  search_text: string;
  recommended_mode: SearchMode;
}

export interface InvestigationRetrievalPlan {
  mode: SearchMode;
  filters: Record<string, any>;
  search_text: string;
  recommended_mode: SearchMode;
  explanation: string;
}

export interface InvestigationQueryRequest {
  query: string;
  retrieval_mode?: string;
  page_size?: number;
  cursor?: string | null;
  include_facets?: boolean;
}

export interface InvestigationQueryResponse {
  query_id: string;
  case_id: string;
  raw_query: string;
  interpretation: InvestigationQueryInterpretation;
  retrieval_plan: InvestigationRetrievalPlan;
  results: SearchResultItem[];
  facets?: SearchFacets | null;
  pagination: SearchPagination;
  duration_ms: number;
}
