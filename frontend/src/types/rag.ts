export interface EvidenceCitation {
  citation_tag: string;
  evidence_id: string;
  canonical_id: string;
  artifact_type: string;
  source_application?: string | null;
  timestamp?: string | null;
  sender?: string | null;
  receiver?: string | null;
  reason: string;
  content_snippet: string;
  is_verified: boolean;
}

export interface ConflictingRecord {
  field_name: string;
  records: Array<Record<string, any>>;
  conflict_description: string;
}

export interface RAGValidationReport {
  is_valid: boolean;
  total_citations_found: number;
  valid_citations: string[];
  invalid_citations: string[];
  cross_case_violations: string[];
  unsupported_claims: string[];
  validation_notes: string;
}

export interface ReproducibilityMetadata {
  query: string;
  case_id: string;
  llm_provider: string;
  llm_model: string;
  temperature: number;
  prompt_version: string;
  rag_version: string;
  retrieval_top_k: number;
  context_record_count: number;
  retrieved_evidence_ids: string[];
  timestamp: string;
}

export interface RAGQueryRequest {
  query: string;
  conversation_id?: string | null;
  max_context_records?: number | null;
  include_citations?: boolean;
  focus_artifact_types?: string[] | null;
  provider_override?: string | null;
}

export interface RAGQueryResponse {
  query_id: string;
  case_id: string;
  conversation_id: string;
  query: string;
  investigation_plan?: Record<string, any> | null;
  answer: string;
  evidence_references: EvidenceCitation[];
  conflicting_evidence: ConflictingRecord[];
  uncertainty?: string | null;
  limitations?: string | null;
  is_insufficient_evidence: boolean;
  validation_report: RAGValidationReport;
  reproducibility: ReproducibilityMetadata;
  audit_log_id?: string | null;
  latency_ms: number;
}

export interface RAGConversationMessage {
  message_id: string;
  case_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  evidence_references?: EvidenceCitation[] | null;
}

export interface RAGConversationHistory {
  conversation_id: string;
  case_id: string;
  messages: RAGConversationMessage[];
  created_at: string;
  updated_at: string;
}
