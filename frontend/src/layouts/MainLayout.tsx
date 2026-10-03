import React, { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { CaseDetailsPage } from '../pages/CaseDetailsPage';
import { CasesPage } from '../pages/CasesPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { SearchPage } from '../components/SearchPage';
import { InvestigatorAssistant } from '../components/InvestigatorAssistant';
import { CommunicationGraphView } from '../components/CommunicationGraphView';
import { TimelineView } from '../components/TimelineView';
import { AnomalyDashboardView } from '../components/AnomalyDashboardView';
import { ReportBuilderView } from '../components/ReportBuilderView';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type { NavigationTab } from '../types/navigation';
import { NAVIGATION_ITEMS } from '../utils/navigationConfig';

export const MainLayout: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavigationTab>('cases');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<Case | null>(null);

  // Load active case details whenever selectedCaseId changes
  useEffect(() => {
    if (selectedCaseId) {
      apiClient
        .getCase(selectedCaseId)
        .then((c) => setActiveCase(c))
        .catch(() => {
          setSelectedCaseId(null);
          setActiveCase(null);
        });
    } else {
      setActiveCase(null);
    }
  }, [selectedCaseId]);

  const handleOpenCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setActiveTab('cases');
  };

  const handleClearCase = () => {
    setSelectedCaseId(null);
    setActiveCase(null);
  };

  const currentItem =
    NAVIGATION_ITEMS.find((item) => item.id === activeTab) || NAVIGATION_ITEMS[0];

  return (
    <div style={styles.layout}>
      <Header activeCase={activeCase} onClearActiveCase={handleClearCase} />
      <div style={styles.body}>
        <Sidebar activeTab={activeTab} onSelectTab={(tab) => {
          setActiveTab(tab);
          // If moving away from cases tab, we keep the active case scope in header
        }} />
        <main style={styles.mainContent}>
          {activeTab === 'cases' ? (
            selectedCaseId ? (
              <CaseDetailsPage caseId={selectedCaseId} onBack={handleClearCase} />
            ) : (
              <CasesPage onOpenCase={handleOpenCase} />
            )
          ) : activeTab === 'evidence' ? (
            selectedCaseId ? (
              <CaseDetailsPage
                caseId={selectedCaseId}
                onBack={handleClearCase}
                initialSubTab="evidence"
              />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>📦</div>
                <h2 style={styles.noCaseTitle}>Forensic Evidence Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  All forensic archives (UFDR and raw phone extractions) must be ingested strictly
                  within an authorized case boundary to enforce RBAC and maintain chain of custody.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT OR CREATE CASE →
                </button>
              </div>
            )
          ) : activeTab === 'search' ? (
            selectedCaseId ? (
              <SearchPage caseId={selectedCaseId} caseData={activeCase} />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>🔍</div>
                <h2 style={styles.noCaseTitle}>Forensic Search Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  All forensic queries and evidence searches are executed strictly within an authorized case boundary to enforce cross-case isolation and maintain audit compliance.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : activeTab === 'investigations' ? (
            selectedCaseId ? (
              <InvestigatorAssistant caseId={selectedCaseId} caseData={activeCase} />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>🤖</div>
                <h2 style={styles.noCaseTitle}>Evidence-Grounded Investigator Assistant</h2>
                <p style={styles.noCaseText}>
                  The AI Investigator Assistant operates strictly within an authorized case boundary to analyze forensic extractions and synthesize evidence-grounded findings with verified citations.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : activeTab === 'graph' ? (
            selectedCaseId ? (
              <CommunicationGraphView caseId={selectedCaseId} caseData={activeCase} />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>🕸️</div>
                <h2 style={styles.noCaseTitle}>Communication Graph Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  Communication network analysis and social network analytics operate strictly within an authorized case boundary to reconstruct verifiable interaction topologies with full evidence traceability.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : activeTab === 'timeline' ? (
            selectedCaseId ? (
              <TimelineView caseId={selectedCaseId} caseData={activeCase} />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>⏱️</div>
                <h2 style={styles.noCaseTitle}>Forensic Timeline Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  Unified multi-source forensic timeline analysis operates strictly within an authorized case boundary to preserve timestamp integrity and provenance across evidence extractions.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : activeTab === 'anomalies' ? (
            selectedCaseId ? (
              <AnomalyDashboardView
                caseId={selectedCaseId}
                caseData={activeCase}
                onNavigateToGraph={() => setActiveTab('graph')}
              />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>📊</div>
                <h2 style={styles.noCaseTitle}>Statistical Anomaly Detection Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  Multidimensional Isolation Forest and behavioral outlier detection operate strictly within an authorized case boundary to identify statistical deviations without making subjective guilt claims.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : activeTab === 'reports' ? (
            selectedCaseId ? (
              <ReportBuilderView caseId={selectedCaseId} />
            ) : (
              <div style={styles.noCasePrompt}>
                <div style={styles.noCaseIcon}>📄</div>
                <h2 style={styles.noCaseTitle}>Forensic Reports Scoped by Case</h2>
                <p style={styles.noCaseText}>
                  Automated forensic report generation synthesizes verified findings, timelines, communication networks, anomalies, and chain-of-custody records into court-ready, SHA-256 signed documents.
                </p>
                <button onClick={() => setActiveTab('cases')} style={styles.selectCaseBtn}>
                  OPEN CASES REGISTRY TO SELECT CASE →
                </button>
              </div>
            )
          ) : (
            <PlaceholderPage item={currentItem} />
          )}
        </main>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  layout: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-primary)',
    overflow: 'hidden',
  },
  body: {
    display: 'flex',
    flex: 1,
    height: 'calc(100vh - var(--header-height))',
    overflow: 'hidden',
  },
  mainContent: {
    flex: 1,
    height: '100%',
    overflowY: 'auto',
    backgroundColor: 'var(--bg-primary)',
  },
  noCasePrompt: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    padding: '32px',
    textAlign: 'center',
    gap: '12px',
  },
  noCaseIcon: {
    fontSize: '48px',
    opacity: 0.6,
  },
  noCaseTitle: {
    fontSize: '18px',
    fontWeight: 700,
    color: 'var(--text-primary)',
    margin: 0,
  },
  noCaseText: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    maxWidth: '480px',
    lineHeight: '1.5',
    margin: 0,
  },
  selectCaseBtn: {
    marginTop: '12px',
    backgroundColor: 'var(--accent-cyan)',
    color: '#000000',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
    letterSpacing: '0.5px',
  },
};
