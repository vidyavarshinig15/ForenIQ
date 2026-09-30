import React from 'react';
import { AuthProvider, useAuth } from './services/authContext';
import { LoginPage } from './pages/LoginPage';
import { MainLayout } from './layouts/MainLayout';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={styles.loadingScreen}>
        <div style={styles.loadingSpinner}>⚙</div>
        <div style={styles.loadingText}>INITIALIZING FORENSIC ENVIRONMENT...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <MainLayout />;
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
    backgroundColor: 'var(--bg-primary)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
  },
  loadingSpinner: {
    fontSize: '28px',
    color: 'var(--accent-cyan)',
    animation: 'spin 2s linear infinite',
  },
  loadingText: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    letterSpacing: '1px',
    color: 'var(--text-muted)',
  },
};

export default App;
