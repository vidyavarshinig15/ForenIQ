import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './services/authContext';
import { LandingPage } from './pages/LandingPage';
import { MainLayout } from './layouts/MainLayout';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentView, setCurrentView] = useState<'landing' | 'workstation'>('landing');

  // When authentication status changes:
  // If user signs out, ensure they go back to landing page
  useEffect(() => {
    if (!isAuthenticated) {
      setCurrentView('landing');
    }
  }, [isAuthenticated]);

  if (isLoading) {
    return (
      <div style={styles.loadingScreen}>
        <div style={styles.loadingSpinner}>⚙</div>
        <div style={styles.loadingText}>INITIALIZING FORENSIC ENVIRONMENT...</div>
      </div>
    );
  }

  if (currentView === 'landing') {
    return (
      <LandingPage
        onNavigateToWorkstation={() => setCurrentView('workstation')}
      />
    );
  }

  return (
    <MainLayout
      onNavigateToLanding={() => setCurrentView('landing')}
    />
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const styles: Record<string, React.CSSProperties> = {
  loadingScreen: {
    height: '100vh',
    width: '100vw',
    backgroundColor: '#0B1220',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    backgroundImage: 'radial-gradient(rgba(38, 52, 73, 0.4) 1px, transparent 1px)',
    backgroundSize: '24px 24px',
  },
  loadingSpinner: {
    fontSize: '28px',
    color: '#22D3EE',
    animation: 'spin 2s linear infinite',
  },
  loadingText: {
    fontSize: '11px',
    fontFamily: '"IBM Plex Mono", monospace',
    fontWeight: 700,
    letterSpacing: '0.1em',
    color: '#94A3B8',
  },
};

export default App;
