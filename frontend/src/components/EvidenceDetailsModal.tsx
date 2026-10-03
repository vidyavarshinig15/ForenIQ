import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/api/client';
import { CanonicalEvidenceExplorer } from './CanonicalEvidenceExplorer';
import type {
  ArtifactType,
  CustodyChainVerificationResult,
  Evidence,
  EvidenceCustodyEvent,
  EvidenceStatus,
  IntegrityStatus,
  IntegrityVerificationResult,
  JobPriority,
  JobStatus,
  ProcessingJob,
  RawArtifact,
} from '../types/evidence';

interface EvidenceDetailsModalProps {
  caseId: string;
  evidence: Evidence | null;
  isOpen: boolean;
  canManage: boolean;
  onClose: () => void;
  onStatusUpdated: () => void;
}

type TabType = 'METADATA' | 'CUSTODY' | 'PROCESSING' | 'ARTIFACTS' | 'CANONICAL';

export const EvidenceDetailsModal: React.FC<EvidenceDetailsModalProps> = ({
  caseId,
  evidence,
  isOpen,
  canManage,
  onClose,
  onStatusUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('METADATA');
  const [copiedHash, setCopiedHash] = useState<boolean>(false);
  const [copiedEventHash, setCopiedEventHash] = useState<string | null>(null);

  // Integrity verification state
  const [isVerifyingIntegrity, setIsVerifyingIntegrity] = useState<boolean>(false);
  const [integrityResult, setIntegrityResult] = useState<IntegrityVerificationResult | null>(null);

  // Custody history state
  const [custodyEvents, setCustodyEvents] = useState<EvidenceCustodyEvent[]>([]);
  const [isLoadingCustody, setIsLoadingCustody] = useState<boolean>(false);
  const [isVerifyingChain, setIsVerifyingChain] = useState<boolean>(false);
  const [chainResult, setChainResult] = useState<CustodyChainVerificationResult | null>(null);

  // Action states
  const [isQuarantining, setIsQuarantining] = useState<boolean>(false);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Phase 5 & 6 Processing Pipeline states
  const [activeJob, setActiveJob] = useState<ProcessingJob | null>(null);
  const [allJobs, setAllJobs] = useState<ProcessingJob[]>([]);
  const [selectedPriority, setSelectedPriority] = useState<JobPriority>('NORMAL');
  const [isTriggeringParse, setIsTriggeringParse] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [parseError, setParseError] = useState<string | null>(null);

  // Phase 7 Normalization states
  const [canonicalTotal, setCanonicalTotal] = useState<number>(0);
  const [isTriggeringNormalize, setIsTriggeringNormalize] = useState<boolean>(false);
  const [normalizeError, setNormalizeError] = useState<string | null>(null);

  // Phase 5 Raw Artifact Explorer states
  const [artifacts, setArtifacts] = useState<RawArtifact[]>([]);
  const [artifactsTotal, setArtifactsTotal] = useState<number>(0);
  const [artifactsPage, setArtifactsPage] = useState<number>(1);
  const [artifactsTotalPages, setArtifactsTotalPages] = useState<number>(1);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState<boolean>(false);
  const [inspectingArtifact, setInspectingArtifact] = useState<RawArtifact | null>(null);
  const [copiedRawJson, setCopiedRawJson] = useState<boolean>(false);

  const loadCanonicalCount = async () => {
    if (!evidence) return;
    try {
      const res = await apiClient.listCanonicalRecords(caseId, evidence.id, { page: 1, pageSize: 1 });
      setCanonicalTotal(res.total || 0);
    } catch {
      setCanonicalTotal(0);
    }
  };

  useEffect(() => {
    if (isOpen && evidence) {
      setIntegrityResult(null);
      setChainResult(null);
      setActionError(null);
      setParseError(null);
      setNormalizeError(null);
      setInspectingArtifact(null);
      loadCustodyHistory();
      loadProcessingJobs();
      loadRawArtifacts('ALL', 1);
      loadCanonicalCount();
    }
  }, [isOpen, evidence?.id]);

  // Polling active processing job
  useEffect(() => {
    if (!isOpen || !evidence || !activeJob) return;
    const isJobActive = ['QUEUED', 'STARTING', 'RUNNING', 'CANCEL_REQUESTED', 'RETRYING'].includes(activeJob.status);
    if (!isJobActive) return;

    const interval = setInterval(async () => {
      try {
        const updated = await apiClient.getProcessingJob(caseId, activeJob.id);
        setActiveJob(updated);
        // Refresh job history simultaneously
        try {
          const jobs = await apiClient.listProcessingJobs(caseId, evidence.id);
          setAllJobs(jobs || []);
        } catch {}
        if (updated.status === 'COMPLETED' || updated.status === 'FAILED' || updated.status === 'CANCELLED' || updated.status === 'PARTIAL') {
          clearInterval(interval);
          onStatusUpdated();
          await loadCustodyHistory();
          await loadRawArtifacts(selectedCategory, artifactsPage);
          await loadCanonicalCount();
        }
      } catch (err) {
        console.error('Error polling processing job status:', err);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [isOpen, evidence?.id, activeJob?.id, activeJob?.status, selectedCategory, artifactsPage]);

  if (!isOpen || !evidence) return null;

  const loadCustodyHistory = async () => {
    setIsLoadingCustody(true);
    try {
      const events = await apiClient.getCustodyHistory(caseId, evidence.id);
      setCustodyEvents(events);
    } catch (err: any) {
      console.error('Failed to load custody history:', err);
    } finally {
      setIsLoadingCustody(false);
    }
  };

  const loadProcessingJobs = async () => {
    try {
      const jobs = await apiClient.listProcessingJobs(caseId, evidence.id);
      setAllJobs(jobs || []);
      if (jobs && jobs.length > 0) {
        setActiveJob(jobs[0]);
      } else {
        setActiveJob(null);
      }
    } catch (err: any) {
      console.error('Failed to load processing jobs:', err);
    }
  };

  const handleTriggerParse = async (priority: JobPriority = selectedPriority) => {
    setIsTriggeringParse(true);
    setParseError(null);
    try {
      const job = await apiClient.triggerParsing(caseId, evidence.id, priority);
      setActiveJob(job);
      await loadProcessingJobs();
      setActiveTab('PROCESSING');
      onStatusUpdated();
    } catch (err: any) {
      setParseError(err.message || 'Failed to trigger evidence parsing.');
    } finally {
      setIsTriggeringParse(false);
    }
  };

  const handleTriggerNormalize = async (priority: JobPriority = selectedPriority) => {
    setIsTriggeringNormalize(true);
    setNormalizeError(null);
    try {
      const job = await apiClient.normalizeEvidence(caseId, evidence.id, priority);
      setActiveJob(job);
      await loadProcessingJobs();
      setActiveTab('PROCESSING');
      onStatusUpdated();
    } catch (err: any) {
      setNormalizeError(err?.message || 'Failed to trigger evidence normalization.');
    } finally {
      setIsTriggeringNormalize(false);
    }
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    setIsCancelling(true);
    setParseError(null);
    try {
      const updated = await apiClient.cancelProcessingJob(caseId, activeJob.id);
      setActiveJob(updated);
      await loadProcessingJobs();
    } catch (err: any) {
      setParseError(err.message || 'Failed to request cancellation.');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryJob = async () => {
    if (!activeJob) return;
    setIsRetrying(true);
    setParseError(null);
    try {
      const retried = await apiClient.retryProcessingJob(caseId, activeJob.id);
      setActiveJob(retried);
      await loadProcessingJobs();
      onStatusUpdated();
    } catch (err: any) {
      setParseError(err.message || 'Failed to retry job.');
    } finally {
      setIsRetrying(false);
    }
  };

  const loadRawArtifacts = async (cat: string = selectedCategory, page: number = artifactsPage) => {
    setIsLoadingArtifacts(true);
    try {
      const res = await apiClient.listRawArtifacts(caseId, evidence.id, cat, page, 20);
      setArtifacts(res.items);
      setArtifactsTotal(res.total);
      setArtifactsTotalPages(res.total_pages);
    } catch (err: any) {
      console.error('Failed to load raw artifacts:', err);
    } finally {
      setIsLoadingArtifacts(false);
    }
  };

  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat);
    setArtifactsPage(1);
    loadRawArtifacts(cat, 1);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > artifactsTotalPages) return;
    setArtifactsPage(newPage);
    loadRawArtifacts(selectedCategory, newPage);
  };

  const handleCopyHash = (text: string, isEvent: boolean = false) => {
    navigator.clipboard.writeText(text);
    if (isEvent) {
      setCopiedEventHash(text);
      setTimeout(() => setCopiedEventHash(null), 2000);
    } else {
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  const handleCopyRawJson = (jsonObj: any) => {
    navigator.clipboard.writeText(JSON.stringify(jsonObj, null, 2));
    setCopiedRawJson(true);
    setTimeout(() => setCopiedRawJson(false), 2000);
  };

  const handleVerifyIntegrity = async () => {
    setIsVerifyingIntegrity(true);
    setActionError(null);
    try {
      const res = await apiClient.verifyIntegrity(caseId, evidence.id);
      setIntegrityResult(res);
      onStatusUpdated();
      await loadCustodyHistory();
    } catch (err: any) {
      setActionError(err.message || 'Integrity verification failed.');
    } finally {
      setIsVerifyingIntegrity(false);
    }
  };

  const handleVerifyChain = async () => {
    setIsVerifyingChain(true);
    setActionError(null);
    try {
      const res = await apiClient.verifyCustodyChain(caseId, evidence.id);
      setChainResult(res);
    } catch (err: any) {
      setActionError(err.message || 'Chain verification failed.');
    } finally {
      setIsVerifyingChain(false);
    }
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    setActionError(null);
    try {
      await apiClient.downloadEvidence(caseId, evidence.id, evidence.original_filename);
      await loadCustodyHistory();
    } catch (err: any) {
      setActionError(err.message || 'Failed to download evidence file.');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleQuarantine = async () => {
    if (
      !confirm(
        `Are you sure you want to quarantine '${evidence.original_filename}'?\n\nForensic Preservation Notice: The original file will NOT be deleted from disk, but its status will be set to QUARANTINED and access restricted.`
      )
    ) {
      return;
    }

    setIsQuarantining(true);
    setActionError(null);
    try {
      await apiClient.quarantineEvidence(caseId, evidence.id);
      onStatusUpdated();
      await loadCustodyHistory();
    } catch (err: any) {
      setActionError(err.message || 'Failed to quarantine evidence.');
    } finally {
      setIsQuarantining(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const renderArtifactPreview = (art: RawArtifact) => {
    const raw = art.raw_data || {};
    switch (art.artifact_type) {
      case 'CALL':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>
              {raw.caller || 'Unknown'} → {raw.receiver || raw.phone_number || 'Unknown'}
            </span>
            <span style={styles.previewSub}>
              Direction: {raw.direction || 'N/A'} | Duration: {raw.duration ? `${raw.duration}s` : '0s'}
            </span>
          </div>
        );
      case 'MESSAGE':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>
              [{raw.application || 'SMS'}] {raw.sender || 'Unknown'} → {raw.receiver || 'Unknown'}
            </span>
            <span style={styles.previewBody}>"{raw.content || '(no text content)'}"</span>
          </div>
        );
      case 'CONTACT':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>{raw.name || 'Unnamed Contact'}</span>
            <span style={styles.previewSub}>
              Phone: {raw.phone || 'N/A'} | Email: {raw.email || 'N/A'}
            </span>
          </div>
        );
      case 'LOCATION':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>
              Lat: {raw.latitude}, Lon: {raw.longitude}
            </span>
            <span style={styles.previewSub}>
              Source: {raw.source || 'GPS'} | Accuracy: {raw.accuracy || 'N/A'}m
            </span>
          </div>
        );
      case 'BROWSER':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>{raw.title || raw.url || 'Web Visit'}</span>
            <span style={styles.previewSub}>
              URL: {raw.url} | Browser: {raw.browser || 'Unknown'}
            </span>
          </div>
        );
      case 'APPLICATION':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>
              {raw.application || raw.package_name || 'Application'}
            </span>
            <span style={styles.previewSub}>
              Version: {raw.version || '1.0'} | Event: {raw.event_type || 'INSTALLED'}
            </span>
          </div>
        );
      case 'FILESYSTEM':
        return (
          <div style={styles.previewContainer}>
            <span style={styles.previewHighlight}>{raw.filename || raw.path || 'File'}</span>
            <span style={styles.previewSub}>
              Path: {raw.path} | Size: {raw.size ? `${raw.size} bytes` : 'N/A'}
            </span>
          </div>
        );
      default:
        return <span style={styles.previewSub}>Raw record extracted</span>;
    }
  };

  const currentIntegrityStatus = integrityResult?.integrity_status || evidence.integrity_status;

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        {/* Modal Header */}
        <div style={styles.header}>
          <div>
            <div style={styles.badgeRow}>
              <h3 style={styles.title}>Forensic Evidence Custody Record</h3>
              <span style={{ ...styles.statusBadge, ...getStatusStyle(evidence.status) }}>
                {evidence.status}
              </span>
              <span style={{ ...styles.integrityBadge, ...getIntegrityStyle(currentIntegrityStatus) }}>
                ● INTEGRITY: {currentIntegrityStatus}
              </span>
            </div>
            <div style={styles.subtitle}>Evidence ID: {evidence.id}</div>
          </div>

          <div style={styles.headerRight}>
            <button
              onClick={() => handleTriggerParse()}
              disabled={
                isTriggeringParse ||
                evidence.integrity_status === 'MISMATCH' ||
                evidence.status === 'QUARANTINED' ||
                activeJob?.status === 'RUNNING'
              }
              style={{
                ...styles.headerParseBtn,
                ...(evidence.integrity_status === 'MISMATCH' || evidence.status === 'QUARANTINED'
                  ? styles.disabledBtn
                  : {}),
              }}
              title={
                evidence.integrity_status === 'MISMATCH'
                  ? 'Integrity mismatch detected. Parsing blocked.'
                  : 'Trigger asynchronous UFDR parsing engine'
              }
            >
              {isTriggeringParse
                ? 'ENQUEUING...'
                : activeJob?.status === 'RUNNING'
                ? `PARSING (${activeJob.progress}%)`
                : 'PARSE EVIDENCE'}
            </button>

            <button onClick={onClose} style={styles.closeBtn} title="Close Modal">
              ✕
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={styles.tabBar}>
          <button
            onClick={() => setActiveTab('METADATA')}
            style={{
              ...styles.tabBtn,
              ...(activeTab === 'METADATA' ? styles.activeTabBtn : {}),
            }}
          >
            FORENSIC METADATA
          </button>
          <button
            onClick={() => setActiveTab('CUSTODY')}
            style={{
              ...styles.tabBtn,
              ...(activeTab === 'CUSTODY' ? styles.activeTabBtn : {}),
            }}
          >
            CHAIN OF CUSTODY ({custodyEvents.length})
          </button>
          <button
            onClick={() => setActiveTab('PROCESSING')}
            style={{
              ...styles.tabBtn,
              ...(activeTab === 'PROCESSING' ? styles.activeTabBtn : {}),
            }}
          >
            PARSING PIPELINE {activeJob ? `(${activeJob.status})` : ''}
          </button>
          <button
            onClick={() => setActiveTab('ARTIFACTS')}
            style={{
              ...styles.tabBtn,
              ...(activeTab === 'ARTIFACTS' ? styles.activeTabBtn : {}),
            }}
          >
            RAW ARTIFACTS ({artifactsTotal})
          </button>
          <button
            onClick={() => setActiveTab('CANONICAL')}
            style={{
              ...styles.tabBtn,
              ...(activeTab === 'CANONICAL' ? styles.activeTabBtn : {}),
            }}
          >
            CANONICAL EVIDENCE {canonicalTotal > 0 ? `(${canonicalTotal.toLocaleString()})` : ''}
          </button>
        </div>

        {actionError && (
          <div style={styles.errorBox}>
            <span>⚠ {actionError}</span>
          </div>
        )}

        {parseError && (
          <div style={styles.errorBox}>
            <span>⚠ Parse Job Failed: {parseError}</span>
          </div>
        )}

        {normalizeError && (
          <div style={styles.errorBox}>
            <span>⚠ Normalization Job Failed: {normalizeError}</span>
          </div>
        )}

        {/* Verification Result Banner */}
        {integrityResult && (
          <div
            style={{
              ...styles.resultBanner,
              backgroundColor: integrityResult.match
                ? 'rgba(16, 185, 129, 0.1)'
                : 'rgba(239, 68, 68, 0.12)',
              borderColor: integrityResult.match
                ? 'rgba(16, 185, 129, 0.4)'
                : 'rgba(239, 68, 68, 0.4)',
            }}
          >
            <div style={styles.resultBannerHeader}>
              <span
                style={{
                  fontWeight: 700,
                  color: integrityResult.match ? 'var(--accent-green)' : 'var(--accent-red)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                }}
              >
                {integrityResult.match
                  ? '✓ CRYPTOGRAPHIC INTEGRITY CONFIRMED'
                  : '⚠ INTEGRITY MISMATCH DETECTED'}
              </span>
              <span style={styles.resultTimestamp}>
                Verified: {new Date(integrityResult.verified_at).toLocaleTimeString()}
              </span>
            </div>
            <div style={styles.resultDetails}>{integrityResult.details}</div>
            {!integrityResult.match && integrityResult.calculated_hash && (
              <div style={styles.mismatchCompare}>
                <div>
                  <span style={styles.compareLabel}>Recorded Baseline SHA-256:</span>{' '}
                  <code>{integrityResult.stored_hash}</code>
                </div>
                <div>
                  <span style={styles.compareLabel}>Calculated Current SHA-256:</span>{' '}
                  <code style={{ color: 'var(--accent-red)' }}>{integrityResult.calculated_hash}</code>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Chain Verification Result Banner */}
        {chainResult && (
          <div
            style={{
              ...styles.resultBanner,
              backgroundColor:
                chainResult.status === 'VALID'
                  ? 'rgba(16, 185, 129, 0.1)'
                  : 'rgba(239, 68, 68, 0.12)',
              borderColor:
                chainResult.status === 'VALID'
                  ? 'rgba(16, 185, 129, 0.4)'
                  : 'rgba(239, 68, 68, 0.4)',
            }}
          >
            <div style={styles.resultBannerHeader}>
              <span
                style={{
                  fontWeight: 700,
                  color: chainResult.status === 'VALID' ? 'var(--accent-green)' : 'var(--accent-red)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                }}
              >
                {chainResult.status === 'VALID'
                  ? `✓ CUSTODY CHAIN VALID (${chainResult.events_checked} Events Verified)`
                  : '⚠ CUSTODY CHAIN BROKEN / TAMPER DETECTED'}
              </span>
              <span style={styles.resultTimestamp}>
                {new Date(chainResult.verified_at).toLocaleTimeString()}
              </span>
            </div>
            <div style={styles.resultDetails}>{chainResult.details}</div>
          </div>
        )}

        {/* TAB 1: METADATA */}
        {activeTab === 'METADATA' && (
          <div style={styles.content}>
            <div style={styles.fieldGrid}>
              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>ORIGINAL EVIDENCE FILE</div>
                <div style={styles.fieldValuePrimary}>{evidence.original_filename}</div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>INGESTION STATUS</div>
                <div style={styles.fieldValue}>
                  <span style={{ ...styles.statusBadge, ...getStatusStyle(evidence.status) }}>
                    {evidence.status}
                  </span>
                </div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>EXACT FILE SIZE</div>
                <div style={styles.fieldValue}>
                  {formatBytes(evidence.file_size)}{' '}
                  <span style={styles.byteCount}>({evidence.file_size.toLocaleString()} bytes)</span>
                </div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>STORAGE IDENTIFIER</div>
                <div style={styles.monoValue}>{evidence.stored_filename}</div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>MIME TYPE (REPORTED / DETECTED)</div>
                <div style={styles.monoValue}>
                  {evidence.mime_type} / {evidence.detected_mime_type || 'unverified'}
                </div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>INTEGRITY STATE</div>
                <div style={styles.fieldValue}>
                  <span style={{ ...styles.integrityBadge, ...getIntegrityStyle(currentIntegrityStatus) }}>
                    {currentIntegrityStatus}
                  </span>
                </div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>INGESTED BY</div>
                <div style={styles.fieldValue}>
                  {evidence.uploader_name || 'Authorized Investigator'}{' '}
                  {evidence.uploader_email && (
                    <span style={styles.emailTag}>({evidence.uploader_email})</span>
                  )}
                </div>
              </div>

              <div style={styles.fieldCard}>
                <div style={styles.fieldLabel}>INGESTION TIMESTAMP (UTC)</div>
                <div style={styles.fieldValue}>
                  {new Date(evidence.uploaded_at).toLocaleString()}
                </div>
              </div>
            </div>

            {/* Cryptographic SHA-256 Checksum Card */}
            <div style={styles.checksumCard}>
              <div style={styles.checksumHeader}>
                <span style={styles.checksumLabel}>RECORDED SHA-256 BASELINE HASH</span>
                <button
                  onClick={() => evidence.sha256_hash && handleCopyHash(evidence.sha256_hash)}
                  style={styles.copyBtn}
                >
                  {copiedHash ? '✓ COPIED' : 'COPY HASH'}
                </button>
              </div>
              <div style={styles.checksumHash}>
                {evidence.sha256_hash || 'SHA-256 hash not computed'}
              </div>
              <div style={styles.checksumNotice}>
                Computed in-flight during streaming upload. Treat as the immutable baseline identifier.
              </div>
            </div>

            {/* Verification trigger card */}
            <div style={styles.verifyActionCard}>
              <div>
                <div style={styles.verifyActionTitle}>On-Demand Cryptographic Integrity Verification</div>
                <div style={styles.verifyActionDesc}>
                  Streams the stored physical evidence from disk in 64KB blocks to recalculate the SHA-256 digest
                  and compares it against the baseline.
                </div>
              </div>
              <button
                onClick={handleVerifyIntegrity}
                disabled={isVerifyingIntegrity || !canManage}
                style={styles.verifyIntegrityBtn}
              >
                {isVerifyingIntegrity ? 'VERIFYING IN-FLIGHT...' : 'VERIFY INTEGRITY NOW'}
              </button>
            </div>
          </div>
        )}

        {/* TAB 2: CHAIN OF CUSTODY */}
        {activeTab === 'CUSTODY' && (
          <div style={styles.content}>
            <div style={styles.custodyToolbar}>
              <div>
                <span style={styles.custodyTitle}>Cryptographic Chain of Custody</span>
                <div style={styles.custodySubtitle}>
                  Append-only, chronologically ordered sequence with SHA-256 event hash linkage.
                </div>
              </div>
              <button
                onClick={handleVerifyChain}
                disabled={isVerifyingChain || custodyEvents.length === 0}
                style={styles.verifyChainBtn}
              >
                {isVerifyingChain ? 'VERIFYING CHAIN...' : 'VERIFY CUSTODY CHAIN'}
              </button>
            </div>

            {isLoadingCustody ? (
              <div style={styles.loadingBox}>Loading custody history...</div>
            ) : custodyEvents.length === 0 ? (
              <div style={styles.emptyCustody}>No custody events recorded for this evidence item.</div>
            ) : (
              <div style={styles.timelineList}>
                {custodyEvents.map((evt) => (
                  <div key={evt.id} style={styles.timelineItem}>
                    <div style={styles.timelineSeq}>#{evt.sequence_number}</div>
                    <div style={styles.timelineContent}>
                      <div style={styles.timelineHeader}>
                        <div style={styles.timelineTypeRow}>
                          <span style={styles.eventTypeTag}>{formatEventType(evt.event_type)}</span>
                          <span style={styles.timelineActor}>
                            Actor: {evt.actor_name || evt.actor_email || 'System Ingestion Engine'}
                          </span>
                        </div>
                        <span style={styles.timelineTime}>
                          {new Date(evt.timestamp).toLocaleString()}
                        </span>
                      </div>

                      {/* Event Hash and Linkage */}
                      <div style={styles.hashLinkageBox}>
                        <div style={styles.hashRow}>
                          <span style={styles.hashLabel}>Event Digest:</span>
                          <code style={styles.hashText}>{evt.event_hash}</code>
                          <button
                            onClick={() => handleCopyHash(evt.event_hash, true)}
                            style={styles.inlineCopyBtn}
                          >
                            {copiedEventHash === evt.event_hash ? '✓' : 'COPY'}
                          </button>
                        </div>
                        {evt.previous_event_hash && (
                          <div style={styles.hashRow}>
                            <span style={styles.hashLabel}>Prev Digest:</span>
                            <code style={styles.hashTextMuted}>{evt.previous_event_hash}</code>
                          </div>
                        )}
                      </div>

                      {/* Event Metadata */}
                      {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                        <div style={styles.metadataBox}>
                          <pre style={styles.metadataPre}>
                            {JSON.stringify(evt.metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: PARSING PIPELINE (PHASE 6 SCALABLE INGESTION) */}
        {activeTab === 'PROCESSING' && (
          <div style={styles.content}>
            {!activeJob ? (
              <div style={styles.emptyStateCard}>
                <div style={styles.emptyIcon}>⚡</div>
                <div style={styles.emptyTitle}>Forensic UFDR Ingestion Engine</div>
                <div style={styles.emptyDesc}>
                  Parse this UFDR package via chunked, bounded-memory worker queues to extract Calls,
                  Messages, Contacts, Locations, Browser history, Applications, and Filesystem records.
                </div>

                {/* Priority Selection for initial parse */}
                <div style={styles.prioritySelectorContainer}>
                  <span style={styles.priorityLabel}>JOB QUEUE PRIORITY:</span>
                  {(['NORMAL', 'HIGH', 'LOW'] as JobPriority[]).map((p) => (
                    <button
                      key={p}
                      onClick={() => setSelectedPriority(p)}
                      style={{
                        ...styles.prioritySelectBtn,
                        ...(selectedPriority === p ? styles.prioritySelectBtnActive : {}),
                      }}
                    >
                      {p}
                    </button>
                  ))}
                </div>

                {parseError && (
                  <div style={styles.jobErrorBox}>
                    <div style={styles.jobErrorTitle}>Parse Initiation Error:</div>
                    <div>{parseError}</div>
                  </div>
                )}

                <button
                  onClick={() => handleTriggerParse(selectedPriority)}
                  disabled={isTriggeringParse || evidence.integrity_status === 'MISMATCH'}
                  style={styles.primaryActionBtn}
                >
                  {isTriggeringParse ? 'ENQUEUING FORENSIC PARSE...' : `ENQUEUE UFDR PARSE (${selectedPriority} PRIORITY)`}
                </button>
              </div>
            ) : (
              <div style={styles.pipelineContainer}>
                {/* Phase 7 End-to-End Forensic Processing Architecture Overview */}
                <div style={styles.dualPipelineBar}>
                  <div style={styles.pipelineStageCard}>
                    <div style={styles.pipelineStageHeader}>
                      <span style={styles.pipelineStageStepNum}>STAGE 1</span>
                      <span style={styles.pipelineStageTitle}>UFDR Ingestion & Extraction</span>
                    </div>
                    <div style={styles.pipelineStageStatusRow}>
                      <span style={{
                        ...styles.pipelineStatusBadge,
                        backgroundColor: artifactsTotal > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: artifactsTotal > 0 ? 'var(--accent-green)' : 'var(--text-muted)',
                        border: artifactsTotal > 0 ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(148, 163, 184, 0.3)',
                      }}>
                        {artifactsTotal > 0 ? '✓ COMPLETED' : activeJob?.job_type === 'UFDR_PARSE' && ['RUNNING', 'STARTING'].includes(activeJob.status) ? '▶ PARSING' : 'PENDING'}
                      </span>
                      <span style={styles.pipelineStageCount}>
                        {artifactsTotal.toLocaleString()} Raw Artifacts
                      </span>
                    </div>
                    <button
                      onClick={() => handleTriggerParse(selectedPriority)}
                      disabled={isTriggeringParse || ['RUNNING', 'STARTING'].includes(activeJob?.status || '')}
                      style={styles.pipelineStageBtn}
                      title="Run chunked, bounded-memory UFDR extraction"
                    >
                      {isTriggeringParse ? 'ENQUEUING...' : artifactsTotal > 0 ? 'RE-PARSE ARCHIVE' : 'RUN UFDR PARSE'}
                    </button>
                  </div>

                  <div style={styles.pipelineArrow}>➔</div>

                  <div style={styles.pipelineStageCard}>
                    <div style={styles.pipelineStageHeader}>
                      <span style={styles.pipelineStageStepNum}>STAGE 2</span>
                      <span style={styles.pipelineStageTitle}>Normalization & Canonical Model</span>
                    </div>
                    <div style={styles.pipelineStageStatusRow}>
                      <span style={{
                        ...styles.pipelineStatusBadge,
                        backgroundColor: canonicalTotal > 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: canonicalTotal > 0 ? 'var(--accent-green)' : 'var(--text-muted)',
                        border: canonicalTotal > 0 ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(148, 163, 184, 0.3)',
                      }}>
                        {canonicalTotal > 0 ? '✓ COMPLETED' : activeJob?.job_type === 'NORMALIZATION' && ['RUNNING', 'STARTING'].includes(activeJob.status) ? '▶ NORMALIZING' : 'PENDING'}
                      </span>
                      <span style={styles.pipelineStageCount}>
                        {canonicalTotal.toLocaleString()} Canonical Records
                      </span>
                    </div>
                    <button
                      onClick={() => handleTriggerNormalize(selectedPriority)}
                      disabled={isTriggeringNormalize || artifactsTotal === 0 || ['RUNNING', 'STARTING'].includes(activeJob?.status || '')}
                      style={{
                        ...styles.pipelineStageBtn,
                        borderColor: 'var(--accent-cyan)',
                        backgroundColor: 'rgba(56, 189, 248, 0.15)',
                        color: 'var(--accent-cyan)',
                      }}
                      title={artifactsTotal === 0 ? 'Must parse raw artifacts first' : 'Standardize raw artifacts into canonical schema'}
                    >
                      {isTriggeringNormalize ? 'ENQUEUING...' : canonicalTotal > 0 ? 'RE-NORMALIZE EVIDENCE' : 'NORMALIZE EVIDENCE'}
                    </button>
                  </div>
                </div>

                {/* Live Job Card */}
                <div style={styles.jobCard}>
                  <div style={styles.jobCardHeader}>
                    <div>
                      <div style={styles.jobIdRow}>
                        <span style={styles.jobTypeBadge}>{activeJob.job_type}</span>
                        <span style={{ ...styles.jobStatusBadge, ...getJobStatusStyle(activeJob.status) }}>
                          ● {activeJob.status}
                        </span>
                        <span style={styles.priorityTag}>
                          PRIORITY: {activeJob.priority || 'NORMAL'}
                        </span>
                        <span style={styles.workerTag}>
                          WORKER: {activeJob.worker_id || 'STANDBY'}
                        </span>
                        {activeJob.retry_count > 0 && (
                          <span style={styles.retryTag}>
                            RETRY {activeJob.retry_count} / {activeJob.max_retries}
                          </span>
                        )}
                        <span style={styles.jobIdText}>Job ID: {activeJob.id.slice(0, 12)}...</span>
                      </div>
                      <div style={styles.jobTimestamp}>
                        Initiated: {new Date(activeJob.created_at).toLocaleString()}
                        {activeJob.completed_at && ` • Completed: ${new Date(activeJob.completed_at).toLocaleString()}`}
                        {activeJob.last_heartbeat_at && (
                          <span style={styles.heartbeatText}>
                            {' '}• Heartbeat: {new Date(activeJob.last_heartbeat_at).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Job Actions: Cancel, Retry, Re-parse, Re-normalize */}
                    <div style={styles.jobActionBtnGroup}>
                      {['QUEUED', 'STARTING', 'RUNNING'].includes(activeJob.status) && (
                        <button
                          onClick={handleCancelJob}
                          disabled={isCancelling || activeJob.status === 'CANCEL_REQUESTED'}
                          style={styles.cancelBtn}
                          title="Request cooperative cancellation at next checkpoint"
                        >
                          {isCancelling || activeJob.status === 'CANCEL_REQUESTED' ? 'CANCELING...' : 'CANCEL JOB'}
                        </button>
                      )}

                      {['FAILED', 'CANCELLED', 'PARTIAL'].includes(activeJob.status) && (
                        <button
                          onClick={handleRetryJob}
                          disabled={isRetrying}
                          style={styles.retryBtn}
                          title="Resume job from latest safe checkpoint"
                        >
                          {isRetrying ? 'RETRYING...' : 'RESUME / RETRY'}
                        </button>
                      )}

                      {['COMPLETED', 'FAILED', 'CANCELLED', 'PARTIAL'].includes(activeJob.status) && (
                        <button
                          onClick={() => {
                            if (activeJob.job_type === 'NORMALIZATION') {
                              handleTriggerNormalize(selectedPriority);
                            } else {
                              handleTriggerParse(selectedPriority);
                            }
                          }}
                          disabled={isTriggeringParse || isTriggeringNormalize}
                          style={styles.reparseBtn}
                          title="Rerun job idempotently"
                        >
                          {isTriggeringParse || isTriggeringNormalize ? 'ENQUEUING...' : `RERUN ${activeJob.job_type}`}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Stage Stepper Pipeline (Dynamic for Parse vs Normalization) */}
                  <div style={styles.stageStepper}>
                    {(activeJob.job_type === 'NORMALIZATION'
                      ? [
                          { key: 'FETCHING_RAW', label: '1. Fetch Raw' },
                          { key: 'NORMALIZING', label: '2. Standardize & Map' },
                          { key: 'PERSISTING', label: '3. Batch Upsert' },
                          { key: 'FINALIZING', label: '4. Finalize' },
                        ]
                      : [
                          { key: 'VALIDATING', label: '1. Validate' },
                          { key: 'INSPECTING_ARCHIVE', label: '2. Inspect' },
                          { key: 'PARSING', label: '3. Parse XML' },
                          { key: 'PERSISTING', label: '4. Batch Commit' },
                          { key: 'FINALIZING', label: '5. Finalize' },
                        ]
                    ).map((step, idx) => {
                      const stages = activeJob.job_type === 'NORMALIZATION'
                        ? ['FETCHING_RAW', 'NORMALIZING', 'PERSISTING', 'FINALIZING', 'COMPLETED']
                        : ['VALIDATING', 'INSPECTING_ARCHIVE', 'PARSING', 'PERSISTING', 'FINALIZING', 'COMPLETED'];
                      const currentIdx = stages.indexOf(activeJob.current_stage || stages[0]);
                      const stepIdx = stages.indexOf(step.key);
                      const isComplete = activeJob.status === 'COMPLETED' || currentIdx > stepIdx;
                      const isCurrent = activeJob.current_stage === step.key && activeJob.status === 'RUNNING';

                      return (
                        <div
                          key={step.key}
                          style={{
                            ...styles.stageStep,
                            ...(isCurrent ? styles.stageStepActive : {}),
                            ...(isComplete ? styles.stageStepComplete : {}),
                          }}
                        >
                          <span style={styles.stageStepBullet}>
                            {isComplete ? '✓' : isCurrent ? '▶' : idx + 1}
                          </span>
                          <span style={styles.stageStepLabel}>{step.label}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* Progress Bar Track */}
                  <div style={styles.progressContainer}>
                    <div style={styles.progressBarTrack}>
                      <div
                        style={{
                          ...styles.progressBarFill,
                          width: `${activeJob.progress}%`,
                          backgroundColor:
                            activeJob.status === 'FAILED'
                              ? 'var(--accent-red)'
                              : activeJob.status === 'CANCELLED'
                              ? '#fb923c'
                              : activeJob.status === 'COMPLETED'
                              ? 'var(--accent-green)'
                              : 'var(--accent-cyan)',
                        }}
                      />
                    </div>
                    <div style={styles.progressMeta}>
                      <span>
                        {activeJob.current_file
                          ? `Processing: ${activeJob.current_file}`
                          : activeJob.status === 'RUNNING'
                          ? `Stage: ${activeJob.current_stage || 'PARSING'}`
                          : activeJob.status}
                      </span>
                      <span style={styles.progressPercent}>{activeJob.progress}%</span>
                    </div>
                  </div>

                  {/* Real-time Telemetry Banner */}
                  <div style={styles.telemetryBar}>
                    <div style={styles.telemetryItem}>
                      <span style={styles.telemetryLabel}>THROUGHPUT:</span>
                      <span style={styles.telemetryVal}>
                        {activeJob.processing_rate ? `${activeJob.processing_rate.toFixed(1)} rec/s` : '0 rec/s'}
                      </span>
                    </div>
                    <div style={styles.telemetryItem}>
                      <span style={styles.telemetryLabel}>ETA REMAINING:</span>
                      <span style={styles.telemetryVal}>
                        {activeJob.estimated_remaining_seconds !== null && activeJob.estimated_remaining_seconds !== undefined
                          ? `~${Math.ceil(activeJob.estimated_remaining_seconds)}s`
                          : ['RUNNING', 'STARTING'].includes(activeJob.status)
                          ? 'Calculating...'
                          : '—'}
                      </span>
                    </div>
                    <div style={styles.telemetryItem}>
                      <span style={styles.telemetryLabel}>STAGE:</span>
                      <span style={{ ...styles.telemetryVal, color: 'var(--accent-cyan)' }}>
                        {activeJob.current_stage || 'INSPECTING_ARCHIVE'}
                      </span>
                    </div>
                    {activeJob.checkpoint_data?.completed_files?.length ? (
                      <div style={styles.telemetryItem}>
                        <span style={styles.telemetryLabel}>CHECKPOINT:</span>
                        <span style={{ ...styles.telemetryVal, color: 'var(--accent-green)' }}>
                          {activeJob.checkpoint_data.completed_files.length} archive member(s) saved
                        </span>
                      </div>
                    ) : null}
                  </div>

                  {/* Metrics Grid */}
                  <div style={styles.metricsGrid}>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>FILES PROCESSED</div>
                      <div style={styles.metricVal}>
                        {activeJob.files_processed} / {activeJob.files_total}
                      </div>
                    </div>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>RECORDS COMMITTED</div>
                      <div style={styles.metricValPrimary}>
                        {(activeJob.records_processed ?? activeJob.artifacts_total ?? 0).toLocaleString()}
                      </div>
                    </div>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>RECORDS FAILED</div>
                      <div style={{ ...styles.metricVal, color: (activeJob.records_failed || 0) > 0 ? 'var(--accent-red)' : 'inherit' }}>
                        {(activeJob.records_failed || 0).toLocaleString()}
                      </div>
                    </div>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>DATA VOLUME</div>
                      <div style={styles.metricVal}>
                        {((activeJob.bytes_processed || 0) / (1024 * 1024)).toFixed(1)} MB / {((activeJob.bytes_total || 0) / (1024 * 1024)).toFixed(1)} MB
                      </div>
                    </div>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>WARNINGS</div>
                      <div style={{ ...styles.metricVal, color: activeJob.warnings_count > 0 ? 'var(--accent-amber)' : 'inherit' }}>
                        {activeJob.warnings_count}
                      </div>
                    </div>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>ERRORS</div>
                      <div style={{ ...styles.metricVal, color: activeJob.errors_count > 0 ? 'var(--accent-red)' : 'inherit' }}>
                        {activeJob.errors_count}
                      </div>
                    </div>
                  </div>

                  {/* Error Box if job failed */}
                  {activeJob.error_message && (
                    <div style={styles.jobErrorBox}>
                      <div style={styles.jobErrorTitle}>Processing Diagnostics:</div>
                      <div>{activeJob.error_message}</div>
                    </div>
                  )}
                </div>

                {/* Parsing Summary Breakdown Card */}
                {activeJob.summary_json && (
                  <div style={styles.summaryCard}>
                    <div style={styles.summaryTitle}>Forensic Artifact Extraction Breakdown</div>
                    <div style={styles.artifactGrid}>
                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>📞</span>
                          <span style={styles.catName}>Calls</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.CALL ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.CALL).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>💬</span>
                          <span style={styles.catName}>Messages</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.MESSAGE ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.MESSAGE).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>👥</span>
                          <span style={styles.catName}>Contacts</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.CONTACT ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.CONTACT).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>📍</span>
                          <span style={styles.catName}>Location Fixes</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.LOCATION ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.LOCATION).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>🌐</span>
                          <span style={styles.catName}>Browser History</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.BROWSER ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.BROWSER).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>📱</span>
                          <span style={styles.catName}>Applications</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.APPLICATION ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.APPLICATION).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>

                      <div style={styles.categoryCard}>
                        <div style={styles.categoryHeader}>
                          <span style={styles.catIcon}>📁</span>
                          <span style={styles.catName}>Filesystem Metadata</span>
                        </div>
                        <div style={styles.catCount}>
                          {(activeJob.summary_json.counts_by_type?.FILESYSTEM ?? 0) > 0
                            ? (activeJob.summary_json.counts_by_type.FILESYSTEM).toLocaleString()
                            : <span style={styles.notPresent}>Not present</span>}
                        </div>
                      </div>
                    </div>

                    {/* Warnings / Diagnostics */}
                    {activeJob.summary_json.warnings && activeJob.summary_json.warnings.length > 0 && (
                      <div style={styles.diagnosticsBox}>
                        <div style={styles.diagnosticsTitle}>
                          Parser Warnings ({activeJob.summary_json.warnings.length})
                        </div>
                        <ul style={styles.diagnosticsList}>
                          {activeJob.summary_json.warnings.map((warn, i) => (
                            <li key={i}>{warn}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Phase 6 Processing Run History Section */}
                {allJobs && allJobs.length > 0 && (
                  <div style={styles.historyContainer}>
                    <div style={styles.historyTitle}>
                      <span>EXECUTION RUN HISTORY</span>
                      <span style={styles.historySubtitle}>{allJobs.length} execution(s) recorded</span>
                    </div>
                    <div style={styles.historyTableWrapper}>
                      <table style={styles.historyTable}>
                        <thead>
                          <tr>
                            <th style={styles.historyTh}>JOB ID</th>
                            <th style={styles.historyTh}>STATUS</th>
                            <th style={styles.historyTh}>PRIORITY</th>
                            <th style={styles.historyTh}>STAGE</th>
                            <th style={styles.historyTh}>WORKER</th>
                            <th style={styles.historyTh}>RECORDS</th>
                            <th style={styles.historyTh}>RETRIES</th>
                            <th style={styles.historyTh}>TIMESTAMP</th>
                            <th style={styles.historyTh}>ACTION</th>
                          </tr>
                        </thead>
                        <tbody>
                          {allJobs.map((j) => (
                            <tr
                              key={j.id}
                              style={{
                                ...styles.historyTr,
                                ...(j.id === activeJob.id ? styles.historyTrActive : {}),
                              }}
                            >
                              <td style={styles.historyTdMono}>{j.id.slice(0, 8)}...</td>
                              <td style={styles.historyTd}>
                                <span style={{ ...styles.jobStatusBadge, ...getJobStatusStyle(j.status), fontSize: '10px' }}>
                                  ● {j.status}
                                </span>
                              </td>
                              <td style={styles.historyTd}>
                                <span style={styles.historyPriorityBadge}>{j.priority || 'NORMAL'}</span>
                              </td>
                              <td style={styles.historyTd}>{j.current_stage || '—'}</td>
                              <td style={styles.historyTdMono}>{j.worker_id || '—'}</td>
                              <td style={styles.historyTd}>
                                {(j.records_processed ?? j.artifacts_total ?? 0).toLocaleString()}
                              </td>
                              <td style={styles.historyTd}>{j.retry_count ?? 0}</td>
                              <td style={styles.historyTd}>{new Date(j.created_at).toLocaleTimeString()}</td>
                              <td style={styles.historyTd}>
                                <button
                                  onClick={() => setActiveJob(j)}
                                  style={j.id === activeJob.id ? styles.historyViewBtnActive : styles.historyViewBtn}
                                >
                                  {j.id === activeJob.id ? 'SELECTED' : 'INSPECT'}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: RAW ARTIFACTS EXPLORER */}
        {activeTab === 'ARTIFACTS' && (
          <div style={styles.content}>
            {/* Category Filter Chips */}
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
                  onClick={() => handleCategoryChange(chip.value)}
                  style={{
                    ...styles.chipBtn,
                    ...(selectedCategory === chip.value ? styles.activeChipBtn : {}),
                  }}
                >
                  {chip.label}
                </button>
              ))}
            </div>

            {/* Artifact Table */}
            {isLoadingArtifacts ? (
              <div style={styles.loadingBox}>Loading forensic artifact records...</div>
            ) : artifacts.length === 0 ? (
              <div style={styles.emptyStateCard}>
                <div style={styles.emptyTitle}>No Artifacts Found</div>
                <div style={styles.emptyDesc}>
                  No parsed artifacts matching "{selectedCategory}" were extracted from this evidence.
                </div>
              </div>
            ) : (
              <div style={styles.artifactsTableWrapper}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>CATEGORY</th>
                      <th style={styles.th}>SOURCE PROVENANCE</th>
                      <th style={styles.th}>RECORD IDENTIFIER</th>
                      <th style={styles.th}>RECORD PREVIEW</th>
                      <th style={styles.th}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {artifacts.map((art) => (
                      <tr key={art.id} style={styles.tr}>
                        <td style={styles.td}>
                          <span style={{ ...styles.categoryBadge, ...getCategoryBadgeStyle(art.artifact_type) }}>
                            {art.artifact_type}
                          </span>
                        </td>
                        <td style={styles.td}>
                          <div style={styles.sourceFile}>{art.source_file}</div>
                          <div style={styles.sourcePath} title={art.source_path}>
                            {art.source_path}
                          </div>
                        </td>
                        <td style={styles.td}>
                          <code style={styles.recordId}>{art.record_identifier}</code>
                        </td>
                        <td style={styles.td}>
                          {renderArtifactPreview(art)}
                        </td>
                        <td style={styles.td}>
                          <button
                            onClick={() => setInspectingArtifact(art)}
                            style={styles.viewPayloadBtn}
                          >
                            INSPECT RAW
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination */}
                <div style={styles.paginationBar}>
                  <div style={styles.pageInfo}>
                    Showing {artifacts.length} of {artifactsTotal.toLocaleString()} artifacts
                    {artifactsTotalPages > 1 && ` (Page ${artifactsPage} of ${artifactsTotalPages})`}
                  </div>
                  <div style={styles.pageBtnGroup}>
                    <button
                      onClick={() => handlePageChange(artifactsPage - 1)}
                      disabled={artifactsPage <= 1}
                      style={styles.pageBtn}
                    >
                      ← PREV
                    </button>
                    <button
                      onClick={() => handlePageChange(artifactsPage + 1)}
                      disabled={artifactsPage >= artifactsTotalPages}
                      style={styles.pageBtn}
                    >
                      NEXT →
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: CANONICAL FORENSIC RECORDS EXPLORER */}
        {activeTab === 'CANONICAL' && evidence && (
          <div style={styles.content}>
            <CanonicalEvidenceExplorer
              caseId={caseId}
              evidence={evidence}
              onSelectRawArtifact={(rawArt) => {
                setActiveTab('ARTIFACTS');
                setInspectingArtifact(rawArt);
              }}
            />
          </div>
        )}

        {/* Modal Actions Footer */}
        <div style={styles.actions}>
          {canManage && evidence.status !== 'QUARANTINED' && (
            <button
              onClick={handleQuarantine}
              disabled={isQuarantining}
              style={styles.quarantineBtn}
              title="Quarantine evidence without physical deletion"
            >
              {isQuarantining ? 'QUARANTINING...' : 'QUARANTINE EVIDENCE'}
            </button>
          )}

          <div style={{ flex: 1 }} />

          <button onClick={onClose} style={styles.closeActionBtn}>
            CLOSE
          </button>

          <button
            onClick={handleDownload}
            disabled={isDownloading || evidence.status === 'FAILED'}
            style={styles.downloadBtn}
          >
            {isDownloading ? 'DOWNLOADING...' : 'DOWNLOAD EVIDENCE ARCHIVE'}
          </button>
        </div>
      </div>

      {/* Raw Payload Inspector Modal */}
      {inspectingArtifact && (
        <div style={styles.inspectOverlay}>
          <div style={styles.inspectModal}>
            <div style={styles.inspectHeader}>
              <div>
                <div style={styles.inspectTitle}>
                  Artifact Provenance & Raw Parsed Representation
                </div>
                <div style={styles.inspectSub}>
                  Record ID: {inspectingArtifact.record_identifier} • Type: {inspectingArtifact.artifact_type}
                </div>
              </div>
              <button
                onClick={() => setInspectingArtifact(null)}
                style={styles.closeBtn}
              >
                ✕
              </button>
            </div>

            <div style={styles.inspectProvenanceCard}>
              <div style={styles.provRow}>
                <span style={styles.provLabel}>Evidence ID:</span>
                <code>{inspectingArtifact.evidence_id}</code>
              </div>
              <div style={styles.provRow}>
                <span style={styles.provLabel}>Source File:</span>
                <code>{inspectingArtifact.source_file}</code>
              </div>
              <div style={styles.provRow}>
                <span style={styles.provLabel}>Source Path:</span>
                <code>{inspectingArtifact.source_path}</code>
              </div>
              <div style={styles.provRow}>
                <span style={styles.provLabel}>Extraction Time:</span>
                <span>{new Date(inspectingArtifact.parsed_at).toLocaleString()}</span>
              </div>
            </div>

            <div style={styles.rawJsonHeader}>
              <span style={styles.rawJsonLabel}>PRESERVED RAW DATA (JSON)</span>
              <button
                onClick={() => handleCopyRawJson(inspectingArtifact.raw_data)}
                style={styles.copyJsonBtn}
              >
                {copiedRawJson ? '✓ COPIED JSON' : 'COPY RAW JSON'}
              </button>
            </div>

            <div style={styles.rawJsonViewer}>
              <pre style={styles.jsonPre}>
                {JSON.stringify(inspectingArtifact.raw_data, null, 2)}
              </pre>
            </div>

            <div style={styles.inspectFooter}>
              <button
                onClick={() => setInspectingArtifact(null)}
                style={styles.primaryActionBtn}
              >
                DONE
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function formatEventType(type: string): string {
  switch (type) {
    case 'EVIDENCE_UPLOADED':
      return 'EVIDENCE INGESTION';
    case 'EVIDENCE_HASHED':
      return 'SHA-256 CALCULATED';
    case 'EVIDENCE_VALIDATED':
      return 'ARCHIVE VALIDATED';
    case 'EVIDENCE_ACCESSED':
      return 'METADATA ACCESSED';
    case 'EVIDENCE_DOWNLOADED':
      return 'EVIDENCE DOWNLOADED';
    case 'INTEGRITY_VERIFIED':
      return 'INTEGRITY VERIFIED';
    case 'INTEGRITY_MISMATCH':
      return 'INTEGRITY MISMATCH DETECTED';
    case 'EVIDENCE_PROCESSING_STARTED':
      return 'UFDR PARSING STARTED';
    case 'EVIDENCE_PROCESSING_COMPLETED':
      return 'UFDR PARSING COMPLETED';
    case 'EVIDENCE_QUARANTINED':
      return 'EVIDENCE QUARANTINED';
    case 'EVIDENCE_ARCHIVED':
      return 'EVIDENCE ARCHIVED';
    default:
      return type;
  }
}

function getStatusStyle(status: EvidenceStatus): React.CSSProperties {
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

function getIntegrityStyle(status: IntegrityStatus): React.CSSProperties {
  switch (status) {
    case 'VALID':
      return {
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        color: 'var(--accent-green)',
        borderColor: 'rgba(16, 185, 129, 0.4)',
      };
    case 'MISMATCH':
      return {
        backgroundColor: 'rgba(239, 68, 68, 0.2)',
        color: 'var(--accent-red)',
        borderColor: 'rgba(239, 68, 68, 0.6)',
      };
    case 'MISSING':
      return {
        backgroundColor: 'rgba(245, 158, 11, 0.2)',
        color: 'var(--accent-amber)',
        borderColor: 'rgba(245, 158, 11, 0.6)',
      };
    case 'UNKNOWN':
    default:
      return {
        backgroundColor: 'rgba(148, 163, 184, 0.15)',
        color: 'var(--text-muted)',
        borderColor: 'rgba(148, 163, 184, 0.3)',
      };
  }
}

function getJobStatusStyle(status: JobStatus): React.CSSProperties {
  switch (status) {
    case 'COMPLETED':
      return {
        backgroundColor: 'rgba(16, 185, 129, 0.15)',
        color: 'var(--accent-green)',
        borderColor: 'rgba(16, 185, 129, 0.4)',
      };
    case 'RUNNING':
      return {
        backgroundColor: 'rgba(56, 189, 248, 0.15)',
        color: 'var(--accent-cyan)',
        borderColor: 'rgba(56, 189, 248, 0.4)',
      };
    case 'STARTING':
    case 'RETRYING':
      return {
        backgroundColor: 'rgba(14, 165, 233, 0.15)',
        color: '#38bdf8',
        borderColor: 'rgba(14, 165, 233, 0.4)',
      };
    case 'QUEUED':
      return {
        backgroundColor: 'rgba(245, 158, 11, 0.15)',
        color: 'var(--accent-amber)',
        borderColor: 'rgba(245, 158, 11, 0.4)',
      };
    case 'CANCEL_REQUESTED':
      return {
        backgroundColor: 'rgba(251, 146, 60, 0.15)',
        color: '#fb923c',
        borderColor: 'rgba(251, 146, 60, 0.4)',
      };
    case 'PARTIAL':
      return {
        backgroundColor: 'rgba(234, 179, 8, 0.15)',
        color: '#eab308',
        borderColor: 'rgba(234, 179, 8, 0.4)',
      };
    case 'PAUSED':
      return {
        backgroundColor: 'rgba(148, 163, 184, 0.15)',
        color: 'var(--text-muted)',
        borderColor: 'rgba(148, 163, 184, 0.4)',
      };
    case 'FAILED':
    case 'CANCELLED':
      return {
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        color: 'var(--accent-red)',
        borderColor: 'rgba(239, 68, 68, 0.4)',
      };
  }
}

function getCategoryBadgeStyle(cat: ArtifactType): React.CSSProperties {
  switch (cat) {
    case 'CALL':
      return { backgroundColor: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)', borderColor: 'rgba(56, 189, 248, 0.4)' };
    case 'MESSAGE':
      return { backgroundColor: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', borderColor: 'rgba(168, 85, 247, 0.4)' };
    case 'CONTACT':
      return { backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-green)', borderColor: 'rgba(16, 185, 129, 0.4)' };
    case 'LOCATION':
      return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'var(--accent-amber)', borderColor: 'rgba(245, 158, 11, 0.4)' };
    case 'BROWSER':
      return { backgroundColor: 'rgba(236, 72, 153, 0.15)', color: '#f472b6', borderColor: 'rgba(236, 72, 153, 0.4)' };
    case 'APPLICATION':
      return { backgroundColor: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', borderColor: 'rgba(99, 102, 241, 0.4)' };
    case 'FILESYSTEM':
      return { backgroundColor: 'rgba(148, 163, 184, 0.15)', color: 'var(--text-muted)', borderColor: 'rgba(148, 163, 184, 0.4)' };
    case 'CALENDAR':
      return { backgroundColor: 'rgba(20, 184, 166, 0.15)', color: '#2dd4bf', borderColor: 'rgba(20, 184, 166, 0.4)' };
    case 'SOCIAL':
      return { backgroundColor: 'rgba(244, 63, 94, 0.15)', color: '#fb7185', borderColor: 'rgba(244, 63, 94, 0.4)' };
    case 'DEVICE_EVENT':
      return { backgroundColor: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa', borderColor: 'rgba(139, 92, 246, 0.4)' };
    default:
      return { backgroundColor: 'rgba(148, 163, 184, 0.15)', color: 'var(--text-secondary)', borderColor: 'rgba(148, 163, 184, 0.3)' };
  }
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    backdropFilter: 'blur(6px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
  },
  modal: {
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '12px',
    border: '1px solid var(--border-color)',
    width: '100%',
    maxWidth: '1050px',
    maxHeight: '92vh',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.7)',
  },
  header: {
    padding: '20px 24px',
    borderBottom: '1px solid var(--border-color)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    backgroundColor: 'var(--bg-tertiary)',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  badgeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  title: {
    margin: 0,
    fontSize: '18px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '-0.3px',
  },
  subtitle: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    marginTop: '4px',
  },
  headerParseBtn: {
    padding: '7px 16px',
    backgroundColor: 'var(--accent-cyan)',
    color: '#0a0f1d',
    border: 'none',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 700,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  disabledBtn: {
    opacity: 0.4,
    cursor: 'not-allowed',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    fontSize: '18px',
    cursor: 'pointer',
    padding: '4px 8px',
    borderRadius: '4px',
  },
  tabBar: {
    display: 'flex',
    backgroundColor: 'var(--bg-primary)',
    borderBottom: '1px solid var(--border-color)',
    padding: '0 16px',
    overflowX: 'auto',
  },
  tabBtn: {
    padding: '12px 18px',
    background: 'none',
    border: 'none',
    borderBottom: '2px solid transparent',
    color: 'var(--text-muted)',
    fontSize: '12px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    whiteSpace: 'nowrap',
  },
  activeTabBtn: {
    color: 'var(--accent-cyan)',
    borderBottomColor: 'var(--accent-cyan)',
  },
  content: {
    padding: '24px',
    overflowY: 'auto',
    flex: 1,
  },
  fieldGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '16px',
    marginBottom: '20px',
  },
  fieldCard: {
    backgroundColor: 'var(--bg-tertiary)',
    padding: '14px 16px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  fieldLabel: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
    marginBottom: '6px',
  },
  fieldValue: {
    fontSize: '14px',
    color: 'var(--text-primary)',
    fontWeight: 500,
  },
  fieldValuePrimary: {
    fontSize: '15px',
    color: 'var(--text-primary)',
    fontWeight: 600,
  },
  monoValue: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
  },
  byteCount: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  emailTag: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  statusBadge: {
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid transparent',
    letterSpacing: '0.4px',
  },
  integrityBadge: {
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid transparent',
    letterSpacing: '0.4px',
  },
  checksumCard: {
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    padding: '16px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    marginBottom: '20px',
  },
  checksumHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  checksumLabel: {
    fontSize: '11px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
  },
  copyBtn: {
    padding: '4px 10px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--accent-cyan)',
    border: '1px solid var(--border-color)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  checksumHash: {
    fontSize: '13px',
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    wordBreak: 'break-all',
    padding: '8px 12px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '6px',
    border: '1px solid rgba(56, 189, 248, 0.2)',
  },
  checksumNotice: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    marginTop: '6px',
  },
  verifyActionCard: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px',
    backgroundColor: 'var(--bg-tertiary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    gap: '20px',
  },
  verifyActionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    marginBottom: '4px',
  },
  verifyActionDesc: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    maxWidth: '650px',
  },
  verifyIntegrityBtn: {
    padding: '9px 18px',
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    color: 'var(--accent-green)',
    border: '1px solid rgba(16, 185, 129, 0.4)',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  verifyChainBtn: {
    padding: '7px 14px',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.4)',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  custodyToolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '16px',
  },
  custodyTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  custodySubtitle: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginTop: '2px',
  },
  loadingBox: {
    padding: '30px',
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
  emptyCustody: {
    padding: '30px',
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
  timelineList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  timelineItem: {
    display: 'flex',
    gap: '16px',
    padding: '14px',
    backgroundColor: 'var(--bg-tertiary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  timelineSeq: {
    fontSize: '14px',
    fontWeight: 800,
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    minWidth: '35px',
  },
  timelineContent: {
    flex: 1,
  },
  timelineHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  timelineTypeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  eventTypeTag: {
    fontSize: '11px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    padding: '2px 8px',
    borderRadius: '4px',
    border: '1px solid rgba(56, 189, 248, 0.3)',
  },
  timelineActor: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
  },
  timelineTime: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  hashLinkageBox: {
    backgroundColor: 'var(--bg-primary)',
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    marginTop: '6px',
  },
  hashRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '11px',
  },
  hashLabel: {
    color: 'var(--text-muted)',
    fontWeight: 600,
    minWidth: '80px',
  },
  hashText: {
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
    wordBreak: 'break-all',
    flex: 1,
  },
  hashTextMuted: {
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
    wordBreak: 'break-all',
  },
  inlineCopyBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--accent-cyan)',
    cursor: 'pointer',
    fontSize: '10px',
    fontWeight: 700,
  },
  metadataBox: {
    marginTop: '8px',
  },
  metadataPre: {
    margin: 0,
    padding: '8px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '4px',
    fontSize: '11px',
    color: 'var(--text-secondary)',
    overflowX: 'auto',
  },
  resultBanner: {
    margin: '16px 24px 0 24px',
    padding: '14px',
    borderRadius: '8px',
    border: '1px solid',
  },
  resultBannerHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
  },
  resultTimestamp: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  resultDetails: {
    fontSize: '13px',
    color: 'var(--text-primary)',
  },
  mismatchCompare: {
    marginTop: '8px',
    padding: '8px',
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    borderRadius: '4px',
    fontSize: '11px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  compareLabel: {
    color: 'var(--text-muted)',
    fontWeight: 600,
  },
  errorBox: {
    margin: '16px 24px 0 24px',
    padding: '12px 16px',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    border: '1px solid rgba(239, 68, 68, 0.4)',
    borderRadius: '6px',
    color: 'var(--accent-red)',
    fontSize: '13px',
  },
  pipelineContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  dualPipelineBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    backgroundColor: 'var(--bg-tertiary)',
    padding: '16px 20px',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
    flexWrap: 'wrap',
  },
  pipelineStageCard: {
    flex: 1,
    minWidth: '260px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    backgroundColor: 'var(--bg-secondary)',
    padding: '14px 16px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  pipelineStageHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  pipelineStageStepNum: {
    padding: '2px 6px',
    borderRadius: '3px',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    fontSize: '9px',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
  pipelineStageTitle: {
    fontSize: '12px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '0.3px',
  },
  pipelineStageStatusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '4px 0',
  },
  pipelineStatusBadge: {
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.5px',
  },
  pipelineStageCount: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  pipelineStageBtn: {
    padding: '7px 12px',
    borderRadius: '4px',
    border: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.5px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    textAlign: 'center',
  },
  pipelineArrow: {
    fontSize: '18px',
    color: 'var(--text-muted)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  jobCard: {
    backgroundColor: 'var(--bg-tertiary)',
    padding: '20px',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
  },
  jobCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
  },
  jobIdRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  jobTypeBadge: {
    padding: '3px 8px',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid rgba(56, 189, 248, 0.4)',
  },
  jobStatusBadge: {
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid transparent',
  },
  jobIdText: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  priorityTag: {
    padding: '3px 8px',
    backgroundColor: 'rgba(168, 85, 247, 0.15)',
    color: '#c084fc',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid rgba(168, 85, 247, 0.3)',
  },
  workerTag: {
    padding: '3px 8px',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-mono)',
    border: '1px solid rgba(56, 189, 248, 0.25)',
  },
  retryTag: {
    padding: '3px 8px',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    color: 'var(--accent-amber)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    border: '1px solid rgba(245, 158, 11, 0.3)',
  },
  heartbeatText: {
    color: 'var(--accent-green)',
    fontWeight: 500,
  },
  jobActionBtnGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  cancelBtn: {
    padding: '7px 14px',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    color: 'var(--accent-red)',
    border: '1px solid rgba(239, 68, 68, 0.4)',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  retryBtn: {
    padding: '7px 14px',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    color: 'var(--accent-amber)',
    border: '1px solid rgba(245, 158, 11, 0.4)',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  reparseBtn: {
    padding: '7px 14px',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  stageStepper: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
    backgroundColor: 'var(--bg-primary)',
    padding: '10px 14px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    marginBottom: '16px',
    overflowX: 'auto',
  },
  stageStep: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '11px',
    color: 'var(--text-muted)',
    whiteSpace: 'nowrap',
  },
  stageStepActive: {
    color: 'var(--accent-cyan)',
    fontWeight: 700,
  },
  stageStepComplete: {
    color: 'var(--accent-green)',
    fontWeight: 600,
  },
  stageStepBullet: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '18px',
    height: '18px',
    borderRadius: '50%',
    backgroundColor: 'rgba(148, 163, 184, 0.1)',
    fontSize: '10px',
  },
  stageStepLabel: {
    fontSize: '11px',
  },
  telemetryBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    backgroundColor: 'var(--bg-primary)',
    padding: '8px 14px',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    marginBottom: '16px',
    fontSize: '11px',
    flexWrap: 'wrap',
  },
  telemetryItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  telemetryLabel: {
    color: 'var(--text-muted)',
    fontWeight: 600,
  },
  telemetryVal: {
    color: 'var(--text-primary)',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
  },
  prioritySelectorContainer: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '10px',
    margin: '16px 0',
  },
  priorityLabel: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontWeight: 600,
  },
  prioritySelectBtn: {
    padding: '6px 14px',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: '6px',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  prioritySelectBtnActive: {
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    borderColor: 'var(--accent-cyan)',
    fontWeight: 700,
  },
  historyContainer: {
    marginTop: '24px',
    backgroundColor: 'var(--bg-tertiary)',
    padding: '16px 20px',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
  },
  historyTitle: {
    fontSize: '13px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    letterSpacing: '0.5px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  historySubtitle: {
    fontSize: '11px',
    fontWeight: 500,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  historyTableWrapper: {
    overflowX: 'auto',
  },
  historyTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '11px',
  },
  historyTh: {
    textAlign: 'left',
    padding: '8px 10px',
    borderBottom: '1px solid var(--border-color)',
    color: 'var(--text-muted)',
    fontWeight: 600,
    fontSize: '10px',
    letterSpacing: '0.5px',
  },
  historyTr: {
    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
    transition: 'background-color 0.15s ease',
  },
  historyTrActive: {
    backgroundColor: 'rgba(56, 189, 248, 0.08)',
  },
  historyTd: {
    padding: '8px 10px',
    color: 'var(--text-secondary)',
  },
  historyTdMono: {
    padding: '8px 10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  historyPriorityBadge: {
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '10px',
    fontWeight: 600,
    backgroundColor: 'rgba(168, 85, 247, 0.1)',
    color: '#c084fc',
    border: '1px solid rgba(168, 85, 247, 0.2)',
  },
  historyViewBtn: {
    padding: '4px 10px',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-secondary)',
    border: '1px solid var(--border-color)',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  historyViewBtnActive: {
    padding: '4px 10px',
    backgroundColor: 'rgba(56, 189, 248, 0.2)',
    color: 'var(--accent-cyan)',
    border: '1px solid var(--accent-cyan)',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 700,
    cursor: 'default',
  },
  progressContainer: {
    marginBottom: '20px',
  },
  progressBarTrack: {
    width: '100%',
    height: '10px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '5px',
    overflow: 'hidden',
    border: '1px solid var(--border-color)',
  },
  progressBarFill: {
    height: '100%',
    transition: 'width 0.4s ease',
  },
  progressMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginTop: '6px',
  },
  progressPercent: {
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: '12px',
  },
  metricCard: {
    backgroundColor: 'var(--bg-primary)',
    padding: '12px 14px',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
  },
  metricLabel: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    fontWeight: 700,
    letterSpacing: '0.5px',
    marginBottom: '4px',
  },
  metricVal: {
    fontSize: '18px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  metricValPrimary: {
    fontSize: '18px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
  },
  jobErrorBox: {
    marginTop: '16px',
    padding: '12px',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: '6px',
    border: '1px solid rgba(239, 68, 68, 0.3)',
    color: 'var(--accent-red)',
    fontSize: '12px',
  },
  jobErrorTitle: {
    fontWeight: 700,
    marginBottom: '4px',
  },
  summaryCard: {
    backgroundColor: 'var(--bg-tertiary)',
    padding: '20px',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
  },
  summaryTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    marginBottom: '16px',
  },
  artifactGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px',
    marginBottom: '16px',
  },
  categoryCard: {
    backgroundColor: 'var(--bg-primary)',
    padding: '14px',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
  },
  categoryHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
  },
  catIcon: {
    fontSize: '16px',
  },
  catName: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  catCount: {
    fontSize: '20px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  notPresent: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    fontWeight: 400,
    fontStyle: 'italic',
  },
  diagnosticsBox: {
    backgroundColor: 'var(--bg-primary)',
    padding: '12px 14px',
    borderRadius: '6px',
    border: '1px solid rgba(245, 158, 11, 0.3)',
  },
  diagnosticsTitle: {
    fontSize: '12px',
    fontWeight: 700,
    color: 'var(--accent-amber)',
    marginBottom: '6px',
  },
  diagnosticsList: {
    margin: 0,
    paddingLeft: '20px',
    fontSize: '12px',
    color: 'var(--text-secondary)',
  },
  emptyStateCard: {
    padding: '40px',
    textAlign: 'center',
    backgroundColor: 'var(--bg-tertiary)',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
  },
  emptyIcon: {
    fontSize: '36px',
    marginBottom: '12px',
  },
  emptyTitle: {
    fontSize: '16px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    marginBottom: '8px',
  },
  emptyDesc: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    maxWidth: '550px',
    margin: '0 auto 20px auto',
    lineHeight: '1.5',
  },
  primaryActionBtn: {
    padding: '10px 22px',
    backgroundColor: 'var(--accent-cyan)',
    color: '#0a0f1d',
    border: 'none',
    borderRadius: '6px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  chipBar: {
    display: 'flex',
    gap: '8px',
    overflowX: 'auto',
    marginBottom: '16px',
    paddingBottom: '4px',
  },
  chipBtn: {
    padding: '6px 14px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-muted)',
    border: '1px solid var(--border-color)',
    borderRadius: '20px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition: 'all 0.15s ease',
  },
  activeChipBtn: {
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    borderColor: 'var(--accent-cyan)',
  },
  artifactsTableWrapper: {
    backgroundColor: 'var(--bg-tertiary)',
    borderRadius: '8px',
    border: '1px solid var(--border-color)',
    overflow: 'hidden',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    textAlign: 'left',
  },
  th: {
    padding: '12px 14px',
    fontSize: '11px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    borderBottom: '1px solid var(--border-color)',
    backgroundColor: 'var(--bg-primary)',
    letterSpacing: '0.5px',
  },
  tr: {
    borderBottom: '1px solid var(--border-color)',
  },
  td: {
    padding: '12px 14px',
    fontSize: '13px',
    verticalAlign: 'top',
  },
  categoryBadge: {
    padding: '2px 8px',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 700,
    border: '1px solid',
  },
  sourceFile: {
    fontWeight: 600,
    color: 'var(--text-primary)',
    fontSize: '12px',
  },
  sourcePath: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    maxWidth: '220px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  recordId: {
    fontSize: '11px',
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
  },
  previewContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  previewHighlight: {
    color: 'var(--text-primary)',
    fontWeight: 600,
    fontSize: '12px',
  },
  previewSub: {
    color: 'var(--text-muted)',
    fontSize: '11px',
  },
  previewBody: {
    color: 'var(--text-secondary)',
    fontSize: '12px',
    fontStyle: 'italic',
    maxWidth: '300px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  viewPayloadBtn: {
    padding: '5px 10px',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    borderRadius: '4px',
    fontSize: '10px',
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  paginationBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    backgroundColor: 'var(--bg-primary)',
  },
  pageInfo: {
    fontSize: '12px',
    color: 'var(--text-muted)',
  },
  pageBtnGroup: {
    display: 'flex',
    gap: '8px',
  },
  pageBtn: {
    padding: '5px 12px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-color)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  inspectOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.88)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1100,
    padding: '20px',
  },
  inspectModal: {
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '10px',
    border: '1px solid var(--border-color)',
    width: '100%',
    maxWidth: '750px',
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  inspectHeader: {
    padding: '16px 20px',
    backgroundColor: 'var(--bg-tertiary)',
    borderBottom: '1px solid var(--border-color)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  inspectTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: 'var(--text-primary)',
  },
  inspectSub: {
    fontSize: '11px',
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    marginTop: '2px',
  },
  inspectProvenanceCard: {
    margin: '16px 20px 0 20px',
    padding: '12px 16px',
    backgroundColor: 'var(--bg-primary)',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  provRow: {
    display: 'flex',
    gap: '10px',
    fontSize: '12px',
  },
  provLabel: {
    color: 'var(--text-muted)',
    fontWeight: 600,
    minWidth: '110px',
  },
  rawJsonHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    margin: '14px 20px 6px 20px',
  },
  rawJsonLabel: {
    fontSize: '11px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
  },
  copyJsonBtn: {
    padding: '4px 10px',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--accent-cyan)',
    border: '1px solid var(--border-color)',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  rawJsonViewer: {
    margin: '0 20px 16px 20px',
    flex: 1,
    overflowY: 'auto',
    backgroundColor: '#090d16',
    borderRadius: '6px',
    border: '1px solid var(--border-color)',
    padding: '12px',
  },
  jsonPre: {
    margin: 0,
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
    color: '#38bdf8',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  },
  inspectFooter: {
    padding: '14px 20px',
    backgroundColor: 'var(--bg-tertiary)',
    borderTop: '1px solid var(--border-color)',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  actions: {
    padding: '16px 24px',
    borderTop: '1px solid var(--border-color)',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    backgroundColor: 'var(--bg-tertiary)',
  },
  quarantineBtn: {
    padding: '9px 16px',
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    color: 'var(--accent-amber)',
    border: '1px solid rgba(245, 158, 11, 0.4)',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  closeActionBtn: {
    padding: '9px 18px',
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-color)',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  downloadBtn: {
    padding: '9px 18px',
    backgroundColor: 'var(--accent-cyan)',
    color: '#0a0f1d',
    border: 'none',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
  },
};
