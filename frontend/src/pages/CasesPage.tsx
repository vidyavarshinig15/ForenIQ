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
      return { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-green)', borderColor: 'rgba(16, 185, 129, 0.3)' };
    case 'IN_PROGRESS':
      return { backgroundColor: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', borderColor: 'rgba(56, 189, 248, 0.3)' };
    case 'CLOSED':
      return { backgroundColor: 'rgba(100, 116, 139, 0.15)', color: 'var(--text-muted)', borderColor: 'rgba(100, 116, 139, 0.3)' };
    case 'ARCHIVED':
      return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)', borderColor: 'rgba(245, 158, 11, 0.3)' };
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
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '16px',
  },
  breadcrumb: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
    marginBottom: '4px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    letterSpacing: '-0.3px',
  },
  subtitle: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  createBtn: {
    backgroundColor: 'var(--accent-blue)',
    color: '#ffffff',
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    padding: '8px 14px',
    borderRadius: '4px',
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
    backgroundColor: 'var(--bg-surface)',
    padding: '3px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
  },
  statusTab: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '5px 12px',
    borderRadius: '3px',
    borderBottom: '2px solid transparent',
    transition: 'all 0.15s ease',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '6px 12px',
    width: '320px',
  },
  searchIcon: {
    fontSize: '12px',
    opacity: 0.6,
  },
  searchInput: {
    backgroundColor: 'transparent',
    border: 'none',
    outline: 'none',
    color: 'var(--text-primary)',
    fontSize: '12px',
    width: '100%',
  },
  errorAlert: {
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    color: 'var(--accent-rose)',
    border: '1px solid rgba(244, 63, 94, 0.3)',
    borderRadius: '4px',
    padding: '10px 14px',
    fontSize: '12px',
  },
  tableCard: {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    overflow: 'hidden',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
  },
  tableHeaderRow: {
    backgroundColor: 'var(--bg-card)',
    borderBottom: '1px solid var(--border-subtle)',
  },
  th: {
    padding: '10px 14px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.8px',
  },
  thRight: {
    padding: '10px 14px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    textAlign: 'right',
  },
  tableRow: {
    borderBottom: '1px solid var(--border-subtle)',
    transition: 'background 0.15s',
  },
  tdCaseNumber: {
    padding: '12px 14px',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--accent-cyan)',
    whiteSpace: 'nowrap',
  },
  tdTitle: {
    padding: '12px 14px',
    maxWidth: '380px',
  },
  caseTitleText: {
    fontSize: '13px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  caseDescText: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '2px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '12px 14px',
    fontSize: '12px',
  },
  tdDate: {
    padding: '12px 14px',
    fontSize: '11px',
    color: 'var(--text-muted)',
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
    borderRadius: '4px',
    border: '1px solid transparent',
  },
  roleBadge: {
    fontSize: '10px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    padding: '2px 6px',
    borderRadius: '3px',
  },
  openBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.12)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    fontSize: '11px',
    fontWeight: 600,
    padding: '5px 10px',
    borderRadius: '4px',
    transition: 'all 0.15s ease',
  },
  loadingState: {
    padding: '40px',
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '13px',
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
    fontSize: '15px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  emptyText: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    maxWidth: '340px',
  },
  createBtnEmpty: {
    backgroundColor: 'var(--accent-blue)',
    color: '#ffffff',
    fontSize: '11px',
    fontWeight: 600,
    padding: '8px 16px',
    borderRadius: '4px',
    marginTop: '8px',
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    width: '100%',
    maxWidth: '500px',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '12px',
  },
  modalTitle: {
    fontSize: '16px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  modalClose: {
    fontSize: '16px',
    color: 'var(--text-muted)',
  },
  modalError: {
    backgroundColor: 'rgba(244, 63, 94, 0.15)',
    color: 'var(--accent-rose)',
    border: '1px solid rgba(244, 63, 94, 0.3)',
    borderRadius: '4px',
    padding: '8px 12px',
    fontSize: '12px',
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
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
  },
  modalInput: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '8px 10px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    outline: 'none',
  },
  modalTextarea: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '8px 10px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    outline: 'none',
    fontFamily: 'inherit',
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
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-subtle)',
    padding: '8px 14px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
  },
  submitBtn: {
    backgroundColor: 'var(--accent-blue)',
    color: '#ffffff',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
  },
};
