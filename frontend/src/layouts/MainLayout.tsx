import React, { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { CaseDetailsPage } from '../pages/CaseDetailsPage';
import { CasesPage } from '../pages/CasesPage';
import { DashboardPage } from '../pages/DashboardPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { SearchPage } from '../components/SearchPage';
import { InvestigatorAssistant } from '../components/InvestigatorAssistant';
import { CommunicationGraphView } from '../components/CommunicationGraphView';
import { TimelineView } from '../components/TimelineView';
import { AnomalyDashboardView } from '../components/AnomalyDashboardView';
import { ReportBuilderView } from '../components/ReportBuilderView';
import { AuditLogsPage } from '../pages/AuditLogsPage';
import { SettingsPage } from '../pages/SettingsPage';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type { NavigationTab } from '../types/navigation';
import { NAVIGATION_ITEMS } from '../utils/navigationConfig';

interface MainLayoutProps {
  onNavigateToLanding?: () => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ onNavigateToLanding }) => {
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
      <Header
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
        activeCase={activeCase}
        onClearActiveCase={handleClearCase}
        onNavigateToLanding={onNavigateToLanding}
        onNewCase={() => {
          setSelectedCaseId(null);
          setActiveTab('cases');
        }}
      />
      <div style={styles.body}>
        <Sidebar activeTab={activeTab} onSelectTab={(tab) => {
          setActiveTab(tab);
          // If moving away from cases tab, we keep the active case scope in header
        }} />
        <main style={styles.mainContent}>
          {activeTab === 'dashboard' ? (
            <DashboardPage
              onOpenCase={(caseId) => { setSelectedCaseId(caseId); setActiveTab('cases'); }}
              onNavigate={(tab) => setActiveTab(tab as NavigationTab)}
            />
          ) : activeTab === 'cases' ? (
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
          ) : activeTab === 'audit' ? (
            <AuditLogsPage />
          ) : activeTab === 'settings' ? (
            <SettingsPage />
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
    backgroundColor: '#0B1220',
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
    backgroundColor: '#0B1220',
    backgroundImage: `
      linear-gradient(to right, rgba(38, 52, 73, 0.15) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(38, 52, 73, 0.15) 1px, transparent 1px)
    `,
    backgroundSize: '32px 32px',
  },
  noCasePrompt: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    padding: '40px',
    textAlign: 'center',
    gap: '14px',
  },
  noCaseIcon: {
    fontSize: '42px',
    color: '#22D3EE',
    opacity: 0.8,
  },
  noCaseTitle: {
    fontSize: '20px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    color: '#F8FAFC',
    margin: 0,
    letterSpacing: '-0.3px',
  },
  noCaseText: {
    fontSize: '13px',
    fontFamily: "'IBM Plex Sans', sans-serif",
    color: '#94A3B8',
    maxWidth: '520px',
    lineHeight: '1.6',
    margin: 0,
  },
  selectCaseBtn: {
    marginTop: '10px',
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    border: '1px solid #22D3EE',
    padding: '10px 22px',
    borderRadius: '2px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: "'IBM Plex Mono', monospace",
    cursor: 'pointer',
    letterSpacing: '0.8px',
    boxShadow: '0 4px 14px rgba(34, 211, 238, 0.25)',
  },
};
