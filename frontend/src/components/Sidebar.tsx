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
      <div style={styles.sidebarHeader}>
        <span style={styles.workspaceLabel}>INVESTIGATION WORKSPACE</span>
      </div>

      <nav style={styles.navContainer}>
        {categories.map((category) => {
          const items = NAVIGATION_ITEMS.filter((item) => item.category === category);
          return (
            <div key={category} style={styles.categoryGroup}>
              <div style={styles.categoryTitle}>{category.toUpperCase()}</div>
              <div style={styles.itemList}>
                {items.map((item) => {
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => onSelectTab(item.id)}
                      style={{
                        ...styles.navItem,
                        backgroundColor: isActive ? 'var(--bg-card)' : 'transparent',
                        borderColor: isActive ? 'var(--accent-cyan)' : 'transparent',
                        color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                      }}
                    >
                      <span style={styles.itemIcon}>{getNavIcon(item.id)}</span>
                      <span style={styles.itemLabel}>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div style={styles.sidebarFooter}>
        <div style={styles.footerNotice}>
          <div style={styles.noticeTitle}>INTEGRITY STANDARD</div>
          <div style={styles.noticeBody}>All future modules adhere to non-accusatory evidence grounding.</div>
        </div>
      </div>
    </aside>
  );
};

function getNavIcon(tab: NavigationTab): string {
  switch (tab) {
    case 'dashboard':
      return '▦';
    case 'cases':
      return '📁';
    case 'evidence':
      return '📦';
    case 'investigations':
      return '🔍';
    case 'search':
      return '🔎';
    case 'timeline':
      return '⏱';
    case 'graph':
      return '🕸';
    case 'anomalies':
      return '⚡';
    case 'reports':
      return '📄';
    case 'audit':
      return '🛡';
    case 'settings':
      return '⚙';
    default:
      return '•';
  }
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 'var(--sidebar-width)',
    backgroundColor: 'var(--bg-surface)',
    borderRight: '1px solid var(--border-subtle)',
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - var(--header-height))',
    flexShrink: 0,
    userSelect: 'none',
  },
  sidebarHeader: {
    padding: '14px 16px 8px 16px',
    borderBottom: '1px solid var(--border-subtle)',
  },
  workspaceLabel: {
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '1px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
  navContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  categoryGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  categoryTitle: {
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    letterSpacing: '0.8px',
    padding: '4px 8px',
    fontFamily: 'var(--font-mono)',
  },
  itemList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '7px 10px',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: 500,
    textAlign: 'left',
    transition: 'all 0.15s ease',
    borderLeft: '3px solid transparent',
  },
  itemIcon: {
    fontSize: '14px',
    width: '18px',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0.85,
  },
  itemLabel: {
    flex: 1,
  },
  sidebarFooter: {
    padding: '12px 16px',
    borderTop: '1px solid var(--border-subtle)',
    backgroundColor: 'rgba(0, 0, 0, 0.2)',
  },
  footerNotice: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  noticeTitle: {
    fontSize: '9px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
    letterSpacing: '0.8px',
    fontFamily: 'var(--font-mono)',
  },
  noticeBody: {
    fontSize: '10px',
    color: 'var(--text-muted)',
    lineHeight: 1.3,
  },
};
