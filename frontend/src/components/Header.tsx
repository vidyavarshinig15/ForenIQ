import React, { useEffect, useState } from 'react';
import { useAuth } from '../services/authContext';
import { apiClient } from '../services/api/client';
import type { HealthResponse } from '../types/api';
import type { Case } from '../types/case';

interface HeaderProps {
  activeCase?: Case | null;
  onClearActiveCase?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeCase, onClearActiveCase }) => {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'connected' | 'error'>('checking');
  const [lastChecked, setLastChecked] = useState<string>('');

  const checkHealth = async () => {
    setHealthStatus('checking');
    try {
      const res = await apiClient.getHealth();
      setHealth(res);
      setHealthStatus('connected');
      setLastChecked(new Date().toLocaleTimeString());
    } catch {
      setHealth(null);
      setHealthStatus('error');
      setLastChecked(new Date().toLocaleTimeString());
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header style={styles.header}>
      <div style={styles.brandingSection}>
        <div style={styles.logoBadge}>UFDR</div>
        <div style={styles.titleContainer}>
          <div style={styles.systemTitle}>AI-Driven Intelligent UFDR Analysis System</div>
          <div style={styles.systemSubtitle}>Digital Forensic Investigation Platform</div>
        </div>
        <div style={styles.phaseBadge}>PHASE 2: AUTH & CASES</div>
      </div>

      <div style={styles.statusSection}>
        {/* Active Case Scope Indicator */}
        <div style={styles.chip}>
          <span style={styles.chipLabel}>CASE SCOPE:</span>
          {activeCase ? (
            <div style={styles.activeCaseScope}>
              <span style={styles.chipValueActive}>{activeCase.case_number}</span>
              {onClearActiveCase && (
                <button
                  onClick={onClearActiveCase}
                  style={styles.clearScopeBtn}
                  title="Clear Active Case Scope"
                >
                  ✕
                </button>
              )}
            </div>
          ) : (
            <span style={styles.chipValueMuted}>None (Global)</span>
          )}
        </div>

        {/* Backend API Health Status */}
        <div
          style={styles.healthChip}
          onClick={checkHealth}
          title={`Click to recheck backend health. Last checked: ${lastChecked}`}
        >
          <span
            style={{
              ...styles.healthDot,
              backgroundColor:
                healthStatus === 'connected'
                  ? 'var(--accent-green)'
                  : healthStatus === 'checking'
                  ? 'var(--accent-amber)'
                  : 'var(--accent-rose)',
            }}
          />
          <span style={styles.healthText}>
            API:{' '}
            {healthStatus === 'connected'
              ? `Healthy (${health?.status || 'ok'})`
              : healthStatus === 'checking'
              ? 'Checking...'
              : 'Offline / Disconnected'}
          </span>
        </div>

        {/* User Identity & Logout */}
        {user && (
          <div style={styles.userSection}>
            <div style={styles.userChip}>
              <span style={styles.userName}>{user.name}</span>
              <span style={styles.userRoleBadge}>{user.role}</span>
            </div>
            <button onClick={() => logout()} style={styles.logoutBtn} title="Sign Out">
              LOGOUT
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

const styles: Record<string, React.CSSProperties> = {
  header: {
    height: 'var(--header-height)',
    backgroundColor: 'var(--bg-surface)',
    borderBottom: '1px solid var(--border-subtle)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    flexShrink: 0,
    userSelect: 'none',
  },
  brandingSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  logoBadge: {
    backgroundColor: 'var(--accent-blue)',
    color: '#ffffff',
    fontWeight: 700,
    fontSize: '12px',
    letterSpacing: '1px',
    padding: '4px 8px',
    borderRadius: '4px',
    fontFamily: 'var(--font-mono)',
  },
  titleContainer: {
    display: 'flex',
    flexDirection: 'column',
  },
  systemTitle: {
    fontSize: '13px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    letterSpacing: '0.2px',
  },
  systemSubtitle: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
  phaseBadge: {
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.3)',
    fontSize: '10px',
    fontWeight: 600,
    letterSpacing: '0.5px',
    padding: '2px 8px',
    borderRadius: '12px',
    marginLeft: '6px',
  },
  statusSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  chip: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    backgroundColor: 'var(--bg-card)',
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
    fontSize: '11px',
  },
  chipLabel: {
    color: 'var(--text-muted)',
    fontWeight: 600,
  },
  chipValueMuted: {
    color: 'var(--text-secondary)',
    fontFamily: 'var(--font-mono)',
  },
  chipValueActive: {
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
  },
  activeCaseScope: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  clearScopeBtn: {
    color: 'var(--text-muted)',
    fontSize: '10px',
    padding: '0 4px',
  },
  healthChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    backgroundColor: 'var(--bg-card)',
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
    fontSize: '11px',
    cursor: 'pointer',
  },
  healthDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    display: 'inline-block',
  },
  healthText: {
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
  },
  userSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  userChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: 'var(--bg-card)',
    padding: '4px 10px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
    fontSize: '11px',
  },
  userName: {
    color: 'var(--text-primary)',
    fontWeight: 500,
  },
  userRoleBadge: {
    fontSize: '9px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    padding: '1px 5px',
    borderRadius: '3px',
  },
  logoutBtn: {
    backgroundColor: 'transparent',
    color: 'var(--accent-rose)',
    border: '1px solid rgba(244, 63, 94, 0.3)',
    fontSize: '10px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    padding: '4px 8px',
    borderRadius: '4px',
  },
};
