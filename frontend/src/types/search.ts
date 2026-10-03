/**
 * Phase 9 — Search TypeScript types
 * Matches backend ForensicSearchResponse schema exactly.
 */

export interface SearchResultSource {
  evidence_id: string;
  raw_artifact_id: string;
  source_file: string;
  source_path: string;
  record_identifier: string;
}

export type SearchMode = 'EXACT' | 'LEXICAL' | 'SEMANTIC' | 'HYBRID';

export interface SearchResultItem {
  id: string;
  artifact_type: string;
  event_timestamp: string | null;
  timestamp_precision: string | null;
  application: string | null;
  device_id: string | null;
  content_preview: string | null;
  matched_entities: Array<{ type: string; value: unknown }>;
  data_quality_status: string | null;
  match_type: 'EXACT_MATCH' | 'TEXT_MATCH' | 'FILTER_MATCH' | 'SEMANTIC_MATCH' | 'HYBRID_MATCH';
  similarity_score?: number | null;
  retrieval_explanation?: string | null;
  source: SearchResultSource;
}

export interface SearchFacets {
  by_artifact_type: Record<string, number>;
  total_matched: number;
}

export interface SearchPagination {
  next_cursor: string | null;
  has_more: boolean;
  page_size: number;
}

export interface ForensicSearchResponse {
  results: SearchResultItem[];
  facets: SearchFacets | null;
  pagination: SearchPagination;
  search_mode?: SearchMode;
  duration_ms: number;
}

export interface SearchHistoryItem {
  id: string;
  query: string | null;
  filters_json: string | null;
  result_count: number | null;
  executed_at: string;
  duration_ms: number | null;
}

export interface SearchHistoryResponse {
  items: SearchHistoryItem[];
  total: number;
}

export interface EmbeddingStatsResponse {
  case_id: string;
  total_canonical_records: number;
  ready: number;
  stale: number;
  failed: number;
  not_embeddable: number;
  pending: number;
  coverage_percentage: number;
}
