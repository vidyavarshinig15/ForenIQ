import React, { useState, useEffect } from 'react';
import { apiClient } from '../services/api/client';
import type {
  ForensicReportDocument,
  ReportCreateRequest,
  ReportListSummary,
  ReportType,
  ReportStatus,
} from '../types/report';

interface ReportBuilderViewProps {
  caseId: string;
}

export const ReportBuilderView: React.FC<ReportBuilderViewProps> = ({ caseId }) => {
  // State
  const [reports, setReports] = useState<ReportListSummary[]>([]);
  const [selectedReport, setSelectedReport] = useState<ForensicReportDocument | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDoc, setLoadingDoc] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<'overview' | 'findings' | 'timeline' | 'graph' | 'anomalies' | 'custody' | 'limitations'>('overview');

  // Form State
  const [reportType, setReportType] = useState<ReportType>('COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT');
  const [customTitle, setCustomTitle] = useState('');
  const [timeRange, setTimeRange] = useState('');
  const [targetEntities, setTargetEntities] = useState('');
  const [includeEvidenceInventory, setIncludeEvidenceInventory] = useState(true);
  const [includeCustodyChain, setIncludeCustodyChain] = useState(true);
  const [includeTimeline, setIncludeTimeline] = useState(true);
  const [includeGraph, setIncludeGraph] = useState(true);
  const [includeAnomalies, setIncludeAnomalies] = useState(true);
  const [includeRagFindings, setIncludeRagFindings] = useState(true);
  const [analystNotes, setAnalystNotes] = useState('');

  // Editing notes state
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState('');

  // Load existing reports
  const fetchReports = async () => {
    if (!caseId) return;
    setLoadingList(true);
    setErrorMessage(null);
    try {
      const data = await apiClient.listReports(caseId);
      setReports(data);
      if (data.length > 0 && !selectedReport) {
        loadReportDetails(data[0].report_id);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch reports for case');
    } finally {
      setLoadingList(false);
    }
  };

  const loadReportDetails = async (reportId: string) => {
    setLoadingDoc(true);
    setErrorMessage(null);
    try {
      const doc = await apiClient.getReport(caseId, reportId);
      setSelectedReport(doc);
      setNotesDraft(doc.analyst_notes || '');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load report details');
    } finally {
      setLoadingDoc(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [caseId]);

  // Handle generation
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    setErrorMessage(null);
    try {
      const payload: ReportCreateRequest = {
        case_id: caseId,
        report_type: reportType,
        custom_title: customTitle.trim() || undefined,
        time_range: timeRange.trim() || undefined,
        target_entities: targetEntities.trim() || undefined,
        include_evidence_inventory: includeEvidenceInventory,
        include_custody_chain: includeCustodyChain,
        include_timeline: includeTimeline,
        include_graph_analysis: includeGraph,
        include_anomalies: includeAnomalies,
        include_rag_findings: includeRagFindings,
        analyst_notes: analystNotes.trim() || undefined,
      };

      const doc = await apiClient.createReport(caseId, payload);
      setSelectedReport(doc);
      setNotesDraft(doc.analyst_notes || '');
      await fetchReports();
    } catch (err: any) {
      setErrorMessage(err.message || 'Report generation failed');
    } finally {
      setGenerating(false);
    }
  };

  // Handle Approval
  const handleApprove = async () => {
    if (!selectedReport) return;
    try {
      const updated = await apiClient.approveReport(caseId, selectedReport.report_id);
      setSelectedReport(updated);
      await fetchReports();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to approve report');
    }
  };

  // Handle Save Analyst Notes
  const handleSaveNotes = async () => {
    if (!selectedReport) return;
    try {
      const updated = await apiClient.updateReport(caseId, selectedReport.report_id, {
        analyst_notes: notesDraft,
      });
      setSelectedReport(updated);
      setEditingNotes(false);
      await fetchReports();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update analyst notes');
    }
  };

  const getStatusBadge = (status: ReportStatus) => {
    switch (status) {
      case 'APPROVED':
        return <span style={{ padding: '2px 8px', borderRadius: '2px', fontSize: '11px', fontWeight: 700, background: 'rgba(16, 185, 129, 0.1)', color: '#10B981', border: '1px solid #10B981', fontFamily: '"IBM Plex Mono", monospace' }}>✓ APPROVED</span>;
      case 'REVIEW_REQUIRED':
        return <span style={{ padding: '2px 8px', borderRadius: '2px', fontSize: '11px', fontWeight: 700, background: 'rgba(245, 158, 11, 0.1)', color: '#F59E0B', border: '1px solid #F59E0B', fontFamily: '"IBM Plex Mono", monospace' }}>⚠ REVIEW REQUIRED</span>;
      case 'EXPORTED':
        return <span style={{ padding: '2px 8px', borderRadius: '2px', fontSize: '11px', fontWeight: 700, background: 'rgba(34, 211, 238, 0.1)', color: '#22D3EE', border: '1px solid #22D3EE', fontFamily: '"IBM Plex Mono", monospace' }}>⬇ EXPORTED</span>;
      case 'ARCHIVED':
        return <span style={{ padding: '2px 8px', borderRadius: '2px', fontSize: '11px', fontWeight: 700, background: '#111827', color: '#64748B', border: '1px solid #263449', fontFamily: '"IBM Plex Mono", monospace' }}>ARCHIVED</span>;
      default:
        return <span style={{ padding: '2px 8px', borderRadius: '2px', fontSize: '11px', fontWeight: 700, background: '#1E293B', color: '#94A3B8', border: '1px solid #263449', fontFamily: '"IBM Plex Mono", monospace' }}>DRAFT (v{selectedReport?.version || 1})</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '8px', color: '#F8FAFC', fontFamily: '"IBM Plex Sans", sans-serif' }}>
      {/* Top Banner / Title */}
      <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '4px', padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '20px', color: '#22D3EE' }}>📑</span>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: '#F8FAFC', letterSpacing: '-0.02em', fontFamily: '"Space Grotesk", sans-serif' }}>Intelligent Forensic Report Generation</h2>
          </div>
          <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: '#94A3B8' }}>
            Structured, court-ready, evidence-grounded reports with immutable SHA-256 verification and traceable citations.
          </p>
        </div>

        <button
          onClick={fetchReports}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', background: '#172033', border: '1px solid #263449', color: '#94A3B8', borderRadius: '2px', cursor: 'pointer', fontSize: '12px', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div style={{ padding: '12px 16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #EF4444', color: '#EF4444', borderRadius: '2px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: '"IBM Plex Mono", monospace' }}>
          <span>⚠️</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Grid: Generator Options & Existing Reports vs Report Viewer */}
      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px' }}>
        {/* Left Column: Report Generation Config & History */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Builder Form Card */}
          <div style={{ background: '#172033', border: '1px solid #263449', borderRadius: '4px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ paddingBottom: '8px', borderBottom: '1px solid #263449', fontSize: '13px', fontWeight: 700, color: '#22D3EE', display: 'flex', alignItems: 'center', gap: '6px', fontFamily: '"Space Grotesk", sans-serif' }}>
              <span>⚙️</span> Generate Forensic Report
            </div>

            <form onSubmit={handleGenerate} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '4px', fontFamily: '"IBM Plex Mono", monospace', fontWeight: 700 }}>Report Taxonomy</label>
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value as ReportType)}
                  style={{ width: '100%', background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '8px', fontSize: '12px', color: '#F8FAFC', fontFamily: '"IBM Plex Sans", sans-serif' }}
                >
                  <option value="COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT">Comprehensive Forensic Analysis</option>
                  <option value="TIMELINE_REPORT">Timeline & Chronology Report</option>
                  <option value="COMMUNICATION_ANALYSIS_REPORT">Communication Network Report</option>
                  <option value="ANOMALY_ANALYSIS_REPORT">Anomaly & Statistical Report</option>
                  <option value="EVIDENCE_SUMMARY">Evidence & Hash Summary</option>
                  <option value="CASE_SUMMARY">Executive Case Summary</option>
                  <option value="INVESTIGATION_QUERY_REPORT">Investigation Query Findings</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '4px', fontFamily: '"IBM Plex Mono", monospace', fontWeight: 700 }}>Custom Title (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g., Preliminary Digital Evidence Report"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '7px 10px', fontSize: '12px', color: '#F8FAFC', fontFamily: '"IBM Plex Sans", sans-serif' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '4px', fontFamily: '"IBM Plex Mono", monospace', fontWeight: 700 }}>Time Scope</label>
                  <input
                    type="text"
                    placeholder="All"
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box', background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '6px 8px', fontSize: '11px', color: '#F8FAFC', fontFamily: '"IBM Plex Mono", monospace' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '4px', fontFamily: '"IBM Plex Mono", monospace', fontWeight: 700 }}>Entities Scope</label>
                  <input
                    type="text"
                    placeholder="All"
                    value={targetEntities}
                    onChange={(e) => setTargetEntities(e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box', background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '6px 8px', fontSize: '11px', color: '#F8FAFC', fontFamily: '"IBM Plex Sans", sans-serif' }}
                  />
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: '1px solid #263449' }}>
                <span style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '6px', fontWeight: 700, fontFamily: '"IBM Plex Mono", monospace' }}>Included Modules</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px', color: '#94A3B8' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeEvidenceInventory}
                      onChange={(e) => setIncludeEvidenceInventory(e.target.checked)}
                    />
                    Evidence & Hashes
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeCustodyChain}
                      onChange={(e) => setIncludeCustodyChain(e.target.checked)}
                    />
                    Custody Chain
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeTimeline}
                      onChange={(e) => setIncludeTimeline(e.target.checked)}
                    />
                    Timeline Events
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeGraph}
                      onChange={(e) => setIncludeGraph(e.target.checked)}
                    />
                    Graph Analytics
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeAnomalies}
                      onChange={(e) => setIncludeAnomalies(e.target.checked)}
                    />
                    Anomalies
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={includeRagFindings}
                      onChange={(e) => setIncludeRagFindings(e.target.checked)}
                    />
                    RAG Grounding
                  </label>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#64748B', marginBottom: '4px', fontFamily: '"IBM Plex Mono", monospace', fontWeight: 700 }}>Analyst Notes</label>
                <textarea
                  rows={2}
                  placeholder="Optional context or investigation focus..."
                  value={analystNotes}
                  onChange={(e) => setAnalystNotes(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '6px 8px', fontSize: '11px', color: '#F8FAFC', resize: 'none', fontFamily: '"IBM Plex Sans", sans-serif' }}
                />
              </div>

              <button
                type="submit"
                disabled={generating}
                style={{ width: '100%', padding: '10px', background: generating ? '#1E293B' : '#22D3EE', color: generating ? '#94A3B8' : '#0B1220', border: 'none', borderRadius: '2px', fontSize: '12px', fontWeight: 700, cursor: generating ? 'not-allowed' : 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', fontFamily: '"Space Grotesk", sans-serif', letterSpacing: '0.05em' }}
              >
                {generating ? '⏳ Synthesizing Evidence...' : '⚡ Generate Structured Report'}
              </button>
            </form>
          </div>

          {/* Report History List */}
          <div style={{ background: '#172033', border: '1px solid #263449', borderRadius: '4px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', paddingBottom: '6px', borderBottom: '1px solid #263449', fontFamily: '"IBM Plex Mono", monospace', letterSpacing: '0.05em' }}>
              GENERATED REPORTS ({reports.length})
            </div>

            {loadingList ? (
              <div style={{ textAlign: 'center', padding: '16px', color: '#64748B', fontSize: '12px' }}>Loading reports...</div>
            ) : reports.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '16px', color: '#64748B', fontSize: '12px' }}>No reports generated yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
                {reports.map((rep) => (
                  <div
                    key={rep.report_id}
                    onClick={() => loadReportDetails(rep.report_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '2px',
                      border: selectedReport?.report_id === rep.report_id ? '1px solid #22D3EE' : '1px solid #263449',
                      background: selectedReport?.report_id === rep.report_id ? 'rgba(34, 211, 238, 0.08)' : '#111827',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#F8FAFC', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>{rep.title}</span>
                      <span style={{ fontSize: '10px', color: '#64748B', fontFamily: '"IBM Plex Mono", monospace' }}>v{rep.version}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94A3B8', marginTop: '4px' }}>
                      <span>{rep.findings_count} findings • {rep.citations_count} citations</span>
                      <span style={{ color: '#22D3EE', fontFamily: '"IBM Plex Mono", monospace' }}>{rep.report_id.slice(0, 8)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Report Viewer & Court Export Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {loadingDoc ? (
            <div style={{ background: '#172033', border: '1px solid #263449', borderRadius: '4px', padding: '40px', textAlign: 'center', color: '#94A3B8', fontFamily: '"IBM Plex Mono", monospace' }}>
              Loading verified forensic report...
            </div>
          ) : !selectedReport ? (
            <div style={{ background: '#172033', border: '1px solid #263449', borderRadius: '4px', padding: '40px', textAlign: 'center', color: '#64748B' }}>
              Select or generate a report to inspect evidence findings, timeline, and export court-ready artifacts.
            </div>
          ) : (
            <div style={{ background: '#172033', border: '1px solid #263449', borderRadius: '4px', overflow: 'hidden' }}>
              {/* Report Header Bar */}
              <div style={{ padding: '20px 24px', background: '#111827', borderBottom: '1px solid #263449', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#F8FAFC', fontFamily: '"Space Grotesk", sans-serif' }}>{selectedReport.title}</h3>
                      {getStatusBadge(selectedReport.status)}
                    </div>
                    <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: '#94A3B8', marginTop: '6px', fontFamily: '"IBM Plex Mono", monospace' }}>
                      <span>ID: {selectedReport.report_id}</span>
                      <span>Case: {selectedReport.case_info.case_number}</span>
                      <span>By: {selectedReport.generated_by_name}</span>
                    </div>
                  </div>

                  {/* Export & Action Buttons */}
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {selectedReport.status !== 'APPROVED' && (
                      <button
                        onClick={handleApprove}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', background: '#10B981', color: '#0B1220', border: 'none', borderRadius: '2px', fontSize: '12px', fontWeight: 700, cursor: 'pointer', fontFamily: '"Space Grotesk", sans-serif' }}
                      >
                        🛡️ Approve Report
                      </button>
                    )}

                    <a
                      href={apiClient.getReportPdfExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', background: '#22D3EE', color: '#0B1220', textDecoration: 'none', borderRadius: '2px', fontSize: '12px', fontWeight: 700, fontFamily: '"Space Grotesk", sans-serif' }}
                    >
                      ⬇️ Export PDF
                    </a>

                    <a
                      href={apiClient.getReportJsonExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', background: '#1E293B', color: '#F8FAFC', border: '1px solid #263449', textDecoration: 'none', borderRadius: '2px', fontSize: '12px', fontFamily: '"IBM Plex Mono", monospace' }}
                    >
                      JSON
                    </a>

                    <a
                      href={apiClient.getReportCsvExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', background: '#1E293B', color: '#F8FAFC', border: '1px solid #263449', textDecoration: 'none', borderRadius: '2px', fontSize: '12px', fontFamily: '"IBM Plex Mono", monospace' }}
                    >
                      CSV
                    </a>
                  </div>
                </div>

                {/* SHA-256 Hash Display */}
                {selectedReport.report_sha256_hash && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#0B1220', border: '1px solid #263449', padding: '6px 12px', borderRadius: '2px', fontSize: '11px', fontFamily: '"IBM Plex Mono", monospace' }}>
                    <span style={{ color: '#10B981', fontWeight: 700 }}>🔒 SHA-256:</span>
                    <span style={{ color: '#22D3EE', wordBreak: 'break-all' }}>{selectedReport.report_sha256_hash}</span>
                  </div>
                )}
              </div>

              {/* Navigation Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid #263449', background: '#111827', padding: '0 16px', gap: '16px', overflowX: 'auto', fontSize: '12px' }}>
                <button
                  onClick={() => setActiveSection('overview')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'overview' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'overview' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Overview & Scope
                </button>
                <button
                  onClick={() => setActiveSection('findings')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'findings' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'findings' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Findings ({selectedReport.findings.length})
                </button>
                <button
                  onClick={() => setActiveSection('timeline')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'timeline' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'timeline' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Timeline ({selectedReport.timeline_entries.length})
                </button>
                <button
                  onClick={() => setActiveSection('graph')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'graph' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'graph' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Network Analysis
                </button>
                <button
                  onClick={() => setActiveSection('anomalies')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'anomalies' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'anomalies' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Anomalies ({selectedReport.anomaly_findings.length})
                </button>
                <button
                  onClick={() => setActiveSection('custody')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'custody' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'custody' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Evidence & Custody
                </button>
                <button
                  onClick={() => setActiveSection('limitations')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'limitations' ? '2px solid #22D3EE' : '2px solid transparent', background: 'transparent', color: activeSection === 'limitations' ? '#22D3EE' : '#94A3B8', cursor: 'pointer', fontWeight: 600, fontFamily: '"Space Grotesk", sans-serif' }}
                >
                  Limitations & Notes
                </button>
              </div>

              {/* Tab Content Body */}
              <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', backgroundColor: '#172033' }}>
                {/* 1. Overview Tab */}
                {activeSection === 'overview' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Case Metadata</h4>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Case Title:</span> {selectedReport.case_info.title}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Case Number:</span> <span style={{ color: '#22D3EE', fontFamily: '"IBM Plex Mono", monospace' }}>{selectedReport.case_info.case_number}</span></p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Investigator:</span> {selectedReport.case_info.lead_investigator || 'N/A'}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Status:</span> {selectedReport.case_info.status}</p>
                      </div>

                      <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Investigation Scope</h4>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Time Range:</span> {String(selectedReport.investigation_scope.time_range || 'Full Span')}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Entities:</span> {String(selectedReport.investigation_scope.target_entities || 'All')}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Software:</span> {selectedReport.software_version}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Template:</span> {selectedReport.report_template_version}</p>
                      </div>
                    </div>

                    {/* Methodology */}
                    <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Forensic Methodology & Pipelines</h4>
                      <ul style={{ margin: 0, paddingLeft: '18px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', color: '#94A3B8' }}>
                        {selectedReport.methodology_used.map((m, idx) => (
                          <li key={idx}>{m}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* 2. Findings & Citations Tab */}
                {activeSection === 'findings' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {selectedReport.findings.length === 0 ? (
                      <p style={{ color: '#64748B', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No analytical findings recorded.</p>
                    ) : (
                      selectedReport.findings.map((f) => (
                        <div key={f.finding_id} style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#F8FAFC', fontFamily: '"Space Grotesk", sans-serif' }}>{f.title}</h4>
                            <span style={{ fontSize: '10px', fontFamily: '"IBM Plex Mono", monospace', padding: '2px 6px', borderRadius: '2px', background: 'rgba(59, 130, 246, 0.1)', color: '#3B82F6', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                              {f.finding_type}
                            </span>
                          </div>
                          <p style={{ margin: 0, fontSize: '12px', color: '#94A3B8', lineHeight: '1.5' }}>{f.description}</p>

                          {/* Citations Box */}
                          {f.citations.length > 0 && (
                            <div style={{ paddingTop: '8px', borderTop: '1px solid #263449', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace' }}>Supporting Evidence Citations:</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {f.citations.map((c) => (
                                  <div key={c.citation_id} style={{ padding: '3px 8px', borderRadius: '2px', background: 'rgba(34, 211, 238, 0.08)', border: '1px solid #22D3EE', fontSize: '11px', color: '#F8FAFC' }}>
                                    <span style={{ fontWeight: 700, color: '#22D3EE', marginRight: '4px', fontFamily: '"IBM Plex Mono", monospace' }}>[{c.citation_id}]</span>
                                    <span>{c.evidence_number}: {c.summary}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* 3. Timeline Tab */}
                {activeSection === 'timeline' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {selectedReport.timeline_entries.length === 0 ? (
                      <p style={{ color: '#64748B', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No timeline events recorded.</p>
                    ) : (
                      <div style={{ overflowX: 'auto', border: '1px solid #263449', borderRadius: '2px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left' }}>
                          <thead>
                            <tr style={{ background: '#1E293B', borderBottom: '1px solid #263449', color: '#94A3B8', textTransform: 'uppercase', fontSize: '10px', fontFamily: '"IBM Plex Mono", monospace' }}>
                              <th style={{ padding: '8px 10px' }}>Timestamp</th>
                              <th style={{ padding: '8px 10px' }}>Event</th>
                              <th style={{ padding: '8px 10px' }}>Parties</th>
                              <th style={{ padding: '8px 10px' }}>Summary</th>
                              <th style={{ padding: '8px 10px' }}>Citation</th>
                            </tr>
                          </thead>
                          <tbody style={{ fontFamily: '"IBM Plex Mono", monospace', backgroundColor: '#111827' }}>
                            {selectedReport.timeline_entries.map((te, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid #263449' }}>
                                <td style={{ padding: '8px 10px', color: '#94A3B8', whiteSpace: 'nowrap' }}>{te.timestamp}</td>
                                <td style={{ padding: '8px 10px', color: '#3B82F6' }}>{te.event_type}</td>
                                <td style={{ padding: '8px 10px', color: '#F8FAFC' }}>{te.actor || '-'} → {te.target || '-'}</td>
                                <td style={{ padding: '8px 10px', color: '#94A3B8', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{te.content_summary || '-'}</td>
                                <td style={{ padding: '8px 10px', color: '#22D3EE' }}>{te.citation_ref}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. Graph Tab */}
                {activeSection === 'graph' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {selectedReport.graph_analysis ? (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
                          <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase', display: 'block' }}>Nodes</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#F8FAFC', fontFamily: '"IBM Plex Mono", monospace' }}>{selectedReport.graph_analysis.total_nodes}</span>
                          </div>
                          <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase', display: 'block' }}>Edges</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#F8FAFC', fontFamily: '"IBM Plex Mono", monospace' }}>{selectedReport.graph_analysis.total_edges}</span>
                          </div>
                          <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase', display: 'block' }}>Density</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#22D3EE', fontFamily: '"IBM Plex Mono", monospace' }}>{selectedReport.graph_analysis.density.toFixed(4)}</span>
                          </div>
                          <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase', display: 'block' }}>Communities</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#F8FAFC', fontFamily: '"IBM Plex Mono", monospace' }}>{selectedReport.graph_analysis.detected_communities_count}</span>
                          </div>
                        </div>

                        {selectedReport.graph_analysis.top_centrality_nodes.length > 0 && (
                          <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Top Degree Entities</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', fontFamily: '"IBM Plex Mono", monospace' }}>
                              {selectedReport.graph_analysis.top_centrality_nodes.map((node, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #263449' }}>
                                  <span style={{ color: '#F8FAFC' }}>{node.entity}</span>
                                  <span style={{ color: '#22D3EE' }}>Degree: {node.degree} (Centrality: {node.centrality_score})</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <p style={{ color: '#64748B', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No graph analytics included in this report.</p>
                    )}
                  </div>
                )}

                {/* 5. Anomalies Tab */}
                {activeSection === 'anomalies' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {selectedReport.anomaly_findings.length === 0 ? (
                      <p style={{ color: '#64748B', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No statistical anomalies detected in this scope.</p>
                    ) : (
                      selectedReport.anomaly_findings.map((a) => (
                        <div key={a.anomaly_id} style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: '13px', color: '#F8FAFC' }}>⚠️ {a.anomaly_type}</span>
                            <span style={{ fontSize: '10px', fontFamily: '"IBM Plex Mono", monospace', padding: '2px 6px', borderRadius: '2px', background: 'rgba(245, 158, 11, 0.1)', color: '#F59E0B', border: '1px solid #F59E0B' }}>
                              Score: {a.anomaly_score.toFixed(3)}
                            </span>
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px', color: '#94A3B8' }}>
                            <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Window:</span> {a.window_timestamp}</p>
                            <p style={{ margin: 0 }}><span style={{ color: '#64748B' }}>Observed:</span> {a.observed_event_count} events (Baseline: {a.baseline_expected_rate.toFixed(1)})</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* 6. Evidence & Custody Tab */}
                {activeSection === 'custody' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Evidence Inventory</h4>
                      <div style={{ overflowX: 'auto', border: '1px solid #263449', borderRadius: '2px' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', fontFamily: '"IBM Plex Mono", monospace' }}>
                          <thead>
                            <tr style={{ background: '#1E293B', borderBottom: '1px solid #263449', color: '#94A3B8', textTransform: 'uppercase', fontSize: '10px' }}>
                              <th style={{ padding: '6px 8px' }}>Evidence No</th>
                              <th style={{ padding: '6px 8px' }}>Filename</th>
                              <th style={{ padding: '6px 8px' }}>SHA-256 Hash</th>
                              <th style={{ padding: '6px 8px' }}>Integrity</th>
                              <th style={{ padding: '6px 8px' }}>Artifacts</th>
                            </tr>
                          </thead>
                          <tbody style={{ backgroundColor: '#111827' }}>
                            {selectedReport.evidence_inventory.map((ev) => (
                              <tr key={ev.evidence_id} style={{ borderBottom: '1px solid #263449' }}>
                                <td style={{ padding: '6px 8px', color: '#22D3EE' }}>{ev.evidence_number}</td>
                                <td style={{ padding: '6px 8px', color: '#F8FAFC' }}>{ev.original_filename}</td>
                                <td style={{ padding: '6px 8px', color: '#64748B', fontSize: '10px' }}>{ev.sha256_hash.slice(0, 16)}...</td>
                                <td style={{ padding: '6px 8px', color: '#10B981' }}>{ev.integrity_status}</td>
                                <td style={{ padding: '6px 8px', color: '#F8FAFC' }}>{ev.artifact_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {selectedReport.custody_chain.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '12px', borderTop: '1px solid #263449' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Chain of Custody History</h4>
                        <div style={{ overflowX: 'auto', border: '1px solid #263449', borderRadius: '2px' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', fontFamily: '"IBM Plex Mono", monospace' }}>
                            <thead>
                              <tr style={{ background: '#1E293B', borderBottom: '1px solid #263449', color: '#94A3B8', textTransform: 'uppercase', fontSize: '10px' }}>
                                <th style={{ padding: '6px 8px' }}>Timestamp</th>
                                <th style={{ padding: '6px 8px' }}>Evidence</th>
                                <th style={{ padding: '6px 8px' }}>Action</th>
                                <th style={{ padding: '6px 8px' }}>Custodian</th>
                                <th style={{ padding: '6px 8px' }}>Integrity</th>
                              </tr>
                            </thead>
                            <tbody style={{ backgroundColor: '#111827' }}>
                              {selectedReport.custody_chain.map((c, i) => (
                                <tr key={i} style={{ borderBottom: '1px solid #263449' }}>
                                  <td style={{ padding: '6px 8px', color: '#94A3B8' }}>{c.timestamp}</td>
                                  <td style={{ padding: '6px 8px', color: '#22D3EE' }}>{c.evidence_number}</td>
                                  <td style={{ padding: '6px 8px', color: '#F8FAFC' }}>{c.action}</td>
                                  <td style={{ padding: '6px 8px', color: '#94A3B8' }}>{c.actor_name}</td>
                                  <td style={{ padding: '6px 8px', color: '#10B981' }}>{c.integrity_verified ? 'VERIFIED' : 'UNVERIFIED'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 7. Limitations & Notes Tab */}
                {activeSection === 'limitations' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Forensic Limitations & Disclaimers</h4>
                      <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#94A3B8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {selectedReport.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>

                    <div style={{ background: '#111827', border: '1px solid #263449', borderRadius: '2px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#64748B', fontFamily: '"IBM Plex Mono", monospace', textTransform: 'uppercase' }}>Analyst Notes & Observations</h4>
                        {!editingNotes ? (
                          <button
                            onClick={() => setEditingNotes(true)}
                            style={{ background: 'transparent', border: 'none', color: '#22D3EE', fontSize: '11px', cursor: 'pointer', textDecoration: 'underline', fontFamily: '"Space Grotesk", sans-serif' }}
                          >
                            Edit Notes
                          </button>
                        ) : (
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              onClick={() => setEditingNotes(false)}
                              style={{ background: 'transparent', border: 'none', color: '#64748B', fontSize: '11px', cursor: 'pointer' }}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleSaveNotes}
                              style={{ padding: '3px 8px', background: '#22D3EE', color: '#0B1220', border: 'none', borderRadius: '2px', fontSize: '11px', cursor: 'pointer', fontWeight: 700, fontFamily: '"Space Grotesk", sans-serif' }}
                            >
                              Save
                            </button>
                          </div>
                        )}
                      </div>

                      {editingNotes ? (
                        <textarea
                          rows={4}
                          value={notesDraft}
                          onChange={(e) => setNotesDraft(e.target.value)}
                          style={{ width: '100%', boxSizing: 'border-box', background: '#0B1220', border: '1px solid #263449', borderRadius: '2px', padding: '8px', fontSize: '12px', color: '#F8FAFC', resize: 'vertical', fontFamily: '"IBM Plex Sans", sans-serif' }}
                        />
                      ) : (
                        <p style={{ margin: 0, fontSize: '12px', color: '#F8FAFC', whiteSpace: 'pre-wrap' }}>
                          {selectedReport.analyst_notes || 'No analyst notes recorded.'}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
