import React, { useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';
import type { Case, CaseCreatePayload, CaseStatus } from '../types/case';

interface CasesPageProps {
  onOpenCase: (caseId: string) => void;
}

export const CasesPage: React.FC<CasesPageProps> = ({ onOpenCase }) => {
  const { user } = useAuth();
  const [cases, setCases] = useState<Case[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters & Search
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newCaseNumber, setNewCaseNumber] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchCases = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.listCases(statusFilter);
      setCases(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load authorized cases.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [statusFilter]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!newTitle.trim()) {
      setFormError('Case Title is required.');
      return;
    }

    setIsSubmitting(true);
    try {
      const payload: CaseCreatePayload = {
        title: newTitle.trim(),
        description: newDesc.trim() || undefined,
        case_number: newCaseNumber.trim() || undefined,
      };
      const created = await apiClient.createCase(payload);
      setIsModalOpen(false);
      setNewTitle('');
      setNewDesc('');
      setNewCaseNumber('');
      fetchCases();
      onOpenCase(created.id);
    } catch (err: any) {
      setFormError(err.message || 'Failed to create case.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredCases = cases.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return c.case_number.toLowerCase().includes(q) || c.title.toLowerCase().includes(q);
  });

  const canCreateCase = user?.role === 'ADMIN' || user?.role === 'INVESTIGATOR';

  return (
    <div style={styles.container}>
      {/* Top Header */}
      <div style={styles.header}>
        <div>
          <div style={styles.breadcrumb}>WORKSPACE / CASE MANAGEMENT</div>
          <h1 style={styles.title}>Forensic Cases</h1>
          <p style={styles.subtitle}>
            Manage case scoping boundaries, lead investigators, and evidence access authorizations.
          </p>
        </div>

        {canCreateCase && (
          <button onClick={() => setIsModalOpen(true)} style={styles.createBtn}>
            + CREATE CASE
          </button>
        )}
      </div>

      {/* Control Bar: Filters & Search */}
      <div style={styles.controlBar}>
        <div style={styles.statusTabs}>
          {['ALL', 'OPEN', 'IN_PROGRESS', 'CLOSED', 'ARCHIVED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              style={{
                ...styles.statusTab,
                backgroundColor: statusFilter === st ? 'var(--bg-card)' : 'transparent',
                color: statusFilter === st ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                borderColor: statusFilter === st ? 'var(--accent-cyan)' : 'transparent',
              }}
            >
              {st}
            </button>
          ))}
        </div>

        <div style={styles.searchBox}>
          <span style={styles.searchIcon}>🔍</span>
          <input
            type="text"
            placeholder="Search by Case Number or Title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={styles.searchInput}
          />
        </div>
      </div>

      {errorMsg && (
        <div style={styles.errorAlert}>
          <span>⚠ {errorMsg}</span>
        </div>
      )}

      {/* Cases Table */}
      <div style={styles.tableCard}>
        {isLoading ? (
          <div style={styles.loadingState}>Querying authorized case records...</div>
        ) : filteredCases.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>📁</div>
            <div style={styles.emptyTitle}>No Authorized Cases Found</div>
            <div style={styles.emptyText}>
              {searchQuery
                ? 'No cases match your search query.'
                : 'You have not been assigned to any cases matching this status filter.'}
            </div>
            {canCreateCase && !searchQuery && (
              <button onClick={() => setIsModalOpen(true)} style={styles.createBtnEmpty}>
                Create Your First Case
              </button>
            )}
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr style={styles.tableHeaderRow}>
                <th style={styles.th}>CASE NUMBER</th>
                <th style={styles.th}>TITLE & DESCRIPTION</th>
                <th style={styles.th}>STATUS</th>
                <th style={styles.th}>YOUR ROLE</th>
                <th style={styles.th}>CREATED AT</th>
                <th style={styles.thRight}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.map((c) => (
                <tr key={c.id} style={styles.tableRow}>
                  <td style={styles.tdCaseNumber}>{c.case_number}</td>
                  <td style={styles.tdTitle}>
                    <div style={styles.caseTitleText}>{c.title}</div>
                    {c.description && <div style={styles.caseDescText}>{c.description}</div>}
                  </td>
                  <td style={styles.td}>
                    <span style={{ ...styles.statusBadge, ...getStatusStyle(c.status) }}>
                      {c.status}
                    </span>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.roleBadge}>{c.current_user_role || 'MEMBER'}</span>
                  </td>
                  <td style={styles.tdDate}>{new Date(c.created_at).toLocaleDateString()}</td>
                  <td style={styles.tdRight}>
                    <button onClick={() => onOpenCase(c.id)} style={styles.openBtn}>
                      OPEN CASE →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create Case Modal */}
      {isModalOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={styles.modalHeader}>
              <h3 style={styles.modalTitle}>Create New Forensic Case</h3>
              <button onClick={() => setIsModalOpen(false)} style={styles.modalClose}>
                ✕
              </button>
            </div>

            {formError && (
              <div style={styles.modalError}>
                <span>⚠ {formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateCase} style={styles.modalForm}>
              <div style={styles.fieldGroup}>
                <label style={styles.label}>CASE TITLE *</label>
                <input
                  type="text"
                  placeholder="e.g. Operation Silent Horizon"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                  style={styles.modalInput}
                />
              </div>

              <div style={styles.fieldGroup}>
                <label style={styles.label}>CASE NUMBER (OPTIONAL)</label>
                <input
                  type="text"
                  placeholder="Leave blank for automatic assignment (CASE-2026-XXXXXX)"
                  value={newCaseNumber}
                  onChange={(e) => setNewCaseNumber(e.target.value)}
                  style={styles.modalInput}
                />
              </div>

              <div style={styles.fieldGroup}>
                <label style={styles.label}>INVESTIGATION SCOPE & SUMMARY</label>
                <textarea
                  placeholder="Describe the background, incident context, or target artifacts..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={3}
                  style={styles.modalTextarea}
                />
              </div>

              <div style={styles.modalActions}>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  style={styles.cancelBtn}
                >
                  CANCEL
                </button>
                <button type="submit" disabled={isSubmitting} style={styles.submitBtn}>
                  {isSubmitting ? 'CREATING...' : 'CREATE CASE & ASSIGN LEAD'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

function getStatusStyle(status: CaseStatus): React.CSSProperties {
  switch (status) {
    case 'OPEN':
      return { backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#10B981', borderColor: 'rgba(16, 185, 129, 0.3)' };
    case 'IN_PROGRESS':
      return { backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#F59E0B', borderColor: 'rgba(245, 158, 11, 0.3)' };
    case 'CLOSED':
      return { backgroundColor: 'rgba(100, 116, 139, 0.1)', color: '#64748B', borderColor: 'rgba(100, 116, 139, 0.3)' };
    case 'ARCHIVED':
      return { backgroundColor: 'rgba(71, 85, 105, 0.1)', color: '#475569', borderColor: 'rgba(71, 85, 105, 0.3)' };
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px 32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    height: '100%',
    overflowY: 'auto',
    backgroundColor: '#0B1220',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottom: '1px solid #263449',
    paddingBottom: '16px',
  },
  breadcrumb: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: '#64748B',
    letterSpacing: '1px',
    marginBottom: '4px',
    textTransform: 'uppercase',
  },
  title: {
    fontSize: '22px',
    fontFamily: 'var(--font-heading)',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.02em',
  },
  subtitle: {
    fontSize: '12px',
    color: '#94A3B8',
    marginTop: '2px',
  },
  createBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    letterSpacing: '0.5px',
    padding: '8px 16px',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  controlBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '16px',
  },
  statusTabs: {
    display: 'flex',
    gap: '4px',
    backgroundColor: '#111827',
    padding: '3px',
    borderRadius: '4px',
    border: '1px solid #263449',
  },
  statusTab: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
    padding: '6px 14px',
    borderRadius: '3px',
    borderBottom: '2px solid transparent',
    transition: 'all 0.15s ease',
    cursor: 'pointer',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '6px 12px',
    width: '320px',
  },
  searchIcon: {
    fontSize: '12px',
    opacity: 0.6,
    color: '#94A3B8',
  },
  searchInput: {
    backgroundColor: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#F8FAFC',
    fontSize: '12px',
    width: '100%',
    fontFamily: 'var(--font-sans)',
  },
  errorAlert: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    color: '#EF4444',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '4px',
    padding: '10px 14px',
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
  },
  tableCard: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
  },
  tableHeaderRow: {
    backgroundColor: '#1E293B',
    borderBottom: '1px solid #263449',
  },
  th: {
    padding: '10px 14px',
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748B',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.8px',
    textTransform: 'uppercase',
  },
  thRight: {
    padding: '10px 14px',
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748B',
    fontFamily: 'var(--font-mono)',
    textAlign: 'right',
    letterSpacing: '0.8px',
    textTransform: 'uppercase',
  },
  tableRow: {
    borderBottom: '1px solid #263449',
    transition: 'background 0.15s ease',
  },
  tdCaseNumber: {
    padding: '12px 14px',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: 600,
    color: '#22D3EE',
    whiteSpace: 'nowrap',
  },
  tdTitle: {
    padding: '12px 14px',
    maxWidth: '380px',
  },
  caseTitleText: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#F8FAFC',
  },
  caseDescText: {
    fontSize: '11px',
    color: '#94A3B8',
    marginTop: '2px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '12px 14px',
    fontSize: '12px',
    color: '#94A3B8',
  },
  tdDate: {
    padding: '12px 14px',
    fontSize: '11px',
    color: '#64748B',
    fontFamily: 'var(--font-mono)',
  },
  tdRight: {
    padding: '12px 14px',
    textAlign: 'right',
  },
  statusBadge: {
    fontSize: '10px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    padding: '3px 8px',
    borderRadius: '3px',
    border: '1px solid transparent',
    letterSpacing: '0.5px',
  },
  roleBadge: {
    fontSize: '10px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    color: '#22D3EE',
    border: '1px solid rgba(34, 211, 238, 0.3)',
    padding: '2px 7px',
    borderRadius: '3px',
    letterSpacing: '0.5px',
  },
  openBtn: {
    backgroundColor: '#1E293B',
    color: '#22D3EE',
    border: '1px solid #263449',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
    padding: '5px 12px',
    borderRadius: '3px',
    letterSpacing: '0.5px',
    transition: 'all 0.15s ease',
  },
  loadingState: {
    padding: '40px',
    textAlign: 'center',
    color: '#64748B',
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '1px',
  },
  emptyState: {
    padding: '48px 24px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
    textAlign: 'center',
  },
  emptyIcon: {
    fontSize: '32px',
    opacity: 0.5,
  },
  emptyTitle: {
    fontSize: '14px',
    fontFamily: 'var(--font-heading)',
    fontWeight: 700,
    color: '#F8FAFC',
  },
  emptyText: {
    fontSize: '12px',
    color: '#64748B',
    maxWidth: '340px',
  },
  createBtnEmpty: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    padding: '8px 16px',
    borderRadius: '4px',
    marginTop: '8px',
    letterSpacing: '0.5px',
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(11, 18, 32, 0.85)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    backdropFilter: 'blur(4px)',
  },
  modalContent: {
    width: '100%',
    maxWidth: '520px',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.8)',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #263449',
    paddingBottom: '12px',
  },
  modalTitle: {
    fontSize: '15px',
    fontFamily: 'var(--font-heading)',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '0.02em',
  },
  modalClose: {
    fontSize: '16px',
    color: '#64748B',
    cursor: 'pointer',
  },
  modalError: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    color: '#EF4444',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    borderRadius: '4px',
    padding: '8px 12px',
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
  },
  modalForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
  },
  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  label: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748B',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.8px',
  },
  modalInput: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '8px 12px',
    color: '#F8FAFC',
    fontSize: '13px',
    outline: 'none',
  },
  modalTextarea: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '8px 12px',
    color: '#F8FAFC',
    fontSize: '13px',
    outline: 'none',
    fontFamily: 'var(--font-sans)',
    resize: 'vertical',
  },
  modalActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '10px',
    marginTop: '6px',
  },
  cancelBtn: {
    backgroundColor: 'transparent',
    color: '#94A3B8',
    border: '1px solid #263449',
    padding: '8px 14px',
    borderRadius: '4px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
  },
  submitBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
};
