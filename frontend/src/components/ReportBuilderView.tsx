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
        return <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', background: '#064e3b', color: '#6ee7b7', border: '1px solid #059669' }}>✓ APPROVED</span>;
      case 'REVIEW_REQUIRED':
        return <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', background: '#78350f', color: '#fcd34d', border: '1px solid #d97706' }}>⚠ REVIEW REQUIRED</span>;
      case 'EXPORTED':
        return <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', background: '#164e63', color: '#67e8f9', border: '1px solid #0891b2' }}>⬇ EXPORTED</span>;
      case 'ARCHIVED':
        return <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', background: '#1f2937', color: '#9ca3af', border: '1px solid #374151' }}>ARCHIVED</span>;
      default:
        return <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', background: '#334155', color: '#cbd5e1', border: '1px solid #64748b' }}>DRAFT (v{selectedReport?.version || 1})</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '8px', color: '#e2e8f0', fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Top Banner / Title */}
      <div style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)', border: '1px solid #334155', borderRadius: '12px', padding: '20px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', boxShadow: '0 4px 20px rgba(0,0,0,0.4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>📑</span>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.02em' }}>Intelligent Forensic Report Generation</h2>
          </div>
          <p style={{ margin: '6px 0 0 0', fontSize: '13px', color: '#94a3b8' }}>
            Structured, court-ready, evidence-grounded reports with immutable SHA-256 verification and traceable citations.
          </p>
        </div>

        <button
          onClick={fetchReports}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', background: '#1e293b', border: '1px solid #475569', color: '#cbd5e1', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
        >
          🔄 Refresh
        </button>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div style={{ padding: '12px 16px', background: '#450a0a', border: '1px solid #b91c1c', color: '#fca5a5', borderRadius: '8px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>⚠️</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Grid: Generator Options & Existing Reports vs Report Viewer */}
      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '20px' }}>
        {/* Left Column: Report Generation Config & History */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Builder Form Card */}
          <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ paddingBottom: '8px', borderBottom: '1px solid #1e293b', fontSize: '13px', fontWeight: 700, color: '#93c5fd', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>⚙️</span> Generate Forensic Report
            </div>

            <form onSubmit={handleGenerate} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Report Taxonomy</label>
                <select
                  value={reportType}
                  onChange={(e) => setReportType(e.target.value as ReportType)}
                  style={{ width: '100%', background: '#020617', border: '1px solid #334155', borderRadius: '6px', padding: '8px', fontSize: '12px', color: '#f1f5f9' }}
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
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Custom Title (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g., Preliminary Digital Evidence Report"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', background: '#020617', border: '1px solid #334155', borderRadius: '6px', padding: '7px 10px', fontSize: '12px', color: '#f1f5f9' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Time Scope</label>
                  <input
                    type="text"
                    placeholder="All"
                    value={timeRange}
                    onChange={(e) => setTimeRange(e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box', background: '#020617', border: '1px solid #334155', borderRadius: '6px', padding: '6px 8px', fontSize: '11px', color: '#f1f5f9' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Entities Scope</label>
                  <input
                    type="text"
                    placeholder="All"
                    value={targetEntities}
                    onChange={(e) => setTargetEntities(e.target.value)}
                    style={{ width: '100%', boxSizing: 'border-box', background: '#020617', border: '1px solid #334155', borderRadius: '6px', padding: '6px 8px', fontSize: '11px', color: '#f1f5f9' }}
                  />
                </div>
              </div>

              <div style={{ paddingTop: '8px', borderTop: '1px solid #1e293b' }}>
                <span style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '6px', fontWeight: 600 }}>Included Modules</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '11px', color: '#cbd5e1' }}>
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
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Analyst Notes</label>
                <textarea
                  rows={2}
                  placeholder="Optional context or investigation focus..."
                  value={analystNotes}
                  onChange={(e) => setAnalystNotes(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', background: '#020617', border: '1px solid #334155', borderRadius: '6px', padding: '6px 8px', fontSize: '11px', color: '#f1f5f9', resize: 'none' }}
                />
              </div>

              <button
                type="submit"
                disabled={generating}
                style={{ width: '100%', padding: '10px', background: generating ? '#312e81' : '#4f46e5', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: generating ? 'not-allowed' : 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', boxShadow: '0 2px 10px rgba(79, 70, 229, 0.3)' }}
              >
                {generating ? '⏳ Synthesizing Evidence...' : '✨ Generate Structured Report'}
              </button>
            </form>
          </div>

          {/* Report History List */}
          <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '10px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#94a3b8', paddingBottom: '6px', borderBottom: '1px solid #1e293b' }}>
              Generated Reports ({reports.length})
            </div>

            {loadingList ? (
              <div style={{ textAlign: 'center', padding: '16px', color: '#64748b', fontSize: '12px' }}>Loading reports...</div>
            ) : reports.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '16px', color: '#64748b', fontSize: '12px' }}>No reports generated yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
                {reports.map((rep) => (
                  <div
                    key={rep.report_id}
                    onClick={() => loadReportDetails(rep.report_id)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: '6px',
                      border: selectedReport?.report_id === rep.report_id ? '1px solid #6366f1' : '1px solid #1e293b',
                      background: selectedReport?.report_id === rep.report_id ? '#1e1b4b' : '#020617',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '180px' }}>{rep.title}</span>
                      <span style={{ fontSize: '10px', color: '#64748b', fontFamily: 'monospace' }}>v{rep.version}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                      <span>{rep.findings_count} findings • {rep.citations_count} citations</span>
                      <span style={{ color: '#818cf8', fontFamily: 'monospace' }}>{rep.report_id.slice(0, 8)}</span>
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
            <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
              Loading verified forensic report...
            </div>
          ) : !selectedReport ? (
            <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', padding: '40px', textAlign: 'center', color: '#64748b' }}>
              Select or generate a report to inspect evidence findings, timeline, and export court-ready artifacts.
            </div>
          ) : (
            <div style={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 8px 30px rgba(0,0,0,0.5)' }}>
              {/* Report Header Bar */}
              <div style={{ padding: '20px 24px', background: 'linear-gradient(180deg, #020617 0%, #0f172a 100%)', borderBottom: '1px solid #1e293b', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>{selectedReport.title}</h3>
                      {getStatusBadge(selectedReport.status)}
                    </div>
                    <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: '#94a3b8', marginTop: '6px', fontFamily: 'monospace' }}>
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
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', background: '#059669', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}
                      >
                        🛡️ Approve Report
                      </button>
                    )}

                    <a
                      href={apiClient.getReportPdfExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', background: '#4f46e5', color: '#fff', textDecoration: 'none', borderRadius: '6px', fontSize: '12px', fontWeight: 600 }}
                    >
                      ⬇️ Export PDF
                    </a>

                    <a
                      href={apiClient.getReportJsonExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', textDecoration: 'none', borderRadius: '6px', fontSize: '12px' }}
                    >
                      JSON
                    </a>

                    <a
                      href={apiClient.getReportCsvExportUrl(caseId, selectedReport.report_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px', background: '#1e293b', color: '#cbd5e1', border: '1px solid #334155', textDecoration: 'none', borderRadius: '6px', fontSize: '12px' }}
                    >
                      CSV
                    </a>
                  </div>
                </div>

                {/* SHA-256 Hash Display */}
                {selectedReport.report_sha256_hash && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#020617', border: '1px solid #1e293b', padding: '6px 12px', borderRadius: '6px', fontSize: '11px', fontFamily: 'monospace' }}>
                    <span style={{ color: '#10b981' }}>🔒 SHA-256:</span>
                    <span style={{ color: '#6ee7b7', wordBreak: 'break-all' }}>{selectedReport.report_sha256_hash}</span>
                  </div>
                )}
              </div>

              {/* Navigation Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid #1e293b', background: '#020617', padding: '0 16px', gap: '16px', overflowX: 'auto', fontSize: '12px' }}>
                <button
                  onClick={() => setActiveSection('overview')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'overview' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'overview' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Overview & Scope
                </button>
                <button
                  onClick={() => setActiveSection('findings')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'findings' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'findings' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Findings ({selectedReport.findings.length})
                </button>
                <button
                  onClick={() => setActiveSection('timeline')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'timeline' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'timeline' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Timeline ({selectedReport.timeline_entries.length})
                </button>
                <button
                  onClick={() => setActiveSection('graph')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'graph' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'graph' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Network Analysis
                </button>
                <button
                  onClick={() => setActiveSection('anomalies')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'anomalies' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'anomalies' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Anomalies ({selectedReport.anomaly_findings.length})
                </button>
                <button
                  onClick={() => setActiveSection('custody')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'custody' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'custody' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Evidence & Custody
                </button>
                <button
                  onClick={() => setActiveSection('limitations')}
                  style={{ padding: '12px 4px', border: 'none', borderBottom: activeSection === 'limitations' ? '2px solid #6366f1' : '2px solid transparent', background: 'transparent', color: activeSection === 'limitations' ? '#818cf8' : '#94a3b8', cursor: 'pointer', fontWeight: 600 }}
                >
                  Limitations & Notes
                </button>
              </div>

              {/* Tab Content Body */}
              <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* 1. Overview Tab */}
                {activeSection === 'overview' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Case Metadata</h4>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Case Title:</span> {selectedReport.case_info.title}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Case Number:</span> {selectedReport.case_info.case_number}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Investigator:</span> {selectedReport.case_info.lead_investigator || 'N/A'}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Status:</span> {selectedReport.case_info.status}</p>
                      </div>

                      <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Investigation Scope</h4>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Time Range:</span> {String(selectedReport.investigation_scope.time_range || 'Full Span')}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Entities:</span> {String(selectedReport.investigation_scope.target_entities || 'All')}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Software:</span> {selectedReport.software_version}</p>
                        <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Template:</span> {selectedReport.report_template_version}</p>
                      </div>
                    </div>

                    {/* Methodology */}
                    <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Forensic Methodology & Pipelines</h4>
                      <ul style={{ margin: 0, paddingLeft: '18px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', color: '#cbd5e1' }}>
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
                      <p style={{ color: '#64748b', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No analytical findings recorded.</p>
                    ) : (
                      selectedReport.findings.map((f) => (
                        <div key={f.finding_id} style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>{f.title}</h4>
                            <span style={{ fontSize: '10px', fontFamily: 'monospace', padding: '2px 6px', borderRadius: '4px', background: '#1e1b4b', color: '#a5b4fc', border: '1px solid #3730a3' }}>
                              {f.finding_type}
                            </span>
                          </div>
                          <p style={{ margin: 0, fontSize: '12px', color: '#cbd5e1', lineHeight: '1.5' }}>{f.description}</p>

                          {/* Citations Box */}
                          {f.citations.length > 0 && (
                            <div style={{ paddingTop: '8px', borderTop: '1px solid #1e293b', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              <span style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8' }}>Supporting Evidence Citations:</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {f.citations.map((c) => (
                                  <div key={c.citation_id} style={{ padding: '3px 8px', borderRadius: '4px', background: '#0f172a', border: '1px solid #334155', fontSize: '11px', color: '#cbd5e1' }}>
                                    <span style={{ fontWeight: 700, color: '#818cf8', marginRight: '4px' }}>[{c.citation_id}]</span>
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
                      <p style={{ color: '#64748b', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No timeline events recorded.</p>
                    ) : (
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px' }}>
                              <th style={{ padding: '8px 10px' }}>Timestamp</th>
                              <th style={{ padding: '8px 10px' }}>Event</th>
                              <th style={{ padding: '8px 10px' }}>Parties</th>
                              <th style={{ padding: '8px 10px' }}>Summary</th>
                              <th style={{ padding: '8px 10px' }}>Citation</th>
                            </tr>
                          </thead>
                          <tbody style={{ fontFamily: 'monospace' }}>
                            {selectedReport.timeline_entries.map((te, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid #1e293b' }}>
                                <td style={{ padding: '8px 10px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{te.timestamp}</td>
                                <td style={{ padding: '8px 10px', color: '#a5b4fc' }}>{te.event_type}</td>
                                <td style={{ padding: '8px 10px', color: '#cbd5e1' }}>{te.actor || '-'} → {te.target || '-'}</td>
                                <td style={{ padding: '8px 10px', color: '#94a3b8', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{te.content_summary || '-'}</td>
                                <td style={{ padding: '8px 10px', color: '#818cf8' }}>{te.citation_ref}</td>
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
                          <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', display: 'block' }}>Nodes</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>{selectedReport.graph_analysis.total_nodes}</span>
                          </div>
                          <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', display: 'block' }}>Edges</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>{selectedReport.graph_analysis.total_edges}</span>
                          </div>
                          <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', display: 'block' }}>Density</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#818cf8' }}>{selectedReport.graph_analysis.density.toFixed(4)}</span>
                          </div>
                          <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px', textAlign: 'center' }}>
                            <span style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', display: 'block' }}>Communities</span>
                            <span style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>{selectedReport.graph_analysis.detected_communities_count}</span>
                          </div>
                        </div>

                        {selectedReport.graph_analysis.top_centrality_nodes.length > 0 && (
                          <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Top Degree Entities</h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px', fontFamily: 'monospace' }}>
                              {selectedReport.graph_analysis.top_centrality_nodes.map((node, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #1e293b' }}>
                                  <span style={{ color: '#cbd5e1' }}>{node.entity}</span>
                                  <span style={{ color: '#818cf8' }}>Degree: {node.degree} (Centrality: {node.centrality_score})</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <p style={{ color: '#64748b', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No graph analytics included in this report.</p>
                    )}
                  </div>
                )}

                {/* 5. Anomalies Tab */}
                {activeSection === 'anomalies' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {selectedReport.anomaly_findings.length === 0 ? (
                      <p style={{ color: '#64748b', fontSize: '12px', textAlign: 'center', margin: '20px 0' }}>No statistical anomalies detected in this scope.</p>
                    ) : (
                      selectedReport.anomaly_findings.map((a) => (
                        <div key={a.anomaly_id} style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 600, fontSize: '13px', color: '#f8fafc' }}>⚠️ {a.anomaly_type}</span>
                            <span style={{ fontSize: '10px', fontFamily: 'monospace', padding: '2px 6px', borderRadius: '4px', background: '#78350f', color: '#fde68a', border: '1px solid #b45309' }}>
                              Score: {a.anomaly_score.toFixed(3)}
                            </span>
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px', color: '#94a3b8' }}>
                            <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Window:</span> {a.window_timestamp}</p>
                            <p style={{ margin: 0 }}><span style={{ color: '#64748b' }}>Observed:</span> {a.observed_event_count} events (Baseline: {a.baseline_expected_rate.toFixed(1)})</p>
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
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Evidence Inventory</h4>
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', fontFamily: 'monospace' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px' }}>
                              <th style={{ padding: '6px 8px' }}>Evidence No</th>
                              <th style={{ padding: '6px 8px' }}>Filename</th>
                              <th style={{ padding: '6px 8px' }}>SHA-256 Hash</th>
                              <th style={{ padding: '6px 8px' }}>Integrity</th>
                              <th style={{ padding: '6px 8px' }}>Artifacts</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedReport.evidence_inventory.map((ev) => (
                              <tr key={ev.evidence_id} style={{ borderBottom: '1px solid #1e293b' }}>
                                <td style={{ padding: '6px 8px', color: '#818cf8' }}>{ev.evidence_number}</td>
                                <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>{ev.original_filename}</td>
                                <td style={{ padding: '6px 8px', color: '#64748b', fontSize: '10px' }}>{ev.sha256_hash.slice(0, 16)}...</td>
                                <td style={{ padding: '6px 8px', color: '#10b981' }}>{ev.integrity_status}</td>
                                <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>{ev.artifact_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {selectedReport.custody_chain.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '12px', borderTop: '1px solid #1e293b' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Chain of Custody History</h4>
                        <div style={{ overflowX: 'auto' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', fontFamily: 'monospace' }}>
                            <thead>
                              <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px' }}>
                                <th style={{ padding: '6px 8px' }}>Timestamp</th>
                                <th style={{ padding: '6px 8px' }}>Evidence</th>
                                <th style={{ padding: '6px 8px' }}>Action</th>
                                <th style={{ padding: '6px 8px' }}>Custodian</th>
                                <th style={{ padding: '6px 8px' }}>Integrity</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedReport.custody_chain.map((c, i) => (
                                <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                                  <td style={{ padding: '6px 8px', color: '#94a3b8' }}>{c.timestamp}</td>
                                  <td style={{ padding: '6px 8px', color: '#a5b4fc' }}>{c.evidence_number}</td>
                                  <td style={{ padding: '6px 8px', color: '#cbd5e1' }}>{c.action}</td>
                                  <td style={{ padding: '6px 8px', color: '#94a3b8' }}>{c.actor_name}</td>
                                  <td style={{ padding: '6px 8px', color: '#10b981' }}>{c.integrity_verified ? 'VERIFIED' : 'UNVERIFIED'}</td>
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
                    <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Forensic Limitations & Disclaimers</h4>
                      <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {selectedReport.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>

                    <div style={{ background: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h4 style={{ margin: 0, fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>Analyst Notes & Observations</h4>
                        {!editingNotes ? (
                          <button
                            onClick={() => setEditingNotes(true)}
                            style={{ background: 'transparent', border: 'none', color: '#818cf8', fontSize: '11px', cursor: 'pointer', textDecoration: 'underline' }}
                          >
                            Edit Notes
                          </button>
                        ) : (
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              onClick={() => setEditingNotes(false)}
                              style={{ background: 'transparent', border: 'none', color: '#64748b', fontSize: '11px', cursor: 'pointer' }}
                            >
                              Cancel
                            </button>
                            <button
                              onClick={handleSaveNotes}
                              style={{ padding: '3px 8px', background: '#4f46e5', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}
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
                          style={{ width: '100%', boxSizing: 'border-box', background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', padding: '8px', fontSize: '12px', color: '#f1f5f9', resize: 'vertical' }}
                        />
                      ) : (
                        <p style={{ margin: 0, fontSize: '12px', color: '#cbd5e1', whiteSpace: 'pre-wrap' }}>
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
