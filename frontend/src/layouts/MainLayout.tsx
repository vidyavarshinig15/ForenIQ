import React, { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { Sidebar } from '../components/Sidebar';
import { CaseDetailsPage } from '../pages/CaseDetailsPage';
import { CasesPage } from '../pages/CasesPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
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
};
