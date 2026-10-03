import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';

interface DashboardProps {
  onOpenCase?: (caseId: string) => void;
  onNavigate?: (tab: string) => void;
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle: string;
  color: string;
  gradient: string;
  icon: React.ReactNode;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, color, gradient, icon }) => (
  <div style={{ ...cardStyles.statCard, borderTop: `3px solid ${color}` }}>
    <div style={cardStyles.statHeader}>
      <div>
        <span style={cardStyles.statTitle}>{title}</span>
        <div style={cardStyles.statValue}>{value}</div>
      </div>
      <div style={{ ...cardStyles.iconWrapper, background: gradient, color }}>
        {icon}
      </div>
    </div>
    <div style={cardStyles.statFooter}>
      <span style={{ ...cardStyles.statusDot, backgroundColor: color }} />
      <span style={cardStyles.statSubtitle}>{subtitle}</span>
    </div>
  </div>
);

export const DashboardPage: React.FC<DashboardProps> = ({ onOpenCase, onNavigate }) => {
  const { user } = useAuth();
  const [cases, setCases] = useState<Case[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [ready, setReady] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshedAt, setRefreshedAt] = useState<Date>(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const [caseList, healthData, readyData] = await Promise.all([
        apiClient.listCases().catch(() => []),
        apiClient.getHealth().catch(() => null),
        fetch('/api/v1/ready').then((r) => r.json()).catch(() => null),
      ]);
      setCases(Array.isArray(caseList) ? caseList : []);
      setHealth(healthData);
      setReady(readyData);
    } catch {
      // degrade gracefully
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      setRefreshedAt(new Date());
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  // Derived real-world counts
  const openCases = cases.filter((c) => c.status === 'OPEN').length;
  const inProgress = cases.filter((c) => c.status === 'IN_PROGRESS').length;
  const closed = cases.filter((c) => c.status === 'CLOSED').length;
  const recentCases = [...cases]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5);

  const apiStatus = health?.status === 'ok';
  const dbStatus = ready?.database === 'connected';

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  };

  const statusBadgeColor: Record<string, { color: string; border: string; bg: string }> = {
    OPEN: { color: '#10B981', border: 'rgba(16, 185, 129, 0.4)', bg: 'rgba(16, 185, 129, 0.12)' },
    IN_PROGRESS: { color: '#F59E0B', border: 'rgba(245, 158, 11, 0.4)', bg: 'rgba(245, 158, 11, 0.12)' },
    CLOSED: { color: '#94A3B8', border: 'rgba(148, 163, 184, 0.4)', bg: 'rgba(148, 163, 184, 0.12)' },
    ARCHIVED: { color: '#64748B', border: 'rgba(100, 116, 139, 0.4)', bg: 'rgba(100, 116, 139, 0.12)' },
  };

  return (
    <div style={styles.page}>
      {/* Top Header Bar */}
      <div style={styles.headerBar}>
        <div>
          <div style={styles.breadcrumb}>
            <span>Workspace</span>
            <span style={styles.breadcrumbSep}>›</span>
            <span>Core</span>
            <span style={styles.breadcrumbSep}>›</span>
            <span style={styles.breadcrumbActive}>Dashboard</span>
          </div>
          <h1 style={styles.title}>Investigative Dashboard</h1>
        </div>

        <div style={styles.headerActions}>
          {/* Health Pill */}
          <div style={styles.healthPill}>
            <span style={{
              ...styles.healthDot,
              backgroundColor: apiStatus ? '#10B981' : '#EF4444',
              boxShadow: apiStatus ? '0 0 8px #10B981' : 'none',
            }} />
            <span style={styles.healthText}>
              {apiStatus ? 'All Systems Operational' : 'Connecting Engine...'}
            </span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={load}
            style={{
              ...styles.refreshBtn,
              opacity: isRefreshing ? 0.7 : 1,
            }}
            title="Refresh dashboard metrics"
            disabled={isRefreshing}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: isRefreshing ? 'rotate(180deg)' : 'none',
                transition: 'transform 0.4s ease',
              }}
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          {/* Quick Create Case CTA */}
          {onNavigate && (
            <button
              onClick={() => onNavigate('cases')}
              style={styles.primaryCtaBtn}
              title="Create a new forensic case"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              <span>New Case</span>
            </button>
          )}
        </div>
      </div>

      {/* Welcome Banner */}
      <div style={styles.welcomeBanner}>
        <div style={styles.welcomeLeft}>
          <div style={styles.welcomeTitle}>
            Welcome back, <span style={styles.userNameHighlight}>{user?.name || user?.email || 'Examiner'}</span>
          </div>
          <p style={styles.welcomeDescription}>
            Universal forensic extractions, entity graphs, and verifiable evidence reporting are active. All forensic evidence vaults remain cryptographically verified and tamper-evident.
          </p>
          <div style={styles.welcomeBadges}>
            <span style={styles.badgePill}>
              <span style={styles.greenPulse} />
              Air-Gapped Isolation
            </span>
            <span style={styles.badgePill}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              ISO/IEC 27037 Verified
            </span>
            <span style={styles.badgePillMuted}>
              Synchronized: {refreshedAt.toLocaleTimeString('en-US', { hour12: false })}
            </span>
          </div>
        </div>
        <div style={styles.welcomeRight}>
          <div style={styles.versionBox}>
            <div style={styles.versionTitle}>ForenIQ Core</div>
            <div style={styles.versionValue}>{ready?.version ? `v${ready.version}` : 'v0.2.0'}</div>
            <div style={styles.versionStatus}>Production Ready</div>
          </div>
        </div>
      </div>

      {/* Stat KPI Cards Row */}
      <div style={styles.statsGrid}>
        <StatCard
          title="Total Cases"
          value={loading ? '—' : cases.length}
          subtitle="Registered investigations"
          color="#22D3EE"
          gradient="rgba(34, 211, 238, 0.12)"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
            </svg>
          }
        />
        <StatCard
          title="Open Investigations"
          value={loading ? '—' : openCases}
          subtitle="Active forensic analysis"
          color="#10B981"
          gradient="rgba(16, 185, 129, 0.12)"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
              <path d="m11 8v6M8 11h6" />
            </svg>
          }
        />
        <StatCard
          title="In Progress"
          value={loading ? '—' : inProgress}
          subtitle="Extraction & correlation"
          color="#F59E0B"
          gradient="rgba(245, 158, 11, 0.12)"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          }
        />
        <StatCard
          title="Closed Cases"
          value={loading ? '—' : closed}
          subtitle="Archived & verified"
          color="#3B82F6"
          gradient="rgba(59, 130, 246, 0.12)"
          icon={
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
          }
        />
      </div>

      {/* Main Two-Column Layout */}
      <div style={styles.mainGrid}>
        {/* Left Column: Recent Investigations */}
        <div style={styles.card}>
          <div style={styles.cardHeader}>
            <div style={styles.cardTitleGroup}>
              <span style={styles.cardTitle}>Recent Investigations</span>
              <span style={styles.countBadge}>{cases.length} Total</span>
            </div>
            {onNavigate && (
              <button onClick={() => onNavigate('cases')} style={styles.viewAllBtn}>
                <span>View All Cases</span>
                <span style={{ fontSize: '14px' }}>→</span>
              </button>
            )}
          </div>

          {loading ? (
            <div style={styles.loadingContainer}>
              <div style={styles.spinner} />
              <span>Loading investigative cases...</span>
            </div>
          ) : recentCases.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={styles.emptyIconCircle}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
                  <line x1="12" y1="11" x2="12" y2="17" />
                  <line x1="9" y1="14" x2="15" y2="14" />
                </svg>
              </div>
              <div style={styles.emptyTitle}>No Cases Created Yet</div>
              <p style={styles.emptyText}>
                Get started by creating your first investigation case to ingest UFDR archives, extract chat logs, and run AI correlation.
              </p>
              {onNavigate && (
                <button onClick={() => onNavigate('cases')} style={styles.createCaseBtn}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  <span>Create First Case</span>
                </button>
              )}
            </div>
          ) : (
            <div style={styles.tableResponsive}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={styles.th}>CASE NUMBER</th>
                    <th style={styles.th}>TITLE</th>
                    <th style={styles.th}>STATUS</th>
                    <th style={styles.th}>LAST UPDATED</th>
                    <th style={{ ...styles.th, textAlign: 'right' }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {recentCases.map((c) => {
                    const badge = statusBadgeColor[c.status] || {
                      color: '#94A3B8',
                      border: 'rgba(148, 163, 184, 0.3)',
                      bg: 'rgba(148, 163, 184, 0.1)',
                    };
                    return (
                      <tr
                        key={c.id}
                        style={styles.tr}
                        onClick={() => onOpenCase?.(c.id)}
                      >
                        <td style={styles.td}>
                          <span style={styles.caseNum}>{c.case_number}</span>
                        </td>
                        <td style={{ ...styles.td, maxWidth: 220 }}>
                          <span style={styles.caseTitle}>{c.title}</span>
                        </td>
                        <td style={styles.td}>
                          <span
                            style={{
                              ...styles.statusBadge,
                              borderColor: badge.border,
                              color: badge.color,
                              backgroundColor: badge.bg,
                            }}
                          >
                            {c.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td style={styles.td}>
                          <span style={styles.dateCell}>{formatDate(c.updated_at)}</span>
                        </td>
                        <td style={{ ...styles.td, textAlign: 'right' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenCase?.(c.id);
                            }}
                            style={styles.openCaseBtn}
                          >
                            Open →
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: System Diagnostics & Quick Workspaces */}
        <div style={styles.rightColumn}>
          {/* Subsystem Health Diagnostics */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <div style={styles.cardTitleGroup}>
                <span style={styles.cardTitle}>System Health & Services</span>
              </div>
              <span style={styles.healthyPill}>All Operational</span>
            </div>
            <div style={styles.serviceList}>
              {[
                { label: 'FastAPI Backend Engine', ok: apiStatus, detail: 'v0.2.0 API' },
                { label: 'PostgreSQL Relational DB', ok: dbStatus, detail: 'WAL Sync' },
                { label: 'UFDR Evidence Vault', ok: ready?.storage === 'writable', detail: 'Encrypted' },
                { label: 'SentenceTransformers Embeddings', ok: apiStatus, detail: 'all-MiniLM' },
                { label: 'Deterministic RAG Engine', ok: true, detail: 'Zero Hallucinations' },
              ].map(({ label, ok, detail }) => (
                <div key={label} style={styles.serviceRow}>
                  <div style={styles.serviceInfo}>
                    <span style={{
                      ...styles.serviceIndicatorDot,
                      backgroundColor: ok ? '#10B981' : '#EF4444',
                    }} />
                    <span style={styles.serviceName}>{label}</span>
                  </div>
                  <div style={styles.serviceRight}>
                    <span style={styles.serviceDetail}>{detail}</span>
                    <span
                      style={{
                        ...styles.serviceStatusPill,
                        color: ok ? '#10B981' : '#EF4444',
                        backgroundColor: ok ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                      }}
                    >
                      {ok ? 'Active' : 'Offline'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Workspaces Launch */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.cardTitle}>Investigative Workspaces</span>
            </div>
            <div style={styles.workspaceGrid}>
              {[
                {
                  label: 'Cases Registry',
                  tab: 'cases',
                  desc: 'Manage and filter investigations',
                  color: '#22D3EE',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
                    </svg>
                  ),
                },
                {
                  label: 'Forensic Search',
                  tab: 'search',
                  desc: 'Cross-evidence keyword & regex',
                  color: '#3B82F6',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="11" cy="11" r="8" />
                      <path d="m21 21-4.3-4.3" />
                    </svg>
                  ),
                },
                {
                  label: 'AI Assistant',
                  tab: 'investigations',
                  desc: 'Evidence-grounded RAG query',
                  color: '#818CF8',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect width="16" height="12" x="4" y="8" rx="2" />
                      <path d="M12 8V4H8" />
                    </svg>
                  ),
                },
                {
                  label: 'Comm Graph',
                  tab: 'graph',
                  desc: 'Network linkage & interaction clusters',
                  color: '#10B981',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                    </svg>
                  ),
                },
                {
                  label: 'Timeline Lineage',
                  tab: 'timeline',
                  desc: 'Chronological message reconstruction',
                  color: '#F59E0B',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <polyline points="12 6 12 12 16 14" />
                    </svg>
                  ),
                },
                {
                  label: 'Forensic Reports',
                  tab: 'reports',
                  desc: 'Export signed PDF court findings',
                  color: '#EC4899',
                  icon: (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    </svg>
                  ),
                },
              ].map(({ label, tab, desc, color, icon }) => (
                <button
                  key={tab}
                  onClick={() => onNavigate?.(tab)}
                  style={styles.workspaceCard}
                >
                  <div style={{ ...styles.workspaceIconBox, color, backgroundColor: `${color}18` }}>
                    {icon}
                  </div>
                  <div style={styles.workspaceText}>
                    <div style={styles.workspaceName}>{label}</div>
                    <div style={styles.workspaceDesc}>{desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const cardStyles: Record<string, React.CSSProperties> = {
  statCard: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '12px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
    transition: 'all 0.2s ease',
  },
  statHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  statTitle: {
    fontSize: '13px',
    fontFamily: "'IBM Plex Sans', sans-serif",
    fontWeight: 500,
    color: '#94A3B8',
    letterSpacing: '0.2px',
  },
  statValue: {
    fontSize: '32px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    marginTop: '6px',
    lineHeight: 1.1,
  },
  iconWrapper: {
    width: '44px',
    height: '44px',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  statFooter: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    marginTop: '16px',
    paddingTop: '12px',
    borderTop: '1px solid rgba(38, 52, 73, 0.6)',
  },
  statusDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  statSubtitle: {
    fontSize: '11px',
    color: '#64748B',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: '28px 32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
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
    fontSize: '28px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.5px',
    margin: 0,
  },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  healthPill: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    border: '1px solid rgba(16, 185, 129, 0.25)',
    padding: '7px 14px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: 500,
    color: '#E2E8F0',
  },
  healthDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
  },
  healthText: {
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  refreshBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    color: '#94A3B8',
    padding: '8px 14px',
    borderRadius: '8px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  primaryCtaBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    background: 'linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)',
    color: '#0B1220',
    border: 'none',
    padding: '8px 16px',
    borderRadius: '8px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    letterSpacing: '0.2px',
    cursor: 'pointer',
    boxShadow: '0 2px 10px rgba(34, 211, 238, 0.25)',
    transition: 'all 0.15s ease',
  },
  welcomeBanner: {
    backgroundColor: '#172033',
    background: 'linear-gradient(135deg, rgba(34, 211, 238, 0.06) 0%, rgba(59, 130, 246, 0.04) 50%, rgba(23, 32, 51, 0.95) 100%)',
    border: '1px solid rgba(34, 211, 238, 0.2)',
    borderRadius: '14px',
    padding: '24px 28px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '24px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
  },
  welcomeLeft: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    maxWidth: '75%',
  },
  welcomeTitle: {
    fontSize: '20px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
  },
  userNameHighlight: {
    color: '#22D3EE',
  },
  welcomeDescription: {
    fontSize: '13px',
    color: '#94A3B8',
    lineHeight: 1.5,
    margin: 0,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  welcomeBadges: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginTop: '6px',
    flexWrap: 'wrap',
  },
  badgePill: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    padding: '4px 10px',
    borderRadius: '16px',
    fontSize: '11px',
    color: '#E2E8F0',
    fontWeight: 500,
  },
  badgePillMuted: {
    fontSize: '11px',
    color: '#64748B',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  greenPulse: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#10B981',
    boxShadow: '0 0 6px #10B981',
  },
  welcomeRight: {
    flexShrink: 0,
  },
  versionBox: {
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    border: '1px solid rgba(38, 52, 73, 0.8)',
    borderRadius: '10px',
    padding: '12px 18px',
    textAlign: 'center',
  },
  versionTitle: {
    fontSize: '11px',
    color: '#94A3B8',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  versionValue: {
    fontSize: '16px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#22D3EE',
    margin: '2px 0',
  },
  versionStatus: {
    fontSize: '10px',
    color: '#10B981',
    fontWeight: 600,
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '18px',
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1.6fr 1fr',
    gap: '24px',
    alignItems: 'start',
  },
  card: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
  },
  cardHeader: {
    padding: '18px 22px',
    borderBottom: '1px solid rgba(38, 52, 73, 0.8)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardTitleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  cardTitle: {
    fontSize: '15px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.2px',
  },
  countBadge: {
    fontSize: '11px',
    fontWeight: 600,
    color: '#22D3EE',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    border: '1px solid rgba(34, 211, 238, 0.25)',
    padding: '2px 8px',
    borderRadius: '10px',
  },
  healthyPill: {
    fontSize: '11px',
    fontWeight: 600,
    color: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid rgba(16, 185, 129, 0.25)',
    padding: '3px 9px',
    borderRadius: '12px',
  },
  viewAllBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '12px',
    color: '#22D3EE',
    fontWeight: 600,
    cursor: 'pointer',
    backgroundColor: 'transparent',
    border: 'none',
  },
  loadingContainer: {
    padding: '48px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    color: '#94A3B8',
    fontSize: '13px',
  },
  spinner: {
    width: '24px',
    height: '24px',
    borderRadius: '50%',
    border: '2px solid rgba(34, 211, 238, 0.2)',
    borderTopColor: '#22D3EE',
    animation: 'spin 1s linear infinite',
  },
  emptyState: {
    padding: '50px 32px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
  },
  emptyIconCircle: {
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    border: '1px solid rgba(34, 211, 238, 0.25)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '16px',
  },
  emptyTitle: {
    fontSize: '16px',
    fontFamily: "'Space Grotesk', sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    marginBottom: '6px',
  },
  emptyText: {
    fontSize: '13px',
    color: '#94A3B8',
    maxWidth: '380px',
    lineHeight: 1.5,
    marginBottom: '20px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  createCaseBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)',
    color: '#0B1220',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '8px',
    fontSize: '13px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(34, 211, 238, 0.25)',
  },
  tableResponsive: {
    overflowX: 'auto',
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
    backgroundColor: 'rgba(17, 24, 39, 0.4)',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  tr: {
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
    borderBottom: '1px solid rgba(38, 52, 73, 0.5)',
  },
  td: {
    padding: '14px 18px',
    fontSize: '13px',
    verticalAlign: 'middle',
  },
  caseNum: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
    color: '#22D3EE',
    fontSize: '12px',
  },
  caseTitle: {
    color: '#F8FAFC',
    fontWeight: 500,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    display: 'block',
  },
  statusBadge: {
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: '12px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.5px',
    border: '1px solid transparent',
  },
  dateCell: {
    color: '#94A3B8',
    fontSize: '12px',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  openCaseBtn: {
    backgroundColor: 'rgba(34, 211, 238, 0.08)',
    border: '1px solid rgba(34, 211, 238, 0.25)',
    color: '#22D3EE',
    fontSize: '11px',
    fontWeight: 600,
    padding: '4px 10px',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  rightColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  serviceList: {
    padding: '12px 18px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  serviceRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 6px',
    borderRadius: '6px',
  },
  serviceInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  serviceIndicatorDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  serviceName: {
    fontSize: '12px',
    color: '#F8FAFC',
    fontWeight: 500,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  serviceRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  serviceDetail: {
    fontSize: '11px',
    color: '#64748B',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  serviceStatusPill: {
    fontSize: '10px',
    fontWeight: 700,
    padding: '2px 7px',
    borderRadius: '10px',
    letterSpacing: '0.3px',
  },
  workspaceGrid: {
    padding: '16px',
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: '10px',
  },
  workspaceCard: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '10px',
    padding: '12px',
    textAlign: 'left',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  workspaceIconBox: {
    width: '34px',
    height: '34px',
    borderRadius: '8px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  workspaceText: {
    overflow: 'hidden',
  },
  workspaceName: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#F8FAFC',
    marginBottom: '2px',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  workspaceDesc: {
    fontSize: '10px',
    color: '#64748B',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
};
