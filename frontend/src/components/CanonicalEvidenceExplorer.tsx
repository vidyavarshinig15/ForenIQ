import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/api/client';
import type {
  ArtifactType,
  CanonicalEvidence,
  DataQualityStatus,
  Evidence,
  RawArtifact,
} from '../types/evidence';

interface CanonicalEvidenceExplorerProps {
  caseId: string;
  evidence: Evidence;
  onSelectRawArtifact?: (rawArtifact: RawArtifact) => void;
}

export const CanonicalEvidenceExplorer: React.FC<CanonicalEvidenceExplorerProps> = ({
  caseId,
  evidence,
  onSelectRawArtifact,
}) => {
  const [records, setRecords] = useState<CanonicalEvidence[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedQuality, setSelectedQuality] = useState<string>('ALL');
  const [appFilter, setAppFilter] = useState<string>('');
  const [debouncedAppFilter, setDebouncedAppFilter] = useState<string>('');

  // Inspection Drawer
  const [inspectingRecord, setInspectingRecord] = useState<CanonicalEvidence | null>(null);
  const [originatingRaw, setOriginatingRaw] = useState<RawArtifact | null>(null);
  const [isLoadingRaw, setIsLoadingRaw] = useState<boolean>(false);
  const [rawFetchError, setRawFetchError] = useState<string | null>(null);
  const [copiedFingerprint, setCopiedFingerprint] = useState<boolean>(false);
  const [copiedRawPayload, setCopiedRawPayload] = useState<boolean>(false);
  const [activeDetailTab, setActiveDetailTab] = useState<'OVERVIEW' | 'ENTITIES' | 'TRACEABILITY' | 'RAW_ORIGIN'>('OVERVIEW');

  // Debounce app filter input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedAppFilter(appFilter);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [appFilter]);

  const loadRecords = async (pageNum: number = page) => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const res = await apiClient.listCanonicalRecords(caseId, evidence.id, {
        artifactType: selectedCategory !== 'ALL' ? selectedCategory : undefined,
        dataQualityStatus: selectedQuality !== 'ALL' ? selectedQuality : undefined,
        application: debouncedAppFilter ? debouncedAppFilter : undefined,
        page: pageNum,
        pageSize: 30,
      });
      setRecords(res.items || []);
      setTotal(res.total || 0);
      setPage(res.page || 1);
      setTotalPages(res.total_pages || 1);
    } catch (err: any) {
      console.error('Failed to load canonical records:', err);
      setFetchError(err?.message || 'Failed to retrieve canonical records');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRecords(page);
  }, [caseId, evidence.id, selectedCategory, selectedQuality, debouncedAppFilter, page]);

  // Load originating raw artifact when inspecting a canonical record
  const inspectRecord = async (rec: CanonicalEvidence) => {
    setInspectingRecord(rec);
    setOriginatingRaw(null);
    setIsLoadingRaw(true);
    setRawFetchError(null);
    setActiveDetailTab('OVERVIEW');

    try {
      const raw = await apiClient.getCanonicalRecordOriginatingRaw(caseId, rec.id);
      setOriginatingRaw(raw);
    } catch (err: any) {
      console.error('Failed to load originating raw artifact:', err);
      setRawFetchError(err?.message || 'Could not fetch originating raw artifact');
    } finally {
      setIsLoadingRaw(false);
    }
  };

  const copyToClipboard = (text: string, type: 'fingerprint' | 'raw') => {
    navigator.clipboard.writeText(text);
    if (type === 'fingerprint') {
      setCopiedFingerprint(true);
      setTimeout(() => setCopiedFingerprint(false), 2000);
    } else {
      setCopiedRawPayload(true);
      setTimeout(() => setCopiedRawPayload(false), 2000);
    }
  };

  const formatTimestamp = (ts?: string | null) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toUTCString().replace('GMT', 'UTC');
    } catch {
      return ts;
    }
  };

  const getQualityBadgeStyle = (status: DataQualityStatus) => {
    switch (status) {
      case 'VALID':
        return { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.4)' };
      case 'PARTIAL':
        return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.4)' };
      case 'INVALID':
        return { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)' };
      default:
        return { backgroundColor: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', border: '1px solid rgba(148, 163, 184, 0.4)' };
    }
  };

  const getArtifactTypeStyle = (type: ArtifactType) => {
    switch (type) {
      case 'CALL':
        return { backgroundColor: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.35)' };
      case 'MESSAGE':
        return { backgroundColor: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', border: '1px solid rgba(168, 85, 247, 0.35)' };
      case 'CONTACT':
        return { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#4ade80', border: '1px solid rgba(34, 197, 94, 0.35)' };
      case 'LOCATION':
        return { backgroundColor: 'rgba(249, 115, 22, 0.15)', color: '#fb923c', border: '1px solid rgba(249, 115, 22, 0.35)' };
      case 'BROWSER':
        return { backgroundColor: 'rgba(234, 179, 8, 0.15)', color: '#facc15', border: '1px solid rgba(234, 179, 8, 0.35)' };
      case 'APPLICATION':
        return { backgroundColor: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.35)' };
      case 'FILESYSTEM':
        return { backgroundColor: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.35)' };
      default:
        return { backgroundColor: 'rgba(148, 163, 184, 0.15)', color: '#cbd5e1', border: '1px solid rgba(148, 163, 184, 0.35)' };
    }
  };

  const getPrecisionBadgeStyle = (precision: string) => {
    switch (precision) {
      case 'MILLISECOND':
      case 'SECOND':
        return { backgroundColor: 'rgba(16, 185, 129, 0.12)', color: '#34d399' };
      case 'MINUTE':
      case 'HOUR':
        return { backgroundColor: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8' };
      case 'DAY':
      case 'MONTH':
      case 'YEAR':
        return { backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#fbbf24' };
      default:
        return { backgroundColor: 'rgba(148, 163, 184, 0.12)', color: '#94a3b8' };
    }
  };

  return (
    <div style={styles.container}>
      {/* Top Filter Bar */}
      <div style={styles.filterSection}>
        <div style={styles.chipBar}>
          {[
            { label: 'ALL CATEGORIES', value: 'ALL' },
            { label: 'CALLS', value: 'CALL' },
            { label: 'MESSAGES', value: 'MESSAGE' },
            { label: 'CONTACTS', value: 'CONTACT' },
            { label: 'LOCATIONS', value: 'LOCATION' },
            { label: 'BROWSER', value: 'BROWSER' },
            { label: 'APPS', value: 'APPLICATION' },
            { label: 'FILESYSTEM', value: 'FILESYSTEM' },
          ].map((chip) => (
            <button
              key={chip.value}
              onClick={() => {
                setSelectedCategory(chip.value);
                setPage(1);
              }}
              style={{
                ...styles.chipBtn,
                ...(selectedCategory === chip.value ? styles.activeChipBtn : {}),
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>

        <div style={styles.secondaryFilterBar}>
          <div style={styles.filterGroup}>
            <span style={styles.filterLabel}>DATA QUALITY:</span>
            <select
              value={selectedQuality}
              onChange={(e) => {
                setSelectedQuality(e.target.value);
                setPage(1);
              }}
              style={styles.selectInput}
            >
              <option value="ALL">All Quality States</option>
              <option value="VALID">VALID ONLY</option>
              <option value="PARTIAL">PARTIAL (Missing Optional Fields)</option>
              <option value="INVALID">INVALID (Validation Failures)</option>
            </select>
          </div>

          <div style={styles.filterGroup}>
            <span style={styles.filterLabel}>APPLICATION:</span>
            <input
              type="text"
              placeholder="Filter by app (e.g. WhatsApp, Chrome)..."
              value={appFilter}
              onChange={(e) => setAppFilter(e.target.value)}
              style={styles.textInput}
            />
          </div>

          <div style={styles.totalBadge}>
            TOTAL NORMALIZED: <strong style={{ color: 'var(--accent-cyan)' }}>{total.toLocaleString()}</strong>
          </div>
        </div>
      </div>

      {fetchError && (
        <div style={styles.errorBox}>
          <span>⚠ {fetchError}</span>
        </div>
      )}

      {/* Canonical Records Table */}
      {isLoading ? (
        <div style={styles.loadingBox}>
          <div style={styles.spinner} />
          <span>Retrieving canonical forensic records...</span>
        </div>
      ) : records.length === 0 ? (
        <div style={styles.emptyStateCard}>
          <div style={styles.emptyIcon}>🛡</div>
          <div style={styles.emptyTitle}>No Canonical Records Found</div>
          <div style={styles.emptyDesc}>
            {total === 0
              ? 'Evidence has not been normalized yet or contains 0 parsed records. Trigger normalization from the PARSING PIPELINE tab.'
              : 'No canonical records match the selected filter criteria.'}
          </div>
        </div>
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>CATEGORY</th>
                <th style={styles.th}>CANONICAL FINGERPRINT / ID</th>
                <th style={styles.th}>EVENT TIMESTAMP (UTC) & PRECISION</th>
                <th style={styles.th}>APP / DEVICE</th>
                <th style={styles.th}>CONTENT & ENTITIES PREVIEW</th>
                <th style={styles.th}>QUALITY</th>
                <th style={styles.th}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => {
                const typeStyle = getArtifactTypeStyle(rec.artifact_type);
                const qualityStyle = getQualityBadgeStyle(rec.data_quality_status);
                const precisionStyle = getPrecisionBadgeStyle(rec.timestamp_precision);

                return (
                  <tr key={rec.id} style={styles.tr}>
                    <td style={styles.td}>
                      <span style={{ ...styles.categoryBadge, ...typeStyle }}>
                        {rec.artifact_type}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <div style={styles.fingerprintCol}>
                        <code style={styles.codeText} title={rec.canonical_fingerprint}>
                          {rec.canonical_fingerprint.slice(0, 14)}...
                        </code>
                        <div style={styles.idSubtext} title={rec.record_identifier}>
                          Ref: {rec.record_identifier}
                        </div>
                      </div>
                    </td>
                    <td style={styles.td}>
                      <div style={styles.timestampCol}>
                        <span style={styles.utcTime}>{formatTimestamp(rec.event_timestamp)}</span>
                        <div style={styles.badgeRow}>
                          <span style={{ ...styles.miniBadge, ...precisionStyle }}>
                            {rec.timestamp_precision}
                          </span>
                          {rec.timestamp_status === 'INVALID' && (
                            <span style={styles.invalidTsBadge}>INVALID TS</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={styles.td}>
                      <div style={styles.appCol}>
                        <span style={styles.appName}>{rec.application || 'System / OS'}</span>
                        {rec.device_id && <span style={styles.deviceText}>Dev: {rec.device_id}</span>}
                      </div>
                    </td>
                    <td style={styles.td}>
                      <div style={styles.contentPreview}>
                        {rec.content ? (
                          <div style={styles.contentSnippet} title={rec.content}>
                            {rec.content.length > 80 ? `${rec.content.slice(0, 80)}...` : rec.content}
                          </div>
                        ) : (
                          <div style={styles.emptyContentText}>No text payload</div>
                        )}
                        {rec.entities && rec.entities.length > 0 && (
                          <div style={styles.entityTagRow}>
                            {rec.entities.slice(0, 3).map((ent, idx) => (
                              <span key={idx} style={styles.entityTag} title={`${ent.role}: ${ent.entity_value}`}>
                                <strong style={styles.entityTypePrefix}>{ent.entity_type}:</strong>{' '}
                                {ent.normalized_value || ent.entity_value}
                              </span>
                            ))}
                            {rec.entities.length > 3 && (
                              <span style={styles.moreEntitiesBadge}>+{rec.entities.length - 3}</span>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={styles.td}>
                      <span style={{ ...styles.qualityBadge, ...qualityStyle }}>
                        ● {rec.data_quality_status}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <button
                        onClick={() => inspectRecord(rec)}
                        style={styles.inspectBtn}
                        title="Inspect canonical record details, normalized entities, and source provenance"
                      >
                        INSPECT
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div style={styles.paginationBar}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || isLoading}
            style={styles.pageBtn}
          >
            ← PREVIOUS
          </button>
          <span style={styles.pageIndicator}>
            PAGE <strong style={{ color: 'var(--text-primary)' }}>{page}</strong> OF {totalPages} ({total} records)
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || isLoading}
            style={styles.pageBtn}
          >
            NEXT →
          </button>
        </div>
      )}

      {/* Forensic Record Detail Drawer / Modal */}
      {inspectingRecord && (
        <div style={styles.drawerOverlay} onClick={() => setInspectingRecord(null)}>
          <div style={styles.drawerContent} onClick={(e) => e.stopPropagation()}>
            {/* Drawer Header */}
            <div style={styles.drawerHeader}>
              <div style={styles.drawerTitleRow}>
                <span style={{ ...styles.categoryBadge, ...getArtifactTypeStyle(inspectingRecord.artifact_type) }}>
                  {inspectingRecord.artifact_type}
                </span>
                <span style={{ ...styles.qualityBadge, ...getQualityBadgeStyle(inspectingRecord.data_quality_status) }}>
                  ● {inspectingRecord.data_quality_status}
                </span>
                <span style={styles.drawerTitle}>Canonical Evidence Inspector</span>
              </div>
              <button onClick={() => setInspectingRecord(null)} style={styles.closeBtn}>
                ✕
              </button>
            </div>

            {/* Subheader: Deterministic Identity */}
            <div style={styles.identityBar}>
              <div style={styles.identityItem}>
                <span style={styles.identityLabel}>DETERMINISTIC FINGERPRINT:</span>
                <code style={styles.identityCode}>{inspectingRecord.canonical_fingerprint}</code>
              </div>
              <button
                onClick={() => copyToClipboard(inspectingRecord.canonical_fingerprint, 'fingerprint')}
                style={styles.copyBtn}
              >
                {copiedFingerprint ? '✓ COPIED' : 'COPY FINGERPRINT'}
              </button>
            </div>

            {/* Detail Tabs */}
            <div style={styles.detailTabBar}>
              <button
                onClick={() => setActiveDetailTab('OVERVIEW')}
                style={{
                  ...styles.detailTabBtn,
                  ...(activeDetailTab === 'OVERVIEW' ? styles.activeDetailTabBtn : {}),
                }}
              >
                STANDARDIZED RECORD
              </button>
              <button
                onClick={() => setActiveDetailTab('ENTITIES')}
                style={{
                  ...styles.detailTabBtn,
                  ...(activeDetailTab === 'ENTITIES' ? styles.activeDetailTabBtn : {}),
                }}
              >
                NORMALIZED ENTITIES ({inspectingRecord.entities.length})
              </button>
              <button
                onClick={() => setActiveDetailTab('TRACEABILITY')}
                style={{
                  ...styles.detailTabBtn,
                  ...(activeDetailTab === 'TRACEABILITY' ? styles.activeDetailTabBtn : {}),
                }}
              >
                PROVENANCE & TRACEABILITY
              </button>
              <button
                onClick={() => setActiveDetailTab('RAW_ORIGIN')}
                style={{
                  ...styles.detailTabBtn,
                  ...(activeDetailTab === 'RAW_ORIGIN' ? styles.activeDetailTabBtn : {}),
                }}
              >
                ORIGINATING RAW ARTIFACT
              </button>
            </div>

            {/* Tab 1: Standardized Record Overview */}
            {activeDetailTab === 'OVERVIEW' && (
              <div style={styles.drawerBody}>
                {/* Timestamp Card */}
                <div style={styles.sectionCard}>
                  <div style={styles.sectionHeader}>🕒 NORMALIZED CHRONOLOGY & PRECISION</div>
                  <div style={styles.grid2Col}>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>EVENT TIMESTAMP (UTC):</span>
                      <span style={styles.metricVal}>{formatTimestamp(inspectingRecord.event_timestamp)}</span>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>TIMESTAMP PRECISION:</span>
                      <span style={{ ...styles.miniBadge, ...getPrecisionBadgeStyle(inspectingRecord.timestamp_precision) }}>
                        {inspectingRecord.timestamp_precision}
                      </span>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>ORIGINAL RAW TIMESTAMP:</span>
                      <code style={styles.metricCode}>{inspectingRecord.original_timestamp || 'None in source'}</code>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>ORIGINAL TIMEZONE:</span>
                      <span style={styles.metricVal}>{inspectingRecord.original_timezone || 'UNKNOWN'}</span>
                    </div>
                  </div>
                </div>

                {/* Content Card */}
                <div style={styles.sectionCard}>
                  <div style={styles.sectionHeader}>📝 VERBATIM CONTENT PAYLOAD</div>
                  {inspectingRecord.content ? (
                    <div style={styles.contentBox}>{inspectingRecord.content}</div>
                  ) : (
                    <div style={styles.emptyNote}>No textual body content in this record.</div>
                  )}
                </div>

                {/* Validation Warnings */}
                {inspectingRecord.validation_warnings && inspectingRecord.validation_warnings.length > 0 && (
                  <div style={styles.warningCard}>
                    <div style={styles.warningHeader}>⚠ VALIDATION ANOMALIES & AUDIT FLAGS</div>
                    <div style={styles.warningList}>
                      {inspectingRecord.validation_warnings.map((warn, idx) => (
                        <div key={idx} style={styles.warningItem}>
                          <span style={warn.severity === 'ERROR' ? styles.errorTag : styles.warningTag}>
                            {warn.severity}
                          </span>
                          <span style={styles.warningCode}>[{warn.code}]</span>
                          <span style={styles.warningMsg}>{warn.message}</span>
                          {warn.field && <code style={styles.warningField}>Field: {warn.field}</code>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Metadata JSON */}
                <div style={styles.sectionCard}>
                  <div style={styles.sectionHeader}>⚙ STRUCTURED NORMALIZED METADATA</div>
                  <pre style={styles.jsonViewer}>
                    {JSON.stringify(inspectingRecord.metadata, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Tab 2: Normalized Entities */}
            {activeDetailTab === 'ENTITIES' && (
              <div style={styles.drawerBody}>
                {inspectingRecord.entities.length === 0 ? (
                  <div style={styles.emptyStateCard}>
                    <div style={styles.emptyIcon}>👤</div>
                    <div style={styles.emptyTitle}>No Entities Extracted</div>
                    <div style={styles.emptyDesc}>
                      This canonical record does not reference explicit persons, phone numbers, emails, accounts, or URLs.
                    </div>
                  </div>
                ) : (
                  <div style={styles.entityTableWrapper}>
                    <table style={styles.table}>
                      <thead>
                        <tr>
                          <th style={styles.th}>ENTITY TYPE</th>
                          <th style={styles.th}>ROLE</th>
                          <th style={styles.th}>RAW EXTRACTED VALUE</th>
                          <th style={styles.th}>CANONICAL NORMALIZED VALUE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {inspectingRecord.entities.map((ent, idx) => (
                          <tr key={idx} style={styles.tr}>
                            <td style={styles.td}>
                              <span style={styles.entityBadge}>{ent.entity_type}</span>
                            </td>
                            <td style={styles.td}>
                              <span style={styles.roleBadge}>{ent.role}</span>
                            </td>
                            <td style={styles.td}>
                              <code style={styles.entityValCode}>{ent.entity_value}</code>
                            </td>
                            <td style={styles.td}>
                              <code style={styles.normalizedValCode}>
                                {ent.normalized_value || <span style={styles.mutedText}>Identical to raw</span>}
                              </code>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Provenance & Traceability */}
            {activeDetailTab === 'TRACEABILITY' && (
              <div style={styles.drawerBody}>
                <div style={styles.provenanceFlow}>
                  <div style={styles.provenanceStep}>
                    <span style={styles.stepNum}>1</span>
                    <div style={styles.stepContent}>
                      <span style={styles.stepTitle}>Original Evidence Package</span>
                      <code style={styles.stepDetail}>ID: {inspectingRecord.evidence_id}</code>
                      <div style={styles.stepDesc}>Filename: {evidence.original_filename}</div>
                    </div>
                  </div>
                  <div style={styles.provenanceArrow}>↓</div>
                  <div style={styles.provenanceStep}>
                    <span style={styles.stepNum}>2</span>
                    <div style={styles.stepContent}>
                      <span style={styles.stepTitle}>Originating Raw Artifact</span>
                      <code style={styles.stepDetail}>Raw Artifact ID: {inspectingRecord.raw_artifact_id}</code>
                      <div style={styles.stepDesc}>Source File: {inspectingRecord.source_file}</div>
                      <div style={styles.stepDesc}>Source Path: {inspectingRecord.source_path}</div>
                      <div style={styles.stepDesc}>Source Record Identifier: {inspectingRecord.record_identifier}</div>
                    </div>
                  </div>
                  <div style={styles.provenanceArrow}>↓</div>
                  <div style={styles.provenanceStep}>
                    <span style={styles.stepNum}>3</span>
                    <div style={styles.stepContent}>
                      <span style={styles.stepTitle}>Canonical Evidence Record</span>
                      <code style={styles.stepDetail}>Canonical ID: {inspectingRecord.id}</code>
                      <div style={styles.stepDesc}>Parser Version: v{inspectingRecord.parser_version}</div>
                      <div style={styles.stepDesc}>Normalizer Version: v{inspectingRecord.normalizer_version}</div>
                    </div>
                  </div>
                </div>

                <div style={styles.sectionCard}>
                  <div style={styles.sectionHeader}>🔗 FORENSIC TRACEABILITY MATRIX</div>
                  <div style={styles.grid2Col}>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>CASE ID:</span>
                      <code style={styles.metricCode}>{inspectingRecord.case_id}</code>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>EVIDENCE ID:</span>
                      <code style={styles.metricCode}>{inspectingRecord.evidence_id}</code>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>RAW ARTIFACT ID:</span>
                      <code style={styles.metricCode}>{inspectingRecord.raw_artifact_id}</code>
                    </div>
                    <div style={styles.metricBlock}>
                      <span style={styles.metricLabel}>PROCESSING JOB ID:</span>
                      <code style={styles.metricCode}>{inspectingRecord.processing_job_id || 'Direct Pipeline'}</code>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tab 4: Originating Raw Artifact Verification */}
            {activeDetailTab === 'RAW_ORIGIN' && (
              <div style={styles.drawerBody}>
                {isLoadingRaw ? (
                  <div style={styles.loadingBox}>
                    <div style={styles.spinner} />
                    <span>Resolving originating RawArtifact record...</span>
                  </div>
                ) : rawFetchError ? (
                  <div style={styles.errorBox}>
                    <span>⚠ Traceability Error: {rawFetchError}</span>
                  </div>
                ) : originatingRaw ? (
                  <div>
                    <div style={styles.rawOriginHeader}>
                      <div>
                        <div style={styles.rawOriginTitle}>Direct Verification: RawArtifact Record</div>
                        <div style={styles.rawOriginSub}>
                          Originating XML / UFDR source preserved verbatim without mutation.
                        </div>
                      </div>
                      <div style={styles.rawBtnGroup}>
                        <button
                          onClick={() => copyToClipboard(JSON.stringify(originatingRaw.raw_data, null, 2), 'raw')}
                          style={styles.copyBtn}
                        >
                          {copiedRawPayload ? '✓ COPIED JSON' : 'COPY RAW JSON'}
                        </button>
                        {onSelectRawArtifact && (
                          <button
                            onClick={() => {
                              onSelectRawArtifact(originatingRaw);
                              setInspectingRecord(null);
                            }}
                            style={styles.jumpRawBtn}
                          >
                            OPEN IN RAW EXPLORER →
                          </button>
                        )}
                      </div>
                    </div>

                    <div style={styles.sectionCard}>
                      <div style={styles.sectionHeader}>RAW FORENSIC PAYLOAD (VERBATIM)</div>
                      <pre style={styles.jsonViewer}>
                        {JSON.stringify(originatingRaw.raw_data, null, 2)}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div style={styles.emptyNote}>Originating raw artifact could not be resolved.</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  filterSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    marginBottom: '16px',
    backgroundColor: 'var(--bg-secondary)',
    padding: '16px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  chipBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  },
  chipBtn: {
    padding: '6px 12px',
    borderRadius: '4px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-secondary)',
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  activeChipBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    borderColor: 'var(--accent-cyan)',
  },
  secondaryFilterBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: '8px',
    borderTop: '1px solid rgba(255, 255, 255, 0.05)',
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  filterLabel: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
  },
  selectInput: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-color)',
    color: 'var(--text-primary)',
    padding: '6px 10px',
    borderRadius: '4px',
    fontSize: '12px',
    outline: 'none',
  },
  textInput: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-color)',
    color: 'var(--text-primary)',
    padding: '6px 10px',
    borderRadius: '4px',
    fontSize: '12px',
    outline: 'none',
    minWidth: '220px',
  },
  totalBadge: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginLeft: 'auto',
  },
  tableWrapper: {
    overflowX: 'auto',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-secondary)',
    flex: 1,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
    textAlign: 'left',
  },
  th: {
    padding: '12px 14px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-muted)',
    fontWeight: 600,
    letterSpacing: '0.5px',
    fontSize: '11px',
    borderBottom: '1px solid var(--border-color)',
    whiteSpace: 'nowrap',
  },
  tr: {
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
    transition: 'background-color 0.15s ease',
  },
  td: {
    padding: '12px 14px',
    verticalAlign: 'top',
  },
  categoryBadge: {
    display: 'inline-block',
    padding: '4px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
  fingerprintCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  codeText: {
    fontSize: '11px',
    fontFamily: 'monospace',
    color: 'var(--accent-cyan)',
  },
  idSubtext: {
    fontSize: '10px',
    color: 'var(--text-muted)',
  },
  timestampCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  utcTime: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    whiteSpace: 'nowrap',
  },
  badgeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  miniBadge: {
    display: 'inline-block',
    padding: '2px 5px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
  invalidTsBadge: {
    display: 'inline-block',
    padding: '2px 5px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    color: '#f87171',
    border: '1px solid rgba(239, 68, 68, 0.4)',
  },
  appCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  appName: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  deviceText: {
    fontSize: '10px',
    color: 'var(--text-muted)',
  },
  contentPreview: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    maxWidth: '300px',
  },
  contentSnippet: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  emptyContentText: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontStyle: 'italic',
  },
  entityTagRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '4px',
  },
  entityTag: {
    fontSize: '10px',
    padding: '2px 6px',
    borderRadius: '3px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-color)',
  },
  entityTypePrefix: {
    color: 'var(--accent-cyan)',
    fontWeight: 600,
  },
  moreEntitiesBadge: {
    fontSize: '9px',
    padding: '2px 4px',
    borderRadius: '3px',
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    color: 'var(--text-muted)',
  },
  qualityBadge: {
    display: 'inline-block',
    padding: '4px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    whiteSpace: 'nowrap',
  },
  inspectBtn: {
    padding: '6px 12px',
    borderRadius: '4px',
    border: '1px solid var(--accent-cyan)',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  paginationBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    marginTop: '12px',
  },
  pageBtn: {
    padding: '6px 14px',
    borderRadius: '4px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  pageIndicator: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
  },
  emptyStateCard: {
    padding: '48px 24px',
    textAlign: 'center',
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  emptyIcon: {
    fontSize: '36px',
    marginBottom: '12px',
  },
  emptyTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    marginBottom: '8px',
  },
  emptyDesc: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    maxWidth: '480px',
    margin: '0 auto',
    lineHeight: '1.5',
  },
  loadingBox: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    padding: '48px 24px',
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
  spinner: {
    width: '18px',
    height: '18px',
    border: '2px solid var(--border-color)',
    borderTopColor: 'var(--accent-cyan)',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  errorBox: {
    padding: '12px 16px',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '6px',
    color: '#f87171',
    fontSize: '12px',
    marginBottom: '12px',
  },
  drawerOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    display: 'flex',
    justifyContent: 'flex-end',
    zIndex: 1000,
    backdropFilter: 'blur(3px)',
  },
  drawerContent: {
    width: '680px',
    maxWidth: '90vw',
    height: '100%',
    backgroundColor: 'var(--bg-primary)',
    borderLeft: '1px solid var(--border-color)',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '-8px 0 24px rgba(0, 0, 0, 0.5)',
  },
  drawerHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '18px 20px',
    borderBottom: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-secondary)',
  },
  drawerTitleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  drawerTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '0.3px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '16px',
    cursor: 'pointer',
    padding: '4px 8px',
  },
  identityBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 20px',
    backgroundColor: 'var(--bg-tertiary)',
    borderBottom: '1px solid var(--border-color)',
  },
  identityItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    overflow: 'hidden',
  },
  identityLabel: {
    fontSize: '9px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
  },
  identityCode: {
    fontSize: '11px',
    fontFamily: 'monospace',
    color: 'var(--accent-cyan)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  copyBtn: {
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-secondary)',
    color: 'var(--text-secondary)',
    fontSize: '10px',
    fontWeight: 600,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    marginLeft: '12px',
  },
  detailTabBar: {
    display: 'flex',
    backgroundColor: 'var(--bg-secondary)',
    borderBottom: '1px solid var(--border-color)',
    padding: '0 16px',
    overflowX: 'auto',
  },
  detailTabBtn: {
    padding: '10px 14px',
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: 'var(--text-muted)',
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  activeDetailTabBtn: {
    color: 'var(--accent-cyan)',
    borderBottomColor: 'var(--accent-cyan)',
  },
  drawerBody: {
    padding: '20px',
    overflowY: 'auto',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  sectionCard: {
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    padding: '16px',
  },
  sectionHeader: {
    fontSize: '11px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
    marginBottom: '12px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
    paddingBottom: '6px',
  },
  grid2Col: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: '12px',
  },
  metricBlock: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  metricLabel: {
    fontSize: '10px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
  },
  metricVal: {
    fontSize: '13px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  metricCode: {
    fontSize: '12px',
    fontFamily: 'monospace',
    color: 'var(--accent-cyan)',
  },
  contentBox: {
    padding: '12px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    fontSize: '13px',
    lineHeight: '1.6',
    color: 'var(--text-primary)',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  warningCard: {
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
    border: '1px solid rgba(245, 158, 11, 0.3)',
    borderRadius: '8px',
    padding: '14px 16px',
  },
  warningHeader: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#fbbf24',
    letterSpacing: '0.5px',
    marginBottom: '10px',
  },
  warningList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  warningItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
  },
  warningTag: {
    padding: '2px 5px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    color: '#fbbf24',
  },
  errorTag: {
    padding: '2px 5px',
    borderRadius: '3px',
    fontSize: '9px',
    fontWeight: 700,
    backgroundColor: 'rgba(239, 68, 68, 0.2)',
    color: '#f87171',
  },
  warningCode: {
    fontFamily: 'monospace',
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  warningMsg: {
    color: 'var(--text-primary)',
    flex: 1,
  },
  warningField: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
    padding: '2px 4px',
    borderRadius: '2px',
  },
  jsonViewer: {
    margin: 0,
    padding: '12px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    fontFamily: 'monospace',
    fontSize: '11px',
    lineHeight: '1.4',
    color: '#38bdf8',
    overflowX: 'auto',
    maxHeight: '260px',
  },
  entityTableWrapper: {
    overflowX: 'auto',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-secondary)',
  },
  entityBadge: {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '10px',
    fontWeight: 700,
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: '#38bdf8',
    border: '1px solid rgba(56, 189, 248, 0.3)',
  },
  roleBadge: {
    display: 'inline-block',
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '10px',
    fontWeight: 600,
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-secondary)',
  },
  entityValCode: {
    fontSize: '11px',
    fontFamily: 'monospace',
    color: 'var(--text-primary)',
  },
  normalizedValCode: {
    fontSize: '11px',
    fontFamily: 'monospace',
    color: '#34d399',
  },
  mutedText: {
    color: 'var(--text-muted)',
    fontStyle: 'italic',
  },
  provenanceFlow: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
  },
  provenanceStep: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
    width: '100%',
    padding: '12px 16px',
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  stepNum: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    border: '1px solid var(--accent-cyan)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '11px',
    fontWeight: 700,
    flexShrink: 0,
  },
  stepContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
  },
  stepTitle: {
    fontSize: '12px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  stepDetail: {
    fontSize: '10px',
    fontFamily: 'monospace',
    color: 'var(--accent-cyan)',
  },
  stepDesc: {
    fontSize: '11px',
    color: 'var(--text-secondary)',
  },
  provenanceArrow: {
    color: 'var(--accent-cyan)',
    fontSize: '16px',
    fontWeight: 700,
  },
  rawOriginHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
  },
  rawOriginTitle: {
    fontSize: '13px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  rawOriginSub: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  rawBtnGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  jumpRawBtn: {
    padding: '5px 12px',
    borderRadius: '4px',
    border: '1px solid var(--accent-cyan)',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    fontSize: '10px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  emptyNote: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontStyle: 'italic',
    padding: '12px',
    textAlign: 'center',
  },
};
