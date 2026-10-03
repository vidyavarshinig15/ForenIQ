import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';

interface AuditEntry {
  id: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  user_id?: string;
  client_ip?: string;
  status?: string;
  timestamp: string;
  created_at?: string;
  details?: Record<string, any>;
}

interface ResourceTypeInfo {
  code: string;
  label: string;
  color: string;
  border: string;
  bg: string;
  description: string;
}

export const RESOURCE_TYPES_CATALOG: Record<string, ResourceTypeInfo> = {
  AUTH_SESSION: {
    code: 'AUTH_SESSION',
    label: 'AUTH SESSION',
    color: '#818CF8',
    border: 'rgba(129, 140, 248, 0.4)',
    bg: 'rgba(129, 140, 248, 0.12)',
    description: 'Investigator login, session validation, and JWT token issuance',
  },
  AUTH: {
    code: 'AUTH_SESSION',
    label: 'AUTH SESSION',
    color: '#818CF8',
    border: 'rgba(129, 140, 248, 0.4)',
    bg: 'rgba(129, 140, 248, 0.12)',
    description: 'Investigator authentication & access control',
  },
  USER: {
    code: 'USER',
    label: 'USER ACCOUNT',
    color: '#818CF8',
    border: 'rgba(129, 140, 248, 0.4)',
    bg: 'rgba(129, 140, 248, 0.12)',
    description: 'Examiner profile management & role-based permissions',
  },
  CASE: {
    code: 'CASE',
    label: 'CASE FILE',
    color: '#22D3EE',
    border: 'rgba(34, 211, 238, 0.4)',
    bg: 'rgba(34, 211, 238, 0.12)',
    description: 'Forensic case container (#CASE-YYYY-XXXX) & tenant scope boundary',
  },
  CASE_MEMBER: {
    code: 'CASE_MEMBER',
    label: 'CASE EXAMINER',
    color: '#22D3EE',
    border: 'rgba(34, 211, 238, 0.4)',
    bg: 'rgba(34, 211, 238, 0.12)',
    description: 'Assigned investigator credentials & case authorization',
  },
  evidence: {
    code: 'EVIDENCE',
    label: 'EVIDENCE VAULT',
    color: '#10B981',
    border: 'rgba(16, 185, 129, 0.4)',
    bg: 'rgba(16, 185, 129, 0.12)',
    description: 'Raw UFDR phone extraction or ZIP archive stored on disk',
  },
  EVIDENCE: {
    code: 'EVIDENCE',
    label: 'EVIDENCE VAULT',
    color: '#10B981',
    border: 'rgba(16, 185, 129, 0.4)',
    bg: 'rgba(16, 185, 129, 0.12)',
    description: 'Raw UFDR phone extraction or ZIP archive stored on disk',
  },
  canonical_evidence: {
    code: 'CANONICAL_ARTIFACT',
    label: 'PARSED ARTIFACT',
    color: '#3B82F6',
    border: 'rgba(59, 130, 246, 0.4)',
    bg: 'rgba(59, 130, 246, 0.12)',
    description: 'Normalized SMS, WhatsApp, call, contact, or media artifact',
  },
  processing_job: {
    code: 'PROCESSING_JOB',
    label: 'EXTRACTION PIPELINE',
    color: '#F59E0B',
    border: 'rgba(245, 158, 11, 0.4)',
    bg: 'rgba(245, 158, 11, 0.12)',
    description: 'Background worker parsing, Zip-Slip inspection, & embedding task',
  },
  evidence_integrity: {
    code: 'EVIDENCE_INTEGRITY',
    label: 'SHA-256 INTEGRITY',
    color: '#10B981',
    border: 'rgba(16, 185, 129, 0.4)',
    bg: 'rgba(16, 185, 129, 0.12)',
    description: 'Cryptographic SHA-256 hash baseline and periodic verification',
  },
  evidence_custody: {
    code: 'EVIDENCE_CUSTODY',
    label: 'CHAIN OF CUSTODY',
    color: '#10B981',
    border: 'rgba(16, 185, 129, 0.4)',
    bg: 'rgba(16, 185, 129, 0.12)',
    description: 'Append-only ISO/IEC 27037 custodial ledger of access & transfers',
  },
  REPORT: {
    code: 'REPORT',
    label: 'COURT REPORT',
    color: '#EC4899',
    border: 'rgba(236, 72, 153, 0.4)',
    bg: 'rgba(236, 72, 153, 0.12)',
    description: 'Cryptographically signed PDF findings and court trial exhibits',
  },
};

const ACTION_COLORS: Record<string, { color: string; border: string; bg: string }> = {
  LOGIN_SUCCESS: { color: '#10B981', border: 'rgba(16, 185, 129, 0.4)', bg: 'rgba(16, 185, 129, 0.12)' },
  LOGOUT: { color: '#94A3B8', border: 'rgba(148, 163, 184, 0.4)', bg: 'rgba(148, 163, 184, 0.12)' },
  LOGIN_FAILURE: { color: '#EF4444', border: 'rgba(239, 68, 68, 0.4)', bg: 'rgba(239, 68, 68, 0.12)' },
  CASE_CREATE: { color: '#22D3EE', border: 'rgba(34, 211, 238, 0.4)', bg: 'rgba(34, 211, 238, 0.12)' },
  CASE_UPDATE: { color: '#3B82F6', border: 'rgba(59, 130, 246, 0.4)', bg: 'rgba(59, 130, 246, 0.12)' },
  EVIDENCE_UPLOAD: { color: '#22D3EE', border: 'rgba(34, 211, 238, 0.4)', bg: 'rgba(34, 211, 238, 0.12)' },
  EVIDENCE_PARSE: { color: '#3B82F6', border: 'rgba(59, 130, 246, 0.4)', bg: 'rgba(59, 130, 246, 0.12)' },
  EVIDENCE_DELETE: { color: '#EF4444', border: 'rgba(239, 68, 68, 0.4)', bg: 'rgba(239, 68, 68, 0.12)' },
  SEARCH: { color: '#3B82F6', border: 'rgba(59, 130, 246, 0.4)', bg: 'rgba(59, 130, 246, 0.12)' },
  REPORT_GENERATE: { color: '#22D3EE', border: 'rgba(34, 211, 238, 0.4)', bg: 'rgba(34, 211, 238, 0.12)' },
  REPORT_EXPORTED: { color: '#F59E0B', border: 'rgba(245, 158, 11, 0.4)', bg: 'rgba(245, 158, 11, 0.12)' },
  ACCESS_DENIED: { color: '#EF4444', border: 'rgba(239, 68, 68, 0.4)', bg: 'rgba(239, 68, 68, 0.12)' },
};

export const AuditLogsPage: React.FC = () => {
  const { user } = useAuth();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [resourceFilter, setResourceFilter] = useState('ALL');
  const [refreshedAt, setRefreshedAt] = useState(new Date());
  const [showCatalog, setShowCatalog] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getAuditLogs(undefined, 100);
      setEntries(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || 'Unable to retrieve audit records.');
      setEntries([]);
    } finally {
      setLoading(false);
      setRefreshedAt(new Date());
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = entries.filter((e) => {
    // Resource filter
    if (resourceFilter !== 'ALL') {
      const canonicalType = (RESOURCE_TYPES_CATALOG[e.resource_type || '']?.code || e.resource_type || '').toUpperCase();
      if (canonicalType !== resourceFilter) {
        return false;
      }
    }

    // Text search
    const q = filter.toLowerCase();
    if (!q) return true;

    return (
      e.action?.toLowerCase().includes(q) ||
      e.resource_type?.toLowerCase().includes(q) ||
      e.resource_id?.toLowerCase().includes(q) ||
      e.client_ip?.toLowerCase().includes(q) ||
      e.status?.toLowerCase().includes(q) ||
      (e.details && JSON.stringify(e.details).toLowerCase().includes(q))
    );
  });

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('en-US', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });
    } catch {
      return iso;
    }
  };

  const getResourceTypeBadge = (rawType?: string) => {
    const key = rawType || 'SYSTEM';
    const config = RESOURCE_TYPES_CATALOG[key] || {
      code: key.toUpperCase(),
      label: key.toUpperCase(),
      color: '#94A3B8',
      border: 'rgba(148, 163, 184, 0.4)',
      bg: 'rgba(148, 163, 184, 0.12)',
      description: 'System-level operation',
    };

    return (
      <span
        style={{
          ...styles.resourceBadge,
          color: config.color,
          borderColor: config.border,
          backgroundColor: config.bg,
        }}
        title={`Resource Category: ${config.code} — ${config.description}`}
      >
        {config.label}
      </span>
    );
  };

  const renderResourceDetails = (entry: AuditEntry) => {
    // 1. Explicit resource_id
    if (entry.resource_id) {
      return (
        <div style={styles.detailContainer}>
          <span style={styles.resourceIdPill}>{entry.resource_id}</span>
          {entry.details && Object.keys(entry.details).length > 0 && (
            <span style={styles.detailsMeta}>
              {Object.entries(entry.details)
                .map(([k, v]) => `${k}: ${v}`)
                .join(' • ')}
            </span>
          )}
        </div>
      );
    }

    // 2. Authentication actions without explicit resource_id
    if (
      entry.action === 'LOGIN_SUCCESS' ||
      entry.action === 'LOGOUT' ||
      entry.action === 'LOGIN_FAILURE'
    ) {
      const email = entry.details?.email || (entry.action === 'LOGIN_SUCCESS' ? (user?.email || 'admin@ufdr.org') : 'admin@ufdr.org');
      const role = entry.details?.role || user?.role || 'ADMIN';
      return (
        <div style={styles.detailContainer}>
          <span style={styles.resourceIdPill}>{email}</span>
          <span style={styles.roleTag}>{role}</span>
        </div>
      );
    }

    // 3. Details dictionary
    if (entry.details && Object.keys(entry.details).length > 0) {
      return (
        <span style={styles.detailsMeta}>
          {Object.entries(entry.details)
            .map(([k, v]) => `${k}: ${v}`)
            .join(' • ')}
        </span>
      );
    }

    // 4. Default fallback
    return <span style={{ color: '#64748B' }}>System Handoff</span>;
  };

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.headerBar}>
        <div>
          <div style={styles.breadcrumb}>
            <span>Workspace</span>
            <span style={styles.breadcrumbSep}>›</span>
            <span>Governance</span>
            <span style={styles.breadcrumbSep}>›</span>
            <span style={styles.breadcrumbActive}>Audit Logs</span>
          </div>
          <h1 style={styles.title}>Immutable Audit Trail</h1>
        </div>

        <div style={styles.headerRight}>
          <div style={styles.statusBadgeGlobal}>
            <span style={styles.greenDot} />
            <span style={styles.statusBadgeText}>
              LEDGER: APPEND-ONLY • {refreshedAt.toLocaleTimeString('en-US', { hour12: false })}
            </span>
          </div>
          <button onClick={load} style={styles.refreshBtn} title="Refresh audit logs from PostgreSQL">
            ↻ REFRESH
          </button>
        </div>
      </div>

      {/* Resource Types Catalog & Standard Banner */}
      <div style={styles.catalogCard}>
        <div style={styles.catalogHeader} onClick={() => setShowCatalog(!showCatalog)}>
          <div style={styles.catalogTitleBox}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
            <span style={styles.catalogTitle}>ForenIQ Standard Forensic Resource Types</span>
            <span style={styles.catalogBadge}>ISO/IEC 27037 Standard</span>
          </div>
          <button style={styles.toggleCatalogBtn}>
            {showCatalog ? 'Hide Schema ▲' : 'View Resource Schema ▼'}
          </button>
        </div>

        {showCatalog && (
          <div style={styles.catalogGrid}>
            {[
              { type: 'AUTH_SESSION', label: 'USER SESSION', desc: 'Investigator authentication, tokens, & sessions', color: '#818CF8' },
              { type: 'CASE', label: 'CASE FILE', desc: 'Investigative case boundaries & scope access', color: '#22D3EE' },
              { type: 'EVIDENCE', label: 'EVIDENCE VAULT', desc: 'Raw UFDR phone extractions and ZIP packages', color: '#10B981' },
              { type: 'CANONICAL_ARTIFACT', label: 'PARSED ARTIFACT', desc: 'Extracted SMS, WhatsApp, and call logs', color: '#3B82F6' },
              { type: 'PROCESSING_JOB', label: 'EXTRACTION PIPELINE', desc: 'Background parser & worker extraction jobs', color: '#F59E0B' },
              { type: 'REPORT', label: 'COURT REPORT', desc: 'Signed forensic PDF findings and court exhibits', color: '#EC4899' },
            ].map((item) => (
              <div key={item.type} style={styles.catalogItem}>
                <div style={styles.catalogItemTop}>
                  <span style={{ ...styles.typeTag, color: item.color, borderColor: `${item.color}40`, backgroundColor: `${item.color}15` }}>
                    {item.label}
                  </span>
                  <code style={styles.typeCode}>{item.type}</code>
                </div>
                <div style={styles.catalogItemDesc}>{item.desc}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Stats Row */}
      <div style={styles.statsRow}>
        {[
          { label: 'Total Audit Events', value: entries.length, color: '#22D3EE' },
          { label: 'Unique Actions', value: new Set(entries.map((e) => e.action)).size, color: '#3B82F6' },
          { label: 'Verified Records', value: entries.filter((e) => e.status === 'SUCCESS').length, color: '#10B981' },
          { label: 'Filtered Results', value: filtered.length, color: '#F59E0B' },
        ].map(({ label, value, color }) => (
          <div key={label} style={styles.statCard}>
            <div style={{ ...styles.statValue, color }}>{loading ? '—' : value}</div>
            <div style={styles.statLabel}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filter Toolbar */}
      <div style={styles.filterRow}>
        <div style={styles.searchWrapper}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            placeholder="Search by action, examiner email, IP address, or ID..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={styles.filterInput}
          />
          {filter && (
            <button onClick={() => setFilter('')} style={styles.clearBtn}>
              ✕
            </button>
          )}
        </div>

        {/* Resource Type Filter */}
        <select
          value={resourceFilter}
          onChange={(e) => setResourceFilter(e.target.value)}
          style={styles.resourceSelect}
        >
          <option value="ALL">All Forensic Resource Types</option>
          <option value="AUTH_SESSION">User Sessions (AUTH_SESSION)</option>
          <option value="CASE">Case Files (CASE)</option>
          <option value="EVIDENCE">Evidence Archives (EVIDENCE)</option>
          <option value="CANONICAL_ARTIFACT">Parsed Artifacts (CANONICAL)</option>
          <option value="PROCESSING_JOB">Extraction Jobs (PROCESSING_JOB)</option>
          <option value="REPORT">Court Reports (REPORT)</option>
        </select>
      </div>

      {/* Table Container */}
      <div style={styles.tableContainer}>
        {loading ? (
          <div style={styles.centeredMsg}>
            <div style={styles.spinner} />
            <div style={styles.msgText}>INITIALIZING AUDIT TRAIL STREAM...</div>
          </div>
        ) : error ? (
          <div style={styles.centeredMsg}>
            <div style={{ fontSize: '24px', color: '#EF4444' }}>⚠️</div>
            <div style={{ ...styles.msgText, color: '#EF4444' }}>{error}</div>
          </div>
        ) : entries.length === 0 ? (
          <div style={styles.centeredMsg}>
            <div style={styles.emptyIcon}>📋</div>
            <div style={styles.msgTitle}>Audit Ledger Operational</div>
            <div style={styles.msgText}>
              All forensic events are logged to the PostgreSQL audit table automatically.
              No events recorded yet in this environment.
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div style={styles.centeredMsg}>
            <div style={{ fontSize: '24px', color: '#F59E0B' }}>🔍</div>
            <div style={styles.msgText}>No audit entries match the specified filter criteria.</div>
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>TIMESTAMP</th>
                <th style={styles.th}>ACTION</th>
                <th style={styles.th}>RESOURCE TYPE</th>
                <th style={styles.th}>RESOURCE IDENTIFIER / DETAILS</th>
                <th style={styles.th}>CLIENT IP</th>
                <th style={styles.th}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => {
                const badge = ACTION_COLORS[entry.action] || {
                  color: '#94A3B8',
                  border: 'rgba(148, 163, 184, 0.4)',
                  bg: 'rgba(148, 163, 184, 0.12)',
                };
                const timeStr = entry.timestamp || entry.created_at || '';
                return (
                  <tr key={entry.id} style={styles.tr}>
                    <td style={styles.tdTimestamp}>{formatDate(timeStr)}</td>
                    <td style={styles.td}>
                      <span
                        style={{
                          ...styles.actionBadge,
                          borderColor: badge.border,
                          color: badge.color,
                          backgroundColor: badge.bg,
                        }}
                      >
                        {entry.action}
                      </span>
                    </td>
                    <td style={styles.td}>
                      {getResourceTypeBadge(entry.resource_type)}
                    </td>
                    <td style={styles.td}>
                      {renderResourceDetails(entry)}
                    </td>
                    <td style={styles.tdMono}>{entry.client_ip || '127.0.0.1'}</td>
                    <td style={styles.td}>
                      <span
                        style={{
                          ...styles.statusBadge,
                          color: entry.status === 'SUCCESS' ? '#10B981' : '#EF4444',
                          borderColor: entry.status === 'SUCCESS' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)',
                          backgroundColor:
                            entry.status === 'SUCCESS'
                              ? 'rgba(16, 185, 129, 0.12)'
                              : 'rgba(239, 68, 68, 0.12)',
                        }}
                      >
                        {entry.status || 'LOGGED'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer */}
      <div style={styles.footer}>
        <span>Audit Standard: ISO/IEC 27037 Tamper-Proof Digital Evidence Custody</span>
        <span>
          Authenticated Examiner: <strong style={{ color: '#22D3EE', fontFamily: 'var(--font-mono)' }}>{user?.email}</strong> ({user?.role})
        </span>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: '28px 32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    maxWidth: '1600px',
    margin: '0 auto',
    width: '100%',
  },
  headerBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    flexWrap: 'wrap',
    gap: '16px',
  },
  breadcrumb: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
    color: '#64748B',
    marginBottom: '6px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  breadcrumbSep: {
    color: '#475569',
  },
  breadcrumbActive: {
    color: '#22D3EE',
    fontWeight: 500,
  },
  title: {
    fontSize: '26px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.5px',
    margin: 0,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  statusBadgeGlobal: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    border: '1px solid rgba(16, 185, 129, 0.25)',
    padding: '7px 14px',
    borderRadius: '20px',
  },
  greenDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#10B981',
    boxShadow: '0 0 6px #10B981',
  },
  statusBadgeText: {
    color: '#E2E8F0',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: "'IBM Plex Mono', monospace",
  },
  refreshBtn: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    color: '#22D3EE',
    padding: '7px 14px',
    borderRadius: '8px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  catalogCard: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 4px 14px rgba(0, 0, 0, 0.15)',
  },
  catalogHeader: {
    padding: '14px 20px',
    backgroundColor: 'rgba(17, 24, 39, 0.6)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
  },
  catalogTitleBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  catalogTitle: {
    fontSize: '14px',
    fontWeight: 700,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  catalogBadge: {
    fontSize: '10px',
    fontWeight: 700,
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    color: '#22D3EE',
    border: '1px solid rgba(34, 211, 238, 0.25)',
    padding: '2px 7px',
    borderRadius: '8px',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  toggleCatalogBtn: {
    backgroundColor: 'transparent',
    border: 'none',
    color: '#94A3B8',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  catalogGrid: {
    padding: '16px 20px',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '14px',
    borderTop: '1px solid rgba(38, 52, 73, 0.7)',
  },
  catalogItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    padding: '12px',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '8px',
  },
  catalogItemTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  typeTag: {
    fontSize: '10px',
    fontWeight: 700,
    border: '1px solid',
    padding: '2px 6px',
    borderRadius: '6px',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  typeCode: {
    fontSize: '10px',
    color: '#64748B',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  catalogItemDesc: {
    fontSize: '11px',
    color: '#94A3B8',
    lineHeight: 1.3,
  },
  statsRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '14px',
  },
  statCard: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '10px',
    padding: '16px 18px',
  },
  statValue: {
    fontSize: '28px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    lineHeight: 1.1,
  },
  statLabel: {
    fontSize: '12px',
    color: '#94A3B8',
    marginTop: '4px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  filterRow: {
    display: 'flex',
    gap: '14px',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  searchWrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '8px',
    padding: '8px 14px',
    flex: 1,
    minWidth: '280px',
  },
  filterInput: {
    backgroundColor: 'transparent',
    border: 'none',
    color: '#F8FAFC',
    fontSize: '13px',
    width: '100%',
    outline: 'none',
    boxShadow: 'none',
  },
  clearBtn: {
    color: '#64748B',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: '12px',
  },
  resourceSelect: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    color: '#F8FAFC',
    borderRadius: '8px',
    padding: '9px 14px',
    fontSize: '13px',
    cursor: 'pointer',
    minWidth: '240px',
  },
  tableContainer: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '12px',
    overflowX: 'auto',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    padding: '12px 18px',
    fontSize: '11px',
    fontWeight: 600,
    color: '#64748B',
    textAlign: 'left',
    letterSpacing: '0.6px',
    borderBottom: '1px solid #263449',
    backgroundColor: 'rgba(17, 24, 39, 0.6)',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  tr: {
    borderBottom: '1px solid rgba(38, 52, 73, 0.5)',
    transition: 'background-color 0.15s ease',
  },
  td: {
    padding: '14px 18px',
    fontSize: '13px',
    verticalAlign: 'middle',
  },
  tdTimestamp: {
    padding: '14px 18px',
    fontSize: '12px',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#94A3B8',
    whiteSpace: 'nowrap',
  },
  tdMono: {
    padding: '14px 18px',
    fontSize: '12px',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#CBD5E1',
  },
  actionBadge: {
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: '6px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.5px',
    border: '1px solid',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  resourceBadge: {
    display: 'inline-block',
    padding: '3px 9px',
    borderRadius: '6px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.4px',
    border: '1px solid',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  detailContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
  },
  resourceIdPill: {
    color: '#22D3EE',
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '12px',
    fontWeight: 600,
  },
  roleTag: {
    fontSize: '9px',
    fontWeight: 700,
    color: '#94A3B8',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid #263449',
    padding: '1px 5px',
    borderRadius: '4px',
  },
  detailsMeta: {
    fontSize: '11px',
    color: '#94A3B8',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  statusBadge: {
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: '6px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.4px',
    border: '1px solid',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  centeredMsg: {
    padding: '60px 20px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    textAlign: 'center',
  },
  spinner: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    border: '2px solid rgba(34, 211, 238, 0.2)',
    borderTopColor: '#22D3EE',
    animation: 'spin 1s linear infinite',
  },
  msgTitle: {
    fontSize: '16px',
    fontWeight: 700,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  msgText: {
    fontSize: '13px',
    color: '#94A3B8',
    maxWidth: '400px',
  },
  emptyIcon: {
    fontSize: '32px',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    color: '#64748B',
    padding: '10px 0',
    flexWrap: 'wrap',
    gap: '10px',
  },
};
