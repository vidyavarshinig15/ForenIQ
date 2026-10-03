import React, { useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';
import type { Case, CaseAccessRole, CaseStatus } from '../types/case';
import { EvidenceSection } from '../components/EvidenceSection';

interface CaseDetailsPageProps {
  caseId: string;
  onBack: () => void;
  initialSubTab?: 'evidence' | 'team' | 'pipeline';
}

export const CaseDetailsPage: React.FC<CaseDetailsPageProps> = ({
  caseId,
  onBack,
  initialSubTab = 'evidence',
}) => {
  const { user } = useAuth();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'evidence' | 'team' | 'pipeline'>(
    initialSubTab
  );

  // Status Change State
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);

  // Add Member Modal State
  const [isAddMemberOpen, setIsAddMemberOpen] = useState<boolean>(false);
  const [memberEmail, setMemberEmail] = useState('');
  const [memberRole, setMemberRole] = useState<CaseAccessRole>('CONTRIBUTOR');
  const [memberError, setMemberError] = useState<string | null>(null);
  const [isSubmittingMember, setIsSubmittingMember] = useState(false);

  const fetchCaseDetails = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.getCase(caseId);
      setCaseData(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve case details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseDetails();
  }, [caseId]);

  const handleStatusChange = async (newStatus: CaseStatus) => {
    if (!caseData || caseData.status === newStatus) return;
    setIsUpdatingStatus(true);
    try {
      const updated = await apiClient.updateCase(caseId, { status: newStatus });
      setCaseData(updated);
    } catch (err: any) {
      alert(`Status update failed: ${err.message}`);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setMemberError(null);

    if (!memberEmail.trim()) {
      setMemberError('Investigator email is required.');
      return;
    }

    setIsSubmittingMember(true);
    try {
      await apiClient.addMember(caseId, {
        email: memberEmail.trim(),
        access_role: memberRole,
      });
      setIsAddMemberOpen(false);
      setMemberEmail('');
      setMemberRole('CONTRIBUTOR');
      fetchCaseDetails();
    } catch (err: any) {
      setMemberError(err.message || 'Failed to add member to case.');
    } finally {
      setIsSubmittingMember(false);
    }
  };

  const handleRemoveMember = async (targetUserId: string, userName: string) => {
    if (!confirm(`Are you sure you want to revoke case access for ${userName}?`)) return;
    try {
      await apiClient.removeMember(caseId, targetUserId);
      fetchCaseDetails();
    } catch (err: any) {
      alert(`Removal failed: ${err.message}`);
    }
  };

  if (isLoading) {
    return (
      <div style={styles.loadingContainer}>
        <div>Verifying case authorization and loading records...</div>
      </div>
    );
  }

  if (errorMsg || !caseData) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorIcon}>⚠</div>
        <div style={styles.errorTitle}>Access Denied or Case Not Found</div>
        <div style={styles.errorText}>
          {errorMsg || 'You are not authorized to view the requested forensic case.'}
        </div>
        <button onClick={onBack} style={styles.backBtn}>
          ← RETURN TO CASES
        </button>
      </div>
    );
  }

  const isLeadOrAdmin =
    user?.role === 'ADMIN' ||
    caseData.current_user_role === 'LEAD' ||
    caseData.current_user_role === 'ADMIN';

  return (
    <div style={styles.container}>
      {/* Top Navigation & Status Bar */}
      <div style={styles.topBar}>
        <button onClick={onBack} style={styles.backBtn}>
          ← RETURN TO CASES
        </button>

        <div style={styles.statusDropdownContainer}>
          <span style={styles.statusLabel}>CASE STATUS:</span>
          {isLeadOrAdmin ? (
            <select
              value={caseData.status}
              disabled={isUpdatingStatus}
              onChange={(e) => handleStatusChange(e.target.value as CaseStatus)}
              style={{
                ...styles.statusSelect,
                ...getStatusColor(caseData.status),
              }}
            >
              <option value="OPEN">OPEN</option>
              <option value="IN_PROGRESS">IN_PROGRESS</option>
              <option value="CLOSED">CLOSED</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          ) : (
            <span style={{ ...styles.statusBadge, ...getStatusColor(caseData.status) }}>
              {caseData.status}
            </span>
          )}
        </div>
      </div>

      {/* Case Header Card */}
      <div style={styles.caseHeaderCard}>
        <div style={styles.caseMetaRow}>
          <span style={styles.caseNumber}>{caseData.case_number}</span>
          <span style={styles.roleChip}>YOUR ROLE: {caseData.current_user_role || 'MEMBER'}</span>
        </div>
        <h1 style={styles.caseTitle}>{caseData.title}</h1>
        {caseData.description && <p style={styles.caseDesc}>{caseData.description}</p>}

        <div style={styles.metaGrid}>
          <div style={styles.metaItem}>
            <span style={styles.metaLabel}>CREATED:</span>
            <span style={styles.metaValue}>{new Date(caseData.created_at).toLocaleString()}</span>
          </div>
          <div style={styles.metaItem}>
            <span style={styles.metaLabel}>LAST UPDATED:</span>
            <span style={styles.metaValue}>{new Date(caseData.updated_at).toLocaleString()}</span>
          </div>
          {caseData.closed_at && (
            <div style={styles.metaItem}>
              <span style={styles.metaLabel}>CLOSED:</span>
              <span style={styles.metaValue}>{new Date(caseData.closed_at).toLocaleString()}</span>
            </div>
          )}
        </div>
      </div>

      {/* Case Sub-Navigation Tab Bar */}
      <div style={styles.subTabBar}>
        <button
          onClick={() => setActiveSubTab('evidence')}
          style={{
            ...styles.subTabBtn,
            ...(activeSubTab === 'evidence' ? styles.subTabBtnActive : {}),
          }}
        >
          📦 Evidence Files (Phase 3)
        </button>

        <button
          onClick={() => setActiveSubTab('team')}
          style={{
            ...styles.subTabBtn,
            ...(activeSubTab === 'team' ? styles.subTabBtnActive : {}),
          }}
        >
          👥 Authorized Personnel ({caseData.members?.length || 0})
        </button>

        <button
          onClick={() => setActiveSubTab('pipeline')}
          style={{
            ...styles.subTabBtn,
            ...(activeSubTab === 'pipeline' ? styles.subTabBtnActive : {}),
          }}
        >
          🔬 Investigation Pipeline (Phases 4-6)
        </button>
      </div>

      {/* Tab 1: Evidence Ingestion (Phase 3 Core Feature) */}
      {activeSubTab === 'evidence' && (
        <EvidenceSection
          caseId={caseId}
          caseNumber={caseData.case_number}
          currentUserCaseRole={caseData.current_user_role}
        />
      )}

      {/* Grid for Team or Pipeline views */}
      {activeSubTab !== 'evidence' && (
        <div style={styles.mainGrid}>
          {activeSubTab === 'team' && (
            <div style={styles.sectionCard}>
              <div style={styles.sectionHeader}>
                <div>
                  <h2 style={styles.sectionTitle}>Authorized Members</h2>
                  <div style={styles.sectionSubtitle}>
                    Personnel with cryptographically verified case-scoping access
                  </div>
                </div>
            {isLeadOrAdmin && (
              <button onClick={() => setIsAddMemberOpen(true)} style={styles.addMemberBtn}>
                + ADD MEMBER
              </button>
            )}
          </div>

          <table style={styles.memberTable}>
            <thead>
              <tr style={styles.memberHeaderRow}>
                <th style={styles.mTh}>INVESTIGATOR</th>
                <th style={styles.mTh}>ACCESS ROLE</th>
                <th style={styles.mTh}>ASSIGNED</th>
                {isLeadOrAdmin && <th style={styles.mThRight}>ACTION</th>}
              </tr>
            </thead>
            <tbody>
              {caseData.members?.map((m) => (
                <tr key={m.id} style={styles.memberRow}>
                  <td style={styles.mTd}>
                    <div style={styles.mName}>{m.user_name}</div>
                    <div style={styles.mEmail}>{m.user_email}</div>
                  </td>
                  <td style={styles.mTd}>
                    <span style={styles.accessBadge}>{m.access_role}</span>
                  </td>
                  <td style={styles.mTdDate}>
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  {isLeadOrAdmin && (
                    <td style={styles.mTdRight}>
                      {m.access_role !== 'LEAD' && (
                        <button
                          onClick={() => handleRemoveMember(m.user_id, m.user_name)}
                          style={styles.removeBtn}
                          title="Revoke Case Access"
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Right Column: Case Investigation Pipeline Placeholders */}
      {activeSubTab === 'pipeline' && (
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <div>
              <h2 style={styles.sectionTitle}>Investigation Pipeline Modules</h2>
              <div style={styles.sectionSubtitle}>
                Artifact processing & analytical capabilities scoped to {caseData.case_number}
              </div>
            </div>
          </div>

          <div style={styles.pipelineGrid}>
            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>📦</span>
                <span style={styles.pipelineName}>Evidence Ingestion</span>
                <span style={styles.phaseTag}>PHASE 3</span>
              </div>
              <p style={styles.pipelineDesc}>
                UFDR ZIP ingestion, streaming decompression, and SHA-256 verification.
              </p>
            </div>

            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>🔎</span>
                <span style={styles.pipelineName}>Search Subsystem</span>
                <span style={styles.phaseTag}>PHASE 4</span>
              </div>
              <p style={styles.pipelineDesc}>
                Exact identifier matching and Sentence-BERT semantic vector search.
              </p>
            </div>

            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>⏱</span>
                <span style={styles.pipelineName}>Timeline Analytics</span>
                <span style={styles.phaseTag}>PHASE 4</span>
              </div>
              <p style={styles.pipelineDesc}>
                Cross-artifact chronological alignment of calls, messages, and locations.
              </p>
            </div>

            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>🕸</span>
                <span style={styles.pipelineName}>Communication Graph</span>
                <span style={styles.phaseTag}>PHASE 5</span>
              </div>
              <p style={styles.pipelineDesc}>
                Multi-entity interaction networks, centrality, and community detection.
              </p>
            </div>

            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>⚡</span>
                <span style={styles.pipelineName}>Anomaly Detection</span>
                <span style={styles.phaseTag}>PHASE 5</span>
              </div>
              <p style={styles.pipelineDesc}>
                Scikit-Learn Isolation Forest outlier scoring on communication patterns.
              </p>
            </div>

            <div style={styles.pipelineItem}>
              <div style={styles.pipelineItemHeader}>
                <span style={styles.pipelineIcon}>📄</span>
                <span style={styles.pipelineName}>Forensic Reporting</span>
                <span style={styles.phaseTag}>PHASE 6</span>
              </div>
              <p style={styles.pipelineDesc}>
                Evidence-grounded RAG assistance and court-ready PDF/HTML report generation.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )}

      {/* Add Member Modal */}
      {isAddMemberOpen && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={styles.modalHeader}>
              <h3 style={styles.modalTitle}>Assign Investigator to Case</h3>
              <button onClick={() => setIsAddMemberOpen(false)} style={styles.modalClose}>
                ✕
              </button>
            </div>

            {memberError && (
              <div style={styles.modalError}>
                <span>⚠ {memberError}</span>
              </div>
            )}

            <form onSubmit={handleAddMember} style={styles.modalForm}>
              <div style={styles.fieldGroup}>
                <label style={styles.label}>INVESTIGATOR EMAIL *</label>
                <input
                  type="email"
                  placeholder="e.g. analyst@ufdr.org"
                  value={memberEmail}
                  onChange={(e) => setMemberEmail(e.target.value)}
                  required
                  style={styles.modalInput}
                />
              </div>

              <div style={styles.fieldGroup}>
                <label style={styles.label}>CASE ACCESS ROLE *</label>
                <select
                  value={memberRole}
                  onChange={(e) => setMemberRole(e.target.value as CaseAccessRole)}
                  style={styles.modalSelect}
                >
                  <option value="CONTRIBUTOR">CONTRIBUTOR (Read / Write Evidence)</option>
                  <option value="ANALYST">ANALYST (Read / Run Analytics)</option>
                  <option value="VIEWER">VIEWER (Read Only)</option>
                  <option value="LEAD">LEAD (Full Case & Membership Admin)</option>
                </select>
              </div>

              <div style={styles.modalActions}>
                <button
                  type="button"
                  onClick={() => setIsAddMemberOpen(false)}
                  style={styles.cancelBtn}
                >
                  CANCEL
                </button>
                <button type="submit" disabled={isSubmittingMember} style={styles.submitBtn}>
                  {isSubmittingMember ? 'ASSIGNING...' : 'AUTHORIZE MEMBER'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

function getStatusColor(status: CaseStatus): React.CSSProperties {
  switch (status) {
    case 'OPEN':
      return { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-green)', borderColor: 'rgba(16, 185, 129, 0.4)' };
    case 'IN_PROGRESS':
      return { backgroundColor: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', borderColor: 'rgba(56, 189, 248, 0.4)' };
    case 'CLOSED':
      return { backgroundColor: 'rgba(100, 116, 139, 0.15)', color: 'var(--text-muted)', borderColor: 'rgba(100, 116, 139, 0.4)' };
    case 'ARCHIVED':
      return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)', borderColor: 'rgba(245, 158, 11, 0.4)' };
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
  topBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  backBtn: {
    backgroundColor: 'var(--bg-card)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-subtle)',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    padding: '6px 12px',
    borderRadius: '4px',
  },
  statusDropdownContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  statusLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  statusSelect: {
    border: '1px solid',
    borderRadius: '4px',
    padding: '4px 10px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    outline: 'none',
    cursor: 'pointer',
  },
  statusBadge: {
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
  },
  caseHeaderCard: {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  caseMetaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  caseNumber: {
    fontSize: '13px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
  },
  roleChip: {
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  caseTitle: {
    fontSize: '22px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    letterSpacing: '-0.3px',
  },
  caseDesc: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
  },
  metaGrid: {
    display: 'flex',
    gap: '24px',
    borderTop: '1px solid var(--border-subtle)',
    paddingTop: '12px',
  },
  metaItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  metaLabel: {
    fontSize: '9px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  metaValue: {
    fontSize: '11px',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
  },
  mainGrid: {
    display: 'grid',
    gridTemplateColumns: '1.2fr 1fr',
    gap: '20px',
  },
  sectionCard: {
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '12px',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  sectionSubtitle: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  addMemberBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    fontSize: '10px',
    fontWeight: 700,
    padding: '5px 10px',
    borderRadius: '4px',
    fontFamily: 'var(--font-mono)',
  },
  memberTable: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  memberHeaderRow: {
    backgroundColor: 'var(--bg-card)',
    borderBottom: '1px solid var(--border-subtle)',
  },
  mTh: {
    padding: '8px 12px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    textAlign: 'left',
  },
  mThRight: {
    padding: '8px 12px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    textAlign: 'right',
  },
  memberRow: {
    borderBottom: '1px solid var(--border-subtle)',
  },
  mTd: {
    padding: '10px 12px',
  },
  mName: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  mEmail: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  accessBadge: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 600,
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    padding: '2px 6px',
    borderRadius: '3px',
  },
  mTdDate: {
    padding: '10px 12px',
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  mTdRight: {
    padding: '10px 12px',
    textAlign: 'right',
  },
  removeBtn: {
    fontSize: '11px',
    color: 'var(--accent-rose)',
    padding: '2px 6px',
  },
  pipelineGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px',
  },
  pipelineItem: {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  pipelineItemHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  pipelineIcon: {
    fontSize: '14px',
  },
  pipelineName: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    flex: 1,
  },
  phaseTag: {
    fontSize: '9px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    color: 'var(--accent-amber)',
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    padding: '1px 5px',
    borderRadius: '3px',
  },
  pipelineDesc: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    lineHeight: 1.4,
  },
  loadingContainer: {
    padding: '60px',
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
  errorContainer: {
    padding: '60px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
    textAlign: 'center',
  },
  errorIcon: {
    fontSize: '36px',
    color: 'var(--accent-rose)',
  },
  errorTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  errorText: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    maxWidth: '400px',
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
    maxWidth: '460px',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '12px',
  },
  modalTitle: {
    fontSize: '15px',
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
  modalSelect: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '8px 10px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    outline: 'none',
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
  subTabBar: {
    display: 'flex',
    gap: '8px',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '10px',
    marginBottom: '8px',
  },
  subTabBtn: {
    backgroundColor: 'var(--bg-card)',
    color: 'var(--text-muted)',
    border: '1px solid var(--border-subtle)',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  subTabBtnActive: {
    backgroundColor: 'rgba(56, 189, 248, 0.12)',
    color: 'var(--accent-cyan)',
    borderColor: 'var(--accent-cyan)',
  },
  phaseActiveTag: {
    fontSize: '9px',
    fontFamily: 'var(--font-mono)',
    padding: '2px 6px',
    borderRadius: '3px',
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    color: 'var(--accent-green)',
    border: '1px solid rgba(16, 185, 129, 0.4)',
    fontWeight: 700,
  },
};
