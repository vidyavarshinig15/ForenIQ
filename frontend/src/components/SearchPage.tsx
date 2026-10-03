/**
 * Phase 9, 10 & 11 — Forensic Search & Investigation Query Page
 *
 * Case-scoped evidence search UI supporting:
 *  - Phase 11: Natural-Language Investigation Query & Intent Classification
 *  - Phase 10: Dense Semantic & Hybrid Vector Retrieval
 *  - Phase 9: Exact & Lexical Keyword Filtering
 *
 * Design & Transparency:
 *  - Shows detected investigative intent and model confidence (strictly model confidence, not criminality)
 *  - Displays extracted forensic entities (PERSON, PHONE, EMAIL, APPLICATION, LOCATION, DEVICE, ACCOUNT)
 *  - Formats temporal constraints with explicit precision (DAY, HOUR, MINUTE, MONTH)
 *  - Displays retrieval plan with recommended vs executed search modes
 *  - Retains 100% evidence provenance and chain of custody traceability
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type {
  ForensicSearchResponse,
  SearchResultItem,
  SearchHistoryItem,
  SearchHistoryResponse,
  SearchMode,
  EmbeddingStatsResponse,
} from '../types/search';
import type {
  InvestigationQueryInterpretation,
  InvestigationRetrievalPlan,
  InvestigationQueryResponse,
} from '../types/investigation';

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const SEARCH_MODES: { value: SearchMode; label: string; desc: string }[] = [
  { value: 'HYBRID', label: 'Hybrid', desc: 'Combined lexical + semantic ranked retrieval' },
  { value: 'SEMANTIC', label: 'Semantic', desc: 'Sentence-BERT vector similarity retrieval' },
  { value: 'LEXICAL', label: 'Lexical', desc: 'Keyword, partial text, and token search' },
  { value: 'EXACT', label: 'Exact', desc: 'Exact value and identifier matching' },
];

const NLP_MODE_OPTIONS = [
  { value: 'AUTO', label: 'Auto (Recommended by NLP Engine)' },
  { value: 'HYBRID', label: 'Hybrid (Dense Vector + Lexical)' },
  { value: 'SEMANTIC', label: 'Semantic Only (Dense Embedding)' },
  { value: 'LEXICAL', label: 'Lexical Only (Exact/Keyword DB)' },
  { value: 'EXACT', label: 'Exact Only (Identifier Match)' },
];

const SUGGESTED_QUERIES = [
  'Find WhatsApp messages sent by Rahul yesterday',
  'Find communication between 9876543210 and 9123456789',
  'What happened between 10 PM and midnight?',
  'Show events related to the suspect on September 12',
  'Show activity from device DEV_9901',
  'Show records associated with Mysuru',
  'Find documents containing encrypted ransomware keys',
  'Show call logs from last week',
];

const ARTIFACT_TYPES = [
  'ALL',
  'MESSAGE',
  'CALL',
  'CONTACT',
  'LOCATION',
  'BROWSER',
  'APPLICATION',
  'FILESYSTEM',
  'CALENDAR',
  'SOCIAL',
  'DEVICE_EVENT',
];

const QUALITY_OPTIONS = ['ALL', 'VALID', 'PARTIAL', 'INVALID', 'UNKNOWN'];

const ARTIFACT_TYPE_COLORS: Record<string, string> = {
  MESSAGE: '#6366f1',
  CALL: '#10b981',
  CONTACT: '#f59e0b',
  LOCATION: '#ef4444',
  BROWSER: '#3b82f6',
  APPLICATION: '#8b5cf6',
  FILESYSTEM: '#64748b',
  CALENDAR: '#ec4899',
  SOCIAL: '#f97316',
  DEVICE_EVENT: '#14b8a6',
};

const ENTITY_TYPE_COLORS: Record<string, string> = {
  PERSON: '#3b82f6',
  PHONE_NUMBER: '#10b981',
  EMAIL: '#8b5cf6',
  APPLICATION: '#ec4899',
  LOCATION: '#ef4444',
  DEVICE: '#06b6d4',
  ACCOUNT: '#f59e0b',
  ARTIFACT_TYPE: '#6366f1',
  DATE: '#14b8a6',
  TIME: '#14b8a6',
};

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

interface SearchPageProps {
  caseId: string;
  caseData?: Case | null;
}

export const SearchPage: React.FC<SearchPageProps> = ({ caseId, caseData }) => {
  // Main Tab State
  const [activeTab, setActiveTab] = useState<'NLP' | 'STRUCTURED'>('NLP');

  // Phase 11 NLP Investigation State
  const [nlpQuery, setNlpQuery] = useState('');
  const [nlpRetrievalMode, setNlpRetrievalMode] = useState('AUTO');
  const [interpretation, setInterpretation] = useState<InvestigationQueryInterpretation | null>(null);
  const [retrievalPlan, setRetrievalPlan] = useState<InvestigationRetrievalPlan | null>(null);

  // Structured / Classic Search inputs
  const [searchMode, setSearchMode] = useState<SearchMode>('HYBRID');
  const [query, setQuery] = useState('');
  const [artifactType, setArtifactType] = useState('ALL');
  const [application, setApplication] = useState('');
  const [deviceId, setDeviceId] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [sourceFile, setSourceFile] = useState('');
  const [dataQualityStatus, setDataQualityStatus] = useState('ALL');
  const [sort, setSort] = useState('timestamp_desc');

  // Results state
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [duration, setDuration] = useState<number | null>(null);

  // Embedding / Index status
  const [embeddingStats, setEmbeddingStats] = useState<EmbeddingStatsResponse | null>(null);
  const [showEmbeddingStats, setShowEmbeddingStats] = useState(false);
  const [isTriggeringEmbeddings, setIsTriggeringEmbeddings] = useState(false);
  const [embeddingActionMessage, setEmbeddingActionMessage] = useState<string | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // History
  const [history, setHistory] = useState<SearchHistoryResponse | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  // Selected Record Modal
  const [selectedItem, setSelectedItem] = useState<SearchResultItem | null>(null);

  const nlpInputRef = useRef<HTMLInputElement>(null);

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch Embedding Index Stats
  // ─────────────────────────────────────────────────────────────────────────

  const fetchEmbeddingStats = useCallback(async () => {
    try {
      const stats = await apiClient.getEmbeddingStats(caseId);
      setEmbeddingStats(stats);
    } catch {
      // Non-critical
    }
  }, [caseId]);

  useEffect(() => {
    fetchEmbeddingStats();
  }, [fetchEmbeddingStats]);

  const handleGenerateEmbeddings = async () => {
    try {
      setIsTriggeringEmbeddings(true);
      setEmbeddingActionMessage(null);
      const res = await apiClient.generateEmbeddings(caseId);
      setEmbeddingActionMessage(`Generation job queued: ${res.job_id}`);
      setTimeout(() => fetchEmbeddingStats(), 2000);
    } catch (err: any) {
      setEmbeddingActionMessage(`Failed to queue embeddings: ${err.message}`);
    } finally {
      setIsTriggeringEmbeddings(false);
    }
  };

  const handleRebuildEmbeddings = async () => {
    try {
      setIsTriggeringEmbeddings(true);
      setEmbeddingActionMessage(null);
      const res = await apiClient.rebuildEmbeddings(caseId);
      setEmbeddingActionMessage(`Rebuild job queued: ${res.job_id}`);
      setTimeout(() => fetchEmbeddingStats(), 2000);
    } catch (err: any) {
      setEmbeddingActionMessage(`Failed to rebuild index: ${err.message}`);
    } finally {
      setIsTriggeringEmbeddings(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Execute Phase 11 NLP Investigation Query
  // ─────────────────────────────────────────────────────────────────────────

  const handleNlpSearch = async (queryText?: string) => {
    const q = queryText !== undefined ? queryText : nlpQuery;
    if (!q.trim()) return;

    setError(null);
    setIsLoading(true);
    setResults([]);
    setInterpretation(null);
    setRetrievalPlan(null);

    try {
      const data: InvestigationQueryResponse = await apiClient.executeInvestigationQuery(caseId, {
        query: q.trim(),
        retrieval_mode: nlpRetrievalMode,
        page_size: 50,
        include_facets: true,
      });

      setResults(data.results);
      setInterpretation(data.interpretation);
      setRetrievalPlan(data.retrieval_plan);
      setDuration(data.duration_ms);
      setHasSearched(true);
    } catch (err: any) {
      setError(err.message || 'Unable to execute investigation query.');
    } finally {
      setIsLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Execute Classic Structured Search (Phase 9 & 10)
  // ─────────────────────────────────────────────────────────────────────────

  const buildStructuredParams = useCallback(() => {
    const params: Record<string, string> = {
      mode: searchMode,
      sort,
      page_size: '50',
    };
    if (query.trim()) params.q = query.trim();
    if (artifactType !== 'ALL') params.artifact_type = artifactType;
    if (application.trim()) params.application = application.trim();
    if (deviceId.trim()) params.device_id = deviceId.trim();
    if (startTime) params.start_time = new Date(startTime).toISOString();
    if (endTime) params.end_time = new Date(endTime).toISOString();
    if (sourceFile.trim()) params.source_file = sourceFile.trim();
    if (dataQualityStatus !== 'ALL') params.data_quality_status = dataQualityStatus;
    return params;
  }, [searchMode, query, artifactType, application, deviceId, startTime, endTime, sourceFile, dataQualityStatus, sort]);

  const executeStructuredSearch = useCallback(async () => {
    setError(null);
    setIsLoading(true);
    setResults([]);
    setInterpretation(null);
    setRetrievalPlan(null);

    try {
      const params = buildStructuredParams();
      const data: ForensicSearchResponse = await apiClient.searchEvidence(caseId, params);

      setResults(data.results);
      setDuration(data.duration_ms);
      setHasSearched(true);
    } catch (err: any) {
      setError(err.message || 'Unable to complete search. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [caseId, buildStructuredParams]);

  const clearAll = () => {
    setNlpQuery('');
    setQuery('');
    setArtifactType('ALL');
    setApplication('');
    setDeviceId('');
    setStartTime('');
    setEndTime('');
    setSourceFile('');
    setDataQualityStatus('ALL');
    setSort('timestamp_desc');
    setResults([]);
    setError(null);
    setHasSearched(false);
    setDuration(null);
    setInterpretation(null);
    setRetrievalPlan(null);
  };

  const fetchHistory = async () => {
    try {
      const data = await apiClient.getSearchHistory(caseId);
      setHistory(data);
      setShowHistory(true);
    } catch {
      // Non-critical
    }
  };

  const restoreSearch = (histItem: SearchHistoryItem) => {
    if (histItem.query) {
      setNlpQuery(histItem.query);
      setQuery(histItem.query);
    }
    if (histItem.filters_json) {
      try {
        const f = JSON.parse(histItem.filters_json);
        if (f.mode) setSearchMode(f.mode);
        if (f.artifact_type) setArtifactType(f.artifact_type);
        if (f.application) setApplication(f.application);
        if (f.device_id) setDeviceId(f.device_id);
        if (f.source_file) setSourceFile(f.source_file);
        if (f.data_quality_status) setDataQualityStatus(f.data_quality_status);
        if (f.sort) setSort(f.sort);
      } catch { /* ignore */ }
    }
    setShowHistory(false);
  };

  const formatTimestamp = (ts: string | null | undefined): string => {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'UTC', hour12: false,
      }) + ' UTC';
    } catch {
      return ts;
    }
  };

  const matchTypeBadge = (mt: string) => {
    if (mt === 'EXACT_MATCH') return { label: 'EXACT', color: '#10b981' };
    if (mt === 'TEXT_MATCH') return { label: 'LEXICAL', color: '#6366f1' };
    if (mt === 'SEMANTIC_MATCH') return { label: 'SEMANTIC', color: '#8b5cf6' };
    if (mt === 'HYBRID_MATCH') return { label: 'HYBRID', color: '#06b6d4' };
    return { label: 'FILTER', color: '#64748b' };
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div style={styles.page}>

      {/* Header */}
      <div style={styles.pageHeader}>
        <div>
          <div style={styles.caseBreadcrumb}>
            <span style={styles.caseLabel}>CASE</span>
            <span style={styles.caseName}>{caseData?.case_number ?? caseId.slice(0, 8).toUpperCase()}</span>
            <span style={styles.caseTitle}>{caseData?.title ?? 'Forensic Case'}</span>
          </div>
          <h1 style={styles.pageTitle}>Investigation Search & NLP Query Engine</h1>
          <p style={styles.pageSubtitle}>
            Natural language inquiry, forensic intent classification, entity extraction, and multi-modal retrieval.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            id="embedding-stats-btn"
            style={styles.historyBtn}
            onClick={() => {
              fetchEmbeddingStats();
              setShowEmbeddingStats(!showEmbeddingStats);
            }}
          >
            <span style={{ marginRight: '6px' }}>🧠</span> Vector Index
          </button>
          <button
            id="search-history-btn"
            style={styles.historyBtn}
            onClick={fetchHistory}
          >
            <span style={{ marginRight: '6px' }}>🕐</span> Search History
          </button>
        </div>
      </div>

      {/* Embedding stats panel */}
      {showEmbeddingStats && (
        <div style={styles.embeddingPanel}>
          <div style={styles.embeddingHeader}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>🧠</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>Vector Index & Dense Embedding Engine</span>
            </div>
            <button style={styles.closeBtn} onClick={() => setShowEmbeddingStats(false)}>✕</button>
          </div>
          <div style={styles.embeddingGrid}>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Total Canonical Records</span>
              <span style={styles.statVal}>{embeddingStats?.total_canonical_records ?? 0}</span>
            </div>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Ready Vectors</span>
              <span style={{ ...styles.statVal, color: '#10b981' }}>{embeddingStats?.ready ?? 0}</span>
            </div>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Pending</span>
              <span style={{ ...styles.statVal, color: '#f59e0b' }}>{embeddingStats?.pending ?? 0}</span>
            </div>
            <div style={styles.statBox}>
              <span style={styles.statLabel}>Vector Coverage</span>
              <span style={styles.statVal}>{(embeddingStats?.coverage_percentage ?? 0).toFixed(1)}%</span>
            </div>
          </div>
          {embeddingActionMessage && (
            <div style={styles.actionMessage}>{embeddingActionMessage}</div>
          )}
          <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
            <button
              id="generate-embeddings-btn"
              style={styles.actionBtnPrimary}
              onClick={handleGenerateEmbeddings}
              disabled={isTriggeringEmbeddings}
            >
              {isTriggeringEmbeddings ? 'Queueing…' : 'Generate Missing Embeddings'}
            </button>
            <button
              id="rebuild-embeddings-btn"
              style={styles.actionBtnSecondary}
              onClick={handleRebuildEmbeddings}
              disabled={isTriggeringEmbeddings}
            >
              Rebuild Vector Index
            </button>
          </div>
        </div>
      )}

      {/* Tab Switcher: NLP Query vs Classic Filter Search */}
      <div style={styles.tabSwitcher}>
        <button
          id="tab-nlp-investigation"
          style={{
            ...styles.tabBtn,
            ...(activeTab === 'NLP' ? styles.tabBtnActive : {}),
          }}
          onClick={() => setActiveTab('NLP')}
        >
          <span style={{ marginRight: '8px' }}>🤖</span> Natural Language Query (NLP Intent)
        </button>
        <button
          id="tab-structured-search"
          style={{
            ...styles.tabBtn,
            ...(activeTab === 'STRUCTURED' ? styles.tabBtnActive : {}),
          }}
          onClick={() => setActiveTab('STRUCTURED')}
        >
          <span style={{ marginRight: '8px' }}>🔍</span> Structured & Keyword Filters
        </button>
      </div>

      {/* TAB 1: NATURAL LANGUAGE INVESTIGATION QUERY (PHASE 11) */}
      {activeTab === 'NLP' && (
        <div style={styles.nlpContainer}>
          <div style={styles.nlpCard}>
            <div style={styles.nlpInputRow}>
              <div style={styles.nlpInputWrapper}>
                <span style={styles.nlpIcon}>⚡</span>
                <input
                  ref={nlpInputRef}
                  id="nlp-query-input"
                  type="text"
                  style={styles.nlpInput}
                  placeholder="Ask a natural language forensic question (e.g. 'Show WhatsApp messages sent by Rahul yesterday')"
                  value={nlpQuery}
                  onChange={(e) => setNlpQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleNlpSearch()}
                />
                {nlpQuery && (
                  <button style={styles.clearBtn} onClick={() => setNlpQuery('')}>✕</button>
                )}
              </div>

              <div style={styles.nlpModeSelectWrapper}>
                <label style={styles.nlpModeLabel}>Search Mode</label>
                <select
                  id="nlp-mode-select"
                  style={styles.nlpSelect}
                  value={nlpRetrievalMode}
                  onChange={(e) => setNlpRetrievalMode(e.target.value)}
                >
                  {NLP_MODE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                id="nlp-search-submit-btn"
                style={styles.nlpSearchBtn}
                onClick={() => handleNlpSearch()}
                disabled={isLoading || !nlpQuery.trim()}
              >
                {isLoading ? 'Interpreting…' : 'Investigate'}
              </button>
            </div>

            {/* Suggestions */}
            <div style={styles.suggestionsRow}>
              <span style={styles.suggestionsLabel}>Suggested Queries:</span>
              <div style={styles.suggestionChips}>
                {SUGGESTED_QUERIES.map((sq, idx) => (
                  <button
                    key={idx}
                    style={styles.suggestionChip}
                    onClick={() => {
                      setNlpQuery(sq);
                      handleNlpSearch(sq);
                    }}
                  >
                    {sq}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* QUERY TRANSPARENCY / INTERPRETATION CARD */}
          {interpretation && (
            <div id="nlp-interpretation-card" style={styles.interpretationCard}>
              <div style={styles.interpretationHeader}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '18px' }}>🧭</span>
                  <span style={styles.interpretationTitle}>NLP Query Interpretation & Forensic Transparency</span>
                </div>
                <div style={styles.transparencyBadge}>
                  Model Confidence: {(interpretation.intent.confidence * 100).toFixed(0)}%
                </div>
              </div>

              <div style={styles.interpretationGrid}>
                {/* 1. Detected Intent */}
                <div style={styles.interpSection}>
                  <div style={styles.interpSectionTitle}>Detected Intent</div>
                  <div style={styles.intentBadgeWrapper}>
                    <span style={styles.intentBadge}>
                      {interpretation.intent.type}
                    </span>
                    <span style={styles.intentExplanation}>
                      {interpretation.intent.explanation}
                    </span>
                  </div>
                </div>

                {/* 2. Extracted Entities */}
                <div style={styles.interpSection}>
                  <div style={styles.interpSectionTitle}>Extracted Forensic Entities ({interpretation.entities.length})</div>
                  {interpretation.entities.length === 0 ? (
                    <span style={styles.emptyNotice}>No specific named entities or identifiers detected.</span>
                  ) : (
                    <div style={styles.entityTagsWrapper}>
                      {interpretation.entities.map((ent, i) => (
                        <div key={i} style={{ ...styles.entityTag, borderColor: ENTITY_TYPE_COLORS[ent.type] || '#6366f1' }}>
                          <span style={{ ...styles.entityTagType, color: ENTITY_TYPE_COLORS[ent.type] || '#6366f1' }}>
                            {ent.type}
                          </span>
                          <span style={styles.entityTagVal}>{ent.text}</span>
                          {ent.normalized_value !== ent.text && (
                            <span style={styles.entityTagNorm}>→ {ent.normalized_value}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Temporal Constraints */}
                <div style={styles.interpSection}>
                  <div style={styles.interpSectionTitle}>Temporal Constraints</div>
                  {interpretation.temporal_constraints.length === 0 ? (
                    <span style={styles.emptyNotice}>No explicit time constraints specified.</span>
                  ) : (
                    <div style={styles.temporalList}>
                      {interpretation.temporal_constraints.map((tc, i) => (
                        <div key={i} style={styles.temporalBox}>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, color: '#f8fafc' }}>"{tc.raw_text}"</span>
                            <span style={styles.precisionBadge}>Precision: {tc.precision}</span>
                          </div>
                          <div style={styles.temporalBounds}>
                            <span>From: {tc.start_time ? formatTimestamp(tc.start_time) : 'Beginning'}</span>
                            <span>To: {tc.end_time ? formatTimestamp(tc.end_time) : 'Present'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 4. Generated Retrieval Plan */}
                <div style={styles.interpSection}>
                  <div style={styles.interpSectionTitle}>Retrieval Execution Plan</div>
                  <div style={styles.planDetails}>
                    <div style={styles.planRow}>
                      <span style={styles.planKey}>Recommended Mode:</span>
                      <span style={styles.planVal}>{retrievalPlan?.recommended_mode ?? interpretation.recommended_mode}</span>
                    </div>
                    <div style={styles.planRow}>
                      <span style={styles.planKey}>Executed Mode:</span>
                      <span style={{ ...styles.planVal, color: '#38bdf8', fontWeight: 600 }}>
                        {retrievalPlan?.mode ?? 'HYBRID'}
                      </span>
                    </div>
                    <div style={styles.planRow}>
                      <span style={styles.planKey}>Synthesized Filters:</span>
                      <span style={styles.planVal}>
                        {Object.keys(interpretation.filters).length === 0
                          ? 'None'
                          : JSON.stringify(interpretation.filters)}
                      </span>
                    </div>
                    <div style={styles.planRow}>
                      <span style={styles.planKey}>Residual Search Terms:</span>
                      <span style={styles.planVal}>"{interpretation.search_text || '—'}"</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Safety Disclaimer Banner */}
              <div style={styles.safetyBanner}>
                <span style={{ marginRight: '6px' }}>⚖️</span>
                <span>
                  <strong>Forensic Neutrality Notice:</strong> Query interpretation and confidence scores represent parser and retrieval matching certainty. They strictly do NOT represent guilt, criminality, or investigative conclusions.
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: STRUCTURED & KEYWORD SEARCH (PHASE 9 & 10) */}
      {activeTab === 'STRUCTURED' && (
        <div>
          {/* Search Mode Selector */}
          <div style={styles.modeTabsRow}>
            <span style={styles.modeLabel}>RETRIEVAL ENGINE:</span>
            {SEARCH_MODES.map((mode) => (
              <button
                key={mode.value}
                id={`search-mode-${mode.value.toLowerCase()}`}
                style={{
                  ...styles.modeTab,
                  ...(searchMode === mode.value ? styles.modeTabActive : {}),
                }}
                onClick={() => setSearchMode(mode.value)}
                title={mode.desc}
              >
                {mode.label}
              </button>
            ))}
          </div>

          <div style={styles.searchBarRow}>
            <input
              id="search-input"
              type="text"
              style={styles.searchInput}
              placeholder="Search evidence content, identifiers, entities, applications..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && executeStructuredSearch()}
            />
            <button
              id="search-btn"
              style={styles.searchBtn}
              onClick={() => executeStructuredSearch()}
              disabled={isLoading}
            >
              {isLoading ? 'Searching…' : 'Search'}
            </button>
            <button style={styles.clearBtnSecondary} onClick={clearAll}>
              Clear
            </button>
          </div>

          {/* Structured filter options */}
          <div style={styles.filtersCard}>
            <div style={styles.filtersGrid}>
              <div style={styles.filterGroup}>
                <label style={styles.filterLabel}>Artifact Type</label>
                <select
                  style={styles.filterSelect}
                  value={artifactType}
                  onChange={(e) => setArtifactType(e.target.value)}
                >
                  {ARTIFACT_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div style={styles.filterGroup}>
                <label style={styles.filterLabel}>Application</label>
                <input
                  type="text"
                  style={styles.filterInput}
                  placeholder="e.g. WhatsApp, Chrome"
                  value={application}
                  onChange={(e) => setApplication(e.target.value)}
                />
              </div>
              <div style={styles.filterGroup}>
                <label style={styles.filterLabel}>Device ID / IMEI</label>
                <input
                  type="text"
                  style={styles.filterInput}
                  placeholder="e.g. DEV_001"
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                />
              </div>
              <div style={styles.filterGroup}>
                <label style={styles.filterLabel}>Data Quality</label>
                <select
                  style={styles.filterSelect}
                  value={dataQualityStatus}
                  onChange={(e) => setDataQualityStatus(e.target.value)}
                >
                  {QUALITY_OPTIONS.map((q) => (
                    <option key={q} value={q}>{q}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* History drawer */}
      {showHistory && history && (
        <div style={styles.historyPanel}>
          <div style={styles.historyHeader}>
            <span style={styles.historyTitle}>Recent Searches ({history.total})</span>
            <button style={styles.closeBtn} onClick={() => setShowHistory(false)}>✕</button>
          </div>
          {history.items.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '13px' }}>No searches recorded yet.</p>
          ) : (
            history.items.map((item) => (
              <div key={item.id} style={styles.historyItem} onClick={() => restoreSearch(item)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={styles.historyQuery}>"{item.query || '(empty search)'}"</span>
                  <span style={styles.historyTime}>{formatTimestamp(item.executed_at)}</span>
                </div>
                <div style={styles.historyMeta}>
                  {item.result_count !== null && <span>{item.result_count} results</span>}
                  {item.duration_ms !== null && <span>{item.duration_ms} ms</span>}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div id="search-error-banner" style={styles.errorBanner}>
          <span style={{ fontSize: '18px', marginRight: '8px' }}>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Search results stats bar */}
      {hasSearched && !isLoading && (
        <div style={styles.resultsMetaBar}>
          <div style={styles.resultsCount}>
            <span>Found <strong>{results.length}</strong> matching canonical records</span>
            {duration !== null && <span style={styles.durationBadge}>{duration} ms</span>}
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div style={styles.loadingBox}>
          <div style={styles.spinner}></div>
          <p style={{ marginTop: '12px', color: '#94a3b8' }}>Processing query and executing forensic retrieval…</p>
        </div>
      )}

      {/* RESULTS LIST */}
      {!isLoading && results.length > 0 && (
        <div id="search-results-list" style={styles.resultsList}>
          {results.map((rec) => {
            const badge = matchTypeBadge(rec.match_type);
            const artColor = ARTIFACT_TYPE_COLORS[rec.artifact_type] || '#64748b';

            return (
              <div
                key={rec.id}
                id={`result-card-${rec.id}`}
                style={styles.resultCard}
                onClick={() => setSelectedItem(rec)}
              >
                <div style={styles.cardHeader}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ ...styles.artifactBadge, backgroundColor: artColor }}>
                      {rec.artifact_type}
                    </span>
                    <span style={{ ...styles.matchBadge, borderColor: badge.color, color: badge.color }}>
                      {badge.label}
                    </span>
                    {rec.application && (
                      <span style={styles.appBadge}>{rec.application}</span>
                    )}
                  </div>
                  <span style={styles.cardTimestamp}>
                    {formatTimestamp(rec.event_timestamp)}
                  </span>
                </div>

                <div style={styles.cardBody}>
                  <p style={styles.contentPreview}>
                    {rec.content_preview || <em style={{ color: '#64748b' }}>(No text content)</em>}
                  </p>
                </div>

                <div style={styles.cardFooter}>
                  <div style={styles.traceabilityChain}>
                    <span style={styles.traceItem}><strong>Source:</strong> {rec.source?.source_file || '—'}</span>
                    <span style={styles.traceItem}><strong>Device:</strong> {rec.device_id || '—'}</span>
                    <span style={styles.traceItem}><strong>ID:</strong> {rec.source?.record_identifier || rec.id.slice(0, 8)}</span>
                  </div>
                  {rec.similarity_score !== undefined && rec.similarity_score !== null && (
                    <span style={styles.scoreBadge}>
                      Score: {(rec.similarity_score * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && hasSearched && results.length === 0 && (
        <div id="search-empty-state" style={styles.emptyState}>
          <span style={{ fontSize: '36px', marginBottom: '12px' }}>📂</span>
          <h3 style={{ margin: '0 0 6px 0', color: '#f8fafc' }}>No Evidence Found</h3>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '14px', maxWidth: '450px' }}>
            No forensic records matched your query constraints. Try widening your temporal scope, using general terms, or switching retrieval modes.
          </p>
        </div>
      )}

      {/* Detail Modal */}
      {selectedItem && (
        <div style={styles.modalBackdrop} onClick={() => setSelectedItem(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div>
                <span style={{ ...styles.artifactBadge, backgroundColor: ARTIFACT_TYPE_COLORS[selectedItem.artifact_type] || '#64748b' }}>
                  {selectedItem.artifact_type}
                </span>
                <h3 style={{ margin: '8px 0 0 0', color: '#f8fafc' }}>Forensic Record Details</h3>
              </div>
              <button style={styles.closeBtn} onClick={() => setSelectedItem(null)}>✕</button>
            </div>
            <div style={styles.modalBody}>
              <div style={styles.modalMetaRow}>
                <div><strong>Canonical ID:</strong> {selectedItem.id}</div>
                <div><strong>Source File:</strong> {selectedItem.source?.source_file || '—'}</div>
                <div><strong>Application:</strong> {selectedItem.application || '—'}</div>
                <div><strong>Device ID:</strong> {selectedItem.device_id || '—'}</div>
                <div><strong>Timestamp:</strong> {formatTimestamp(selectedItem.event_timestamp)}</div>
              </div>
              <div style={{ marginTop: '16px' }}>
                <strong>Content Preview:</strong>
                <pre style={styles.rawJsonPre}>{selectedItem.content_preview || '(Empty)'}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: '28px 32px',
    backgroundColor: '#090d16',
    minHeight: '100vh',
    color: '#e2e8f0',
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  },
  pageHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
    borderBottom: '1px solid #1e293b',
    paddingBottom: '18px',
  },
  caseBreadcrumb: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '6px',
    fontSize: '12px',
  },
  caseLabel: {
    padding: '2px 6px',
    borderRadius: '4px',
    backgroundColor: '#3b82f6',
    color: '#ffffff',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
  caseName: {
    color: '#94a3b8',
    fontWeight: 600,
  },
  caseTitle: {
    color: '#64748b',
  },
  pageTitle: {
    fontSize: '24px',
    fontWeight: 700,
    color: '#f8fafc',
    margin: '0 0 6px 0',
  },
  pageSubtitle: {
    fontSize: '14px',
    color: '#94a3b8',
    margin: 0,
  },
  historyBtn: {
    padding: '8px 14px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '6px',
    color: '#f8fafc',
    fontSize: '13px',
    fontWeight: 500,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
  },
  tabSwitcher: {
    display: 'flex',
    gap: '10px',
    marginBottom: '20px',
  },
  tabBtn: {
    padding: '10px 18px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#94a3b8',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s',
  },
  tabBtnActive: {
    backgroundColor: '#3b82f6',
    borderColor: '#3b82f6',
    color: '#ffffff',
  },
  nlpContainer: {
    marginBottom: '24px',
  },
  nlpCard: {
    backgroundColor: '#111827',
    border: '1px solid #1f2937',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  },
  nlpInputRow: {
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-end',
  },
  nlpInputWrapper: {
    flex: 1,
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  nlpIcon: {
    position: 'absolute',
    left: '14px',
    fontSize: '16px',
    color: '#38bdf8',
  },
  nlpInput: {
    width: '100%',
    padding: '14px 40px 14px 40px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#f8fafc',
    fontSize: '15px',
    outline: 'none',
  },
  nlpModeSelectWrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  nlpModeLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#94a3b8',
  },
  nlpSelect: {
    padding: '13px 14px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#f8fafc',
    fontSize: '14px',
    outline: 'none',
    cursor: 'pointer',
  },
  nlpSearchBtn: {
    padding: '14px 24px',
    backgroundColor: '#3b82f6',
    border: 'none',
    borderRadius: '8px',
    color: '#ffffff',
    fontSize: '15px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background-color 0.2s',
  },
  suggestionsRow: {
    marginTop: '14px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  suggestionsLabel: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#64748b',
  },
  suggestionChips: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  suggestionChip: {
    padding: '4px 10px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '20px',
    color: '#94a3b8',
    fontSize: '12px',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  interpretationCard: {
    marginTop: '16px',
    backgroundColor: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    padding: '20px',
  },
  interpretationHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #1e293b',
    paddingBottom: '12px',
    marginBottom: '16px',
  },
  interpretationTitle: {
    fontWeight: 700,
    color: '#f8fafc',
    fontSize: '16px',
  },
  transparencyBadge: {
    padding: '4px 10px',
    backgroundColor: '#1e293b',
    borderRadius: '6px',
    fontSize: '12px',
    color: '#38bdf8',
    fontWeight: 600,
  },
  interpretationGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: '16px',
    marginBottom: '16px',
  },
  interpSection: {
    backgroundColor: '#111827',
    border: '1px solid #1f2937',
    borderRadius: '8px',
    padding: '14px',
  },
  interpSectionTitle: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '10px',
  },
  intentBadgeWrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  intentBadge: {
    display: 'inline-block',
    padding: '4px 10px',
    backgroundColor: '#6366f1',
    color: '#ffffff',
    fontWeight: 700,
    borderRadius: '6px',
    fontSize: '13px',
    alignSelf: 'flex-start',
  },
  intentExplanation: {
    fontSize: '13px',
    color: '#cbd5e1',
    lineHeight: 1.4,
  },
  entityTagsWrapper: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  entityTag: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 8px',
    backgroundColor: '#1e293b',
    border: '1px solid',
    borderRadius: '6px',
    fontSize: '12px',
  },
  entityTagType: {
    fontWeight: 700,
    fontSize: '11px',
    textTransform: 'uppercase',
  },
  entityTagVal: {
    color: '#f8fafc',
    fontWeight: 600,
  },
  entityTagNorm: {
    color: '#94a3b8',
    fontSize: '11px',
  },
  temporalList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  temporalBox: {
    backgroundColor: '#1e293b',
    borderRadius: '6px',
    padding: '8px 10px',
  },
  precisionBadge: {
    fontSize: '11px',
    padding: '2px 6px',
    backgroundColor: '#0f172a',
    borderRadius: '4px',
    color: '#38bdf8',
  },
  temporalBounds: {
    marginTop: '4px',
    display: 'flex',
    flexDirection: 'column',
    fontSize: '11px',
    color: '#94a3b8',
  },
  planDetails: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    fontSize: '13px',
  },
  planRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '8px',
  },
  planKey: {
    color: '#94a3b8',
  },
  planVal: {
    color: '#f8fafc',
    textAlign: 'right',
  },
  emptyNotice: {
    fontSize: '13px',
    color: '#64748b',
    fontStyle: 'italic',
  },
  safetyBanner: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    borderLeft: '4px solid #f59e0b',
    padding: '10px 14px',
    borderRadius: '4px',
    fontSize: '12px',
    color: '#cbd5e1',
    lineHeight: 1.4,
  },
  modeTabsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
  },
  modeLabel: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#64748b',
    marginRight: '6px',
  },
  modeTab: {
    padding: '6px 14px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '6px',
    color: '#94a3b8',
    fontSize: '13px',
    cursor: 'pointer',
  },
  modeTabActive: {
    backgroundColor: '#3b82f6',
    borderColor: '#3b82f6',
    color: '#ffffff',
    fontWeight: 600,
  },
  searchBarRow: {
    display: 'flex',
    gap: '10px',
    marginBottom: '16px',
  },
  searchInput: {
    flex: 1,
    padding: '12px 16px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#f8fafc',
    fontSize: '14px',
  },
  searchBtn: {
    padding: '12px 20px',
    backgroundColor: '#3b82f6',
    border: 'none',
    borderRadius: '8px',
    color: '#ffffff',
    fontWeight: 600,
    cursor: 'pointer',
  },
  clearBtnSecondary: {
    padding: '12px 16px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#94a3b8',
    cursor: 'pointer',
  },
  filtersCard: {
    backgroundColor: '#111827',
    border: '1px solid #1f2937',
    borderRadius: '8px',
    padding: '14px',
    marginBottom: '20px',
  },
  filtersGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '12px',
  },
  filterGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  filterLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    fontWeight: 600,
  },
  filterSelect: {
    padding: '8px 10px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '6px',
    color: '#f8fafc',
    fontSize: '13px',
  },
  filterInput: {
    padding: '8px 10px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '6px',
    color: '#f8fafc',
    fontSize: '13px',
  },
  embeddingPanel: {
    backgroundColor: '#111827',
    border: '1px solid #3b82f6',
    borderRadius: '10px',
    padding: '16px',
    marginBottom: '20px',
  },
  embeddingHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  embeddingGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
  },
  statBox: {
    backgroundColor: '#1e293b',
    padding: '10px 14px',
    borderRadius: '6px',
    display: 'flex',
    flexDirection: 'column',
  },
  statLabel: {
    fontSize: '11px',
    color: '#94a3b8',
    marginBottom: '4px',
  },
  statVal: {
    fontSize: '18px',
    fontWeight: 700,
    color: '#f8fafc',
  },
  actionBtnPrimary: {
    padding: '8px 14px',
    backgroundColor: '#3b82f6',
    color: '#ffffff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  actionBtnSecondary: {
    padding: '8px 14px',
    backgroundColor: '#1e293b',
    color: '#f8fafc',
    border: '1px solid #334155',
    borderRadius: '6px',
    fontSize: '13px',
    cursor: 'pointer',
  },
  actionMessage: {
    marginTop: '10px',
    padding: '6px 12px',
    backgroundColor: '#1e293b',
    borderRadius: '4px',
    fontSize: '12px',
    color: '#38bdf8',
  },
  resultsMetaBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '14px',
  },
  resultsCount: {
    fontSize: '14px',
    color: '#cbd5e1',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  durationBadge: {
    padding: '2px 8px',
    backgroundColor: '#1e293b',
    borderRadius: '4px',
    fontSize: '12px',
    color: '#94a3b8',
  },
  resultsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  resultCard: {
    backgroundColor: '#111827',
    border: '1px solid #1f2937',
    borderRadius: '10px',
    padding: '16px',
    cursor: 'pointer',
    transition: 'border-color 0.15s, transform 0.15s',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  artifactBadge: {
    padding: '3px 8px',
    borderRadius: '4px',
    color: '#ffffff',
    fontSize: '11px',
    fontWeight: 700,
  },
  matchBadge: {
    padding: '2px 6px',
    borderRadius: '4px',
    border: '1px solid',
    fontSize: '11px',
    fontWeight: 700,
  },
  appBadge: {
    padding: '2px 6px',
    borderRadius: '4px',
    backgroundColor: '#1e293b',
    color: '#cbd5e1',
    fontSize: '11px',
  },
  cardTimestamp: {
    fontSize: '12px',
    color: '#94a3b8',
  },
  cardBody: {
    marginBottom: '10px',
  },
  contentPreview: {
    fontSize: '14px',
    color: '#f8fafc',
    margin: 0,
    lineHeight: 1.5,
  },
  cardFooter: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTop: '1px solid #1e293b',
    paddingTop: '8px',
  },
  traceabilityChain: {
    display: 'flex',
    gap: '14px',
    fontSize: '12px',
    color: '#64748b',
  },
  traceItem: {
    color: '#94a3b8',
  },
  scoreBadge: {
    fontSize: '11px',
    fontWeight: 600,
    color: '#10b981',
    backgroundColor: '#064e3b',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  emptyState: {
    textAlign: 'center',
    padding: '48px 24px',
    backgroundColor: '#111827',
    border: '1px dashed #334155',
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  loadingBox: {
    textAlign: 'center',
    padding: '48px 24px',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #1e293b',
    borderTopColor: '#3b82f6',
    borderRadius: '50%',
    margin: '0 auto',
    animation: 'spin 1s linear infinite',
  },
  historyPanel: {
    backgroundColor: '#111827',
    border: '1px solid #1f2937',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '20px',
    maxHeight: '300px',
    overflowY: 'auto',
  },
  historyHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  historyTitle: {
    fontWeight: 700,
    color: '#f8fafc',
  },
  historyItem: {
    padding: '8px 10px',
    backgroundColor: '#1e293b',
    borderRadius: '6px',
    marginBottom: '6px',
    cursor: 'pointer',
  },
  historyQuery: {
    fontSize: '13px',
    color: '#f8fafc',
    fontWeight: 600,
  },
  historyTime: {
    fontSize: '11px',
    color: '#64748b',
  },
  historyMeta: {
    marginTop: '4px',
    display: 'flex',
    gap: '10px',
    fontSize: '11px',
    color: '#94a3b8',
  },
  errorBanner: {
    backgroundColor: '#450a0a',
    border: '1px solid #dc2626',
    borderRadius: '8px',
    padding: '12px 16px',
    marginBottom: '16px',
    color: '#fca5a5',
    display: 'flex',
    alignItems: 'center',
  },
  clearBtn: {
    position: 'absolute',
    right: '12px',
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: '14px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: '16px',
  },
  modalBackdrop: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: '#111827',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    width: '600px',
    maxWidth: '90%',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
  },
  modalBody: {
    color: '#cbd5e1',
    fontSize: '14px',
  },
  modalMetaRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    marginBottom: '14px',
  },
  rawJsonPre: {
    marginTop: '6px',
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '12px',
    color: '#38bdf8',
    fontSize: '12px',
    overflowX: 'auto',
    whiteSpace: 'pre-wrap',
  },
};
