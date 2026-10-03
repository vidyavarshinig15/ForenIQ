import React, { useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';
import type { Evidence, EvidenceStatus } from '../types/evidence';
import { EvidenceDetailsModal } from './EvidenceDetailsModal';
import { EvidenceUploadModal } from './EvidenceUploadModal';

interface EvidenceSectionProps {
  caseId: string;
  caseNumber: string;
  currentUserCaseRole?: string | null;
}

export const EvidenceSection: React.FC<EvidenceSectionProps> = ({
  caseId,
  caseNumber,
  currentUserCaseRole,
}) => {
  const { user } = useAuth();
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState<boolean>(false);

  const canUpload =
    user?.role === 'ADMIN' ||
    ((user?.role === 'INVESTIGATOR' || currentUserCaseRole === 'LEAD' || currentUserCaseRole === 'CONTRIBUTOR') &&
      currentUserCaseRole !== 'VIEWER');

  const canManage =
    user?.role === 'ADMIN' || currentUserCaseRole === 'LEAD';

  const fetchEvidence = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await apiClient.listEvidence(caseId);
      setEvidenceList(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load case evidence.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvidence();
  }, [caseId]);

  const handleOpenDetails = (ev: Evidence) => {
    setSelectedEvidence(ev);
    setIsDetailsModalOpen(true);
  };

  const handleDirectDownload = async (e: React.MouseEvent, ev: Evidence) => {
    e.stopPropagation();
    try {
      await apiClient.downloadEvidence(caseId, ev.id, ev.original_filename);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const filteredEvidence = evidenceList.filter((ev) => {
    const matchesSearch =
      ev.original_filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (ev.sha256_hash && ev.sha256_hash.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (ev.uploader_name && ev.uploader_name.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus = statusFilter === 'ALL' || ev.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div style={styles.container}>
      {/* Evidence Sub-Header Controls */}
      <div style={styles.topControls}>
        <div style={styles.searchAndFilter}>
          <div style={styles.searchBox}>
            <span style={styles.searchIcon}>🔍</span>
            <input
              type="text"
              placeholder="Filter by filename, SHA-256 hash, or uploader..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={styles.searchInput}
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={styles.statusSelect}
          >
            <option value="ALL">ALL STATUSES ({evidenceList.length})</option>
            <option value="VALID">VALID</option>
            <option value="QUARANTINED">QUARANTINED</option>
            <option value="FAILED">FAILED</option>
          </select>
        </div>

        <div style={styles.actionsBar}>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            disabled={!canUpload}
            style={{
              ...styles.uploadBtn,
              opacity: canUpload ? 1 : 0.5,
              cursor: canUpload ? 'pointer' : 'not-allowed',
            }}
            title={
              canUpload
                ? 'Upload new forensic archive to case'
                : 'Upload restricted: Requires CONTRIBUTOR or LEAD case access'
            }
          >
            + UPLOAD EVIDENCE ARCHIVE
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={styles.errorBox}>
          <span>⚠ {errorMsg}</span>
          <button onClick={fetchEvidence} style={styles.retryBtn}>
            RETRY
          </button>
        </div>
      )}

      {/* Evidence Records Table */}
      <div style={styles.tableCard}>
        {isLoading ? (
          <div style={styles.emptyState}>
            <div style={styles.spinnerIcon}>⌛</div>
            <div>Verifying case authorization and querying evidence records...</div>
          </div>
        ) : filteredEvidence.length === 0 ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}>📦</div>
            <div style={styles.emptyTitle}>No Forensic Evidence Found</div>
            <div style={styles.emptySub}>
              {searchTerm || statusFilter !== 'ALL'
                ? 'No evidence items matched your search criteria.'
                : `No evidence archives have been ingested into ${caseNumber} yet.`}
            </div>
            {canUpload && !searchTerm && statusFilter === 'ALL' && (
              <button
                onClick={() => setIsUploadModalOpen(true)}
                style={styles.emptyUploadBtn}
              >
                INGEST FIRST EVIDENCE ARCHIVE (.UFDR / .ZIP)
              </button>
            )}
          </div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr style={styles.headerRow}>
                <th style={styles.th}>ORIGINAL EVIDENCE FILE</th>
                <th style={styles.th}>STATUS</th>
                <th style={styles.th}>INTEGRITY</th>
                <th style={styles.th}>SIZE</th>
                <th style={styles.th}>CRYPTOGRAPHIC SHA-256</th>
                <th style={styles.th}>EXAMINER</th>
                <th style={styles.th}>INGESTED</th>
                <th style={styles.thRight}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvidence.map((ev) => (
                <tr
                  key={ev.id}
                  style={styles.row}
                  onClick={() => handleOpenDetails(ev)}
                >
                  <td style={styles.td}>
                    <div style={styles.fileTitleRow}>
                      <span style={styles.fileIcon}>
                        {ev.file_extension.toLowerCase() === '.ufdr' ? '📱' : '🗜'}
                      </span>
                      <div>
                        <div style={styles.fileName}>{ev.original_filename}</div>
                        <div style={styles.formatSub}>
                          {ev.file_extension.toUpperCase()} ARCHIVE
                        </div>
                      </div>
                    </div>
                  </td>

                  <td style={styles.td}>
                    <span style={{ ...styles.badge, ...getStatusBadgeStyle(ev.status) }}>
                      {ev.status}
                    </span>
                  </td>

                  <td style={styles.td}>
                    <span style={{ ...styles.badge, ...getIntegrityBadgeStyle(ev.integrity_status) }}>
                      ● {ev.integrity_status}
                    </span>
                  </td>

                  <td style={styles.tdMono}>{formatBytes(ev.file_size)}</td>


                  <td style={styles.tdMono}>
                    <div style={styles.hashContainer}>
                      <span style={styles.hashText}>
                        {ev.sha256_hash ? `${ev.sha256_hash.slice(0, 14)}...` : 'N/A'}
                      </span>
                    </div>
                  </td>

                  <td style={styles.td}>
                    <div style={styles.examinerName}>{ev.uploader_name || 'Investigator'}</div>
                    <div style={styles.examinerEmail}>{ev.uploader_email || ''}</div>
                  </td>

                  <td style={styles.tdDate}>
                    {new Date(ev.uploaded_at).toLocaleDateString()}
                  </td>

                  <td style={styles.tdRight} onClick={(e) => e.stopPropagation()}>
                    <div style={styles.actionGroup}>
                      <button
                        onClick={() => handleOpenDetails(ev)}
                        style={styles.actionBtn}
                        title="View Full Forensic Metadata"
                      >
                        Details
                      </button>
                      <button
                        onClick={(e) => handleDirectDownload(e, ev)}
                        disabled={ev.status === 'FAILED'}
                        style={styles.downloadActionBtn}
                        title="Download Original Archive"
                      >
                        Download
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Evidence Upload Modal */}
      <EvidenceUploadModal
        caseId={caseId}
        caseNumber={caseNumber}
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={fetchEvidence}
      />

      {/* Evidence Details Modal */}
      <EvidenceDetailsModal
        caseId={caseId}
        evidence={selectedEvidence}
        isOpen={isDetailsModalOpen}
        canManage={canManage}
        onClose={() => {
          setIsDetailsModalOpen(false);
          setSelectedEvidence(null);
        }}
        onStatusUpdated={fetchEvidence}
      />
    </div>
  );
};

function getStatusBadgeStyle(status: EvidenceStatus): React.CSSProperties {
  switch (status) {
    case 'VALID':
      return {
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        color: 'var(--accent-green)',
        borderColor: 'rgba(16, 185, 129, 0.4)',
      };
    case 'UPLOADED':
    case 'VALIDATING':
    case 'UPLOADING':
      return {
        backgroundColor: 'rgba(56, 189, 248, 0.15)',
        color: 'var(--accent-cyan)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
      };
    case 'QUARANTINED':
      return {
        backgroundColor: 'rgba(245, 158, 11, 0.15)',
        color: 'var(--accent-amber)',
        borderColor: 'rgba(245, 158, 11, 0.4)',
      };
    case 'PROCESSED':
      return {
        backgroundColor: 'rgba(56, 189, 248, 0.15)',
        color: 'var(--accent-cyan)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
      };
    case 'FAILED':
    case 'INVALID':
      return {
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        color: 'var(--accent-red)',
        borderColor: 'rgba(239, 68, 68, 0.4)',
      };
    default:
      return {
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        color: 'var(--text-secondary)',
        borderColor: 'var(--border-subtle)',
      };
  }
}

function getIntegrityBadgeStyle(status?: string): React.CSSProperties {
  switch (status) {
    case 'VALID':
      return {
        backgroundColor: 'rgba(16, 185, 129, 0.12)',
        color: 'var(--accent-green)',
        borderColor: 'rgba(16, 185, 129, 0.4)',
      };
    case 'MISMATCH':
      return {
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        color: 'var(--accent-red)',
        borderColor: 'rgba(239, 68, 68, 0.5)',
      };
    case 'MISSING':
      return {
        backgroundColor: 'rgba(245, 158, 11, 0.15)',
        color: 'var(--accent-amber)',
        borderColor: 'rgba(245, 158, 11, 0.5)',
      };
    case 'UNKNOWN':
    default:
      return {
        backgroundColor: 'rgba(148, 163, 184, 0.1)',
        color: 'var(--text-muted)',
        borderColor: 'rgba(148, 163, 184, 0.3)',
      };
  }
}

const styles: Record<string, React.CSSProperties> = {

  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    height: '100%',
  },
  topControls: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '16px',
    flexWrap: 'wrap',
  },
  searchAndFilter: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flex: 1,
    maxWidth: '650px',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '0 12px',
    flex: 1,
    height: '36px',
  },
  searchIcon: {
    fontSize: '12px',
    marginRight: '8px',
    opacity: 0.6,
  },
  searchInput: {
    background: 'none',
    border: 'none',
    color: 'var(--text-primary)',
    fontSize: '12px',
    outline: 'none',
    width: '100%',
    fontFamily: 'var(--font-sans)',
  },
  statusSelect: {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    color: 'var(--text-secondary)',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    padding: '0 12px',
    height: '36px',
    outline: 'none',
    cursor: 'pointer',
  },
  actionsBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  uploadBtn: {
    backgroundColor: 'var(--accent-cyan)',
    color: '#000000',
    border: 'none',
    padding: '0 16px',
    height: '36px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s ease',
  },
  errorBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid rgba(239, 68, 68, 0.4)',
    borderRadius: '4px',
    padding: '10px 14px',
    color: 'var(--accent-red)',
    fontSize: '12px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  retryBtn: {
    background: 'none',
    border: '1px solid var(--accent-red)',
    color: 'var(--accent-red)',
    borderRadius: '3px',
    padding: '2px 8px',
    fontSize: '10px',
    cursor: 'pointer',
  },
  tableCard: {
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    overflow: 'hidden',
  },
  emptyState: {
    padding: '48px 24px',
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '12px',
  },
  emptyIcon: {
    fontSize: '40px',
    opacity: 0.5,
  },
  spinnerIcon: {
    fontSize: '28px',
  },
  emptyTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  emptySub: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    maxWidth: '400px',
  },
  emptyUploadBtn: {
    marginTop: '8px',
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--accent-cyan)',
    color: 'var(--accent-cyan)',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
  },
  headerRow: {
    backgroundColor: 'var(--bg-card)',
    borderBottom: '1px solid var(--border-subtle)',
  },
  th: {
    padding: '12px 16px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
  },
  thRight: {
    padding: '12px 16px',
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
    textAlign: 'right',
  },
  row: {
    borderBottom: '1px solid var(--border-subtle)',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
  },
  td: {
    padding: '12px 16px',
    fontSize: '12px',
    color: 'var(--text-primary)',
    verticalAlign: 'middle',
  },
  tdMono: {
    padding: '12px 16px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-secondary)',
    verticalAlign: 'middle',
  },
  tdDate: {
    padding: '12px 16px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    verticalAlign: 'middle',
  },
  tdRight: {
    padding: '12px 16px',
    textAlign: 'right',
    verticalAlign: 'middle',
  },
  fileTitleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  fileIcon: {
    fontSize: '18px',
  },
  fileName: {
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  formatSub: {
    fontSize: '9px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  badge: {
    padding: '3px 8px',
    borderRadius: '4px',
    border: '1px solid',
    fontSize: '10px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
  },
  hashContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  hashText: {
    color: 'var(--accent-cyan)',
    backgroundColor: 'var(--bg-primary)',
    padding: '2px 6px',
    borderRadius: '3px',
    border: '1px solid rgba(56, 189, 248, 0.2)',
  },
  examinerName: {
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  examinerEmail: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  actionGroup: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '8px',
  },
  actionBtn: {
    backgroundColor: 'var(--bg-card)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-subtle)',
    padding: '4px 10px',
    borderRadius: '3px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
  },
  downloadActionBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    padding: '4px 10px',
    borderRadius: '3px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
  },
};
