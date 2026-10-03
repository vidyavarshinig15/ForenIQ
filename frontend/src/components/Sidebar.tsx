import React from 'react';
import type { NavigationItem, NavigationTab } from '../types/navigation';
import { NAVIGATION_ITEMS } from '../utils/navigationConfig';

interface SidebarProps {
  activeTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onSelectTab }) => {
  const categories: Array<NavigationItem['category']> = ['Core', 'Forensic Analysis', 'Governance'];

  return (
    <aside style={styles.sidebar}>
      {/* Workspace Header */}
      <div style={styles.sidebarHeader}>
        <div style={styles.workspacePill}>
          <span style={styles.pulseDot} />
          <span style={styles.workspaceLabel}>Forensic Console</span>
        </div>
        <div style={styles.activeProfile}>Session Active & Encrypted</div>
      </div>

      {/* Navigation Groups */}
      <nav style={styles.navContainer}>
        {categories.map((category) => {
          const items = NAVIGATION_ITEMS.filter((item) => item.category === category);
          return (
            <div key={category} style={styles.categoryGroup}>
              <div style={styles.categoryTitle}>{category}</div>
              <div style={styles.itemList}>
                {items.map((item) => {
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => onSelectTab(item.id)}
                      style={{
                        ...styles.navItem,
                        backgroundColor: isActive ? 'rgba(34, 211, 238, 0.1)' : 'transparent',
                        color: isActive ? '#22D3EE' : '#94A3B8',
                        fontWeight: isActive ? 600 : 500,
                        border: isActive ? '1px solid rgba(34, 211, 238, 0.25)' : '1px solid transparent',
                      }}
                    >
                      <span style={{
                        ...styles.itemIcon,
                        color: isActive ? '#22D3EE' : '#64748B',
                      }}>
                        {renderNavIcon(item.id)}
                      </span>
                      <span style={styles.itemLabel}>{item.label}</span>
                      {isActive && <span style={styles.activeIndicator} />}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Sidebar Footer Integrity Standard */}
      <div style={styles.sidebarFooter}>
        <div style={styles.footerNotice}>
          <div style={styles.noticeHeader}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
            <span style={styles.noticeTitle}>Integrity Standard</span>
          </div>
          <div style={styles.noticeBody}>
            ISO/IEC 27037 chain of custody & non-accusatory findings strictly enforced.
          </div>
        </div>
      </div>
    </aside>
  );
};

function renderNavIcon(tab: NavigationTab) {
  switch (tab) {
    case 'dashboard':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="7" height="9" x="3" y="3" rx="1" />
          <rect width="7" height="5" x="14" y="3" rx="1" />
          <rect width="7" height="9" x="14" y="12" rx="1" />
          <rect width="7" height="5" x="3" y="16" rx="1" />
        </svg>
      );
    case 'cases':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
        </svg>
      );
    case 'evidence':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z" />
          <path d="m3.3 7 8.7 5 8.7-5" />
          <path d="M12 22V12" />
        </svg>
      );
    case 'investigations':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 8V4H8" />
          <rect width="16" height="12" x="4" y="8" rx="2" />
          <path d="M2 14h2" />
          <path d="M20 14h2" />
          <path d="M15 13v2" />
          <path d="M9 13v2" />
        </svg>
      );
    case 'search':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
      );
    case 'timeline':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case 'graph':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <line x1="8.59" x2="15.42" y1="13.51" y2="17.49" />
          <line x1="15.41" x2="8.59" y1="6.51" y2="10.49" />
        </svg>
      );
    case 'anomalies':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="m13 2-2 10h9L7 22l2-10H0Z" />
        </svg>
      );
    case 'reports':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
    case 'audit':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      );
    case 'settings':
      return (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    default:
      return null;
  }
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: '260px',
    backgroundColor: '#111827',
    borderRight: '1px solid rgba(38, 52, 73, 0.8)',
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 62px)',
    flexShrink: 0,
    userSelect: 'none',
  },
  sidebarHeader: {
    padding: '16px 18px 14px 18px',
    borderBottom: '1px solid rgba(38, 52, 73, 0.6)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  workspacePill: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
  },
  pulseDot: {
    width: '7px',
    height: '7px',
    borderRadius: '50%',
    backgroundColor: '#22D3EE',
    boxShadow: '0 0 6px #22D3EE',
  },
  workspaceLabel: {
    fontSize: '13px',
    fontWeight: 700,
    letterSpacing: '0.2px',
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  activeProfile: {
    fontSize: '11px',
    fontFamily: "'IBM Plex Sans', sans-serif",
    color: '#64748B',
  },
  navContainer: {
    padding: '16px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    overflowY: 'auto',
    flex: 1,
  },
  categoryGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  categoryTitle: {
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.8px',
    textTransform: 'uppercase',
    color: '#64748B',
    padding: '0 10px 4px 10px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  itemList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '11px',
    padding: '9px 12px',
    borderRadius: '8px',
    fontSize: '13px',
    textAlign: 'left',
    width: '100%',
    cursor: 'pointer',
    position: 'relative',
    transition: 'all 0.15s ease-in-out',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  itemIcon: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '18px',
    height: '18px',
    flexShrink: 0,
    transition: 'color 0.15s ease',
  },
  itemLabel: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    letterSpacing: '0.1px',
  },
  activeIndicator: {
    width: '5px',
    height: '5px',
    borderRadius: '50%',
    backgroundColor: '#22D3EE',
    boxShadow: '0 0 8px #22D3EE',
  },
  sidebarFooter: {
    padding: '14px',
    borderTop: '1px solid rgba(38, 52, 73, 0.6)',
    backgroundColor: 'rgba(15, 23, 42, 0.5)',
  },
  footerNotice: {
    backgroundColor: 'rgba(23, 32, 51, 0.7)',
    border: '1px solid rgba(38, 52, 73, 0.8)',
    borderRadius: '8px',
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
  },
  noticeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  noticeTitle: {
    fontSize: '11px',
    fontWeight: 700,
    letterSpacing: '0.4px',
    color: '#10B981',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  noticeBody: {
    fontSize: '11px',
    color: '#94A3B8',
    lineHeight: 1.4,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
};
