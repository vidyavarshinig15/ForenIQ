import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../services/authContext';
import type { Case } from '../types/case';
import type { NavigationTab } from '../types/navigation';

interface HeaderProps {
  activeTab?: NavigationTab;
  onSelectTab?: (tab: NavigationTab) => void;
  activeCase?: Case | null;
  onClearActiveCase?: () => void;
  onNavigateToLanding?: () => void;
  onNewCase?: () => void;
}

const TAB_CONFIG: Record<NavigationTab, { label: string; icon: string }> = {
  dashboard: { label: 'Dashboard', icon: '📊' },
  cases: { label: 'Cases Registry', icon: '📁' },
  evidence: { label: 'Evidence Vault', icon: '📦' },
  investigations: { label: 'AI Assistant', icon: '🤖' },
  search: { label: 'Forensic Search', icon: '🔍' },
  timeline: { label: 'Timeline', icon: '⏱️' },
  graph: { label: 'Communication Graph', icon: '🕸️' },
  anomalies: { label: 'Anomaly Detection', icon: '📈' },
  reports: { label: 'Forensic Reports', icon: '📄' },
  audit: { label: 'Audit Vault', icon: '🔒' },
  settings: { label: 'Settings', icon: '⚙️' },
};

interface NotificationItem {
  id: string;
  title: string;
  desc: string;
  time: string;
  unread: boolean;
  type: 'security' | 'ingestion' | 'case' | 'ai';
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: 'n1',
    title: 'SHA-256 Vault Integrity Verified',
    desc: 'Automated cryptographic check confirmed all evidence hashes match baseline.',
    time: '2m ago',
    unread: true,
    type: 'security',
  },
  {
    id: 'n2',
    title: 'Case Scoping Boundary Active',
    desc: 'Multi-tenant isolation enforced for active forensic sessions (ISO/IEC 27037).',
    time: '18m ago',
    unread: true,
    type: 'case',
  },
  {
    id: 'n3',
    title: 'Offline AI Model Initialized',
    desc: 'SentenceTransformers embeddings running on-premises without external network calls.',
    time: '45m ago',
    unread: false,
    type: 'ai',
  },
];

export const Header: React.FC<HeaderProps> = ({
  activeTab = 'cases',
  onSelectTab,
  activeCase,
  onClearActiveCase,
  onNavigateToLanding,
  onNewCase,
}) => {
  const { user, logout } = useAuth();
  const [logoHover, setLogoHover] = useState(false);
  const [logoutHover, setLogoutHover] = useState(false);

  // UTC Forensic Clock
  const [utcTime, setUtcTime] = useState<string>('');
  const [localTime, setLocalTime] = useState<string>('');

  // Quick Search state
  const [searchVal, setSearchVal] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);

  // Notifications dropdown
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>(INITIAL_NOTIFICATIONS);
  const notifRef = useRef<HTMLDivElement>(null);

  // Help modal
  const [showHelpModal, setShowHelpModal] = useState(false);

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const hours = String(now.getUTCHours()).padStart(2, '0');
      const minutes = String(now.getUTCMinutes()).padStart(2, '0');
      const seconds = String(now.getUTCSeconds()).padStart(2, '0');
      setUtcTime(`${hours}:${minutes}:${seconds} UTC`);
      setLocalTime(now.toLocaleTimeString());
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Close notifications dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotifications(false);
      }
    };
    if (showNotifications) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showNotifications]);

  // Keyboard shortcut: Cmd+K or Ctrl+K triggers search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onSelectTab?.('search');
        const input = document.getElementById('global-forensic-search-input');
        if (input) input.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onSelectTab]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSelectTab) {
      onSelectTab('search');
    }
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

  const unreadCount = notifications.filter((n) => n.unread).length;

  const currentTabMeta = TAB_CONFIG[activeTab] || { label: 'Workspace', icon: '📁' };

  const userInitials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'EX';

  return (
    <>
      <header style={styles.header}>
        {/* LEFT SECTION: Logo & Feature Breadcrumb */}
        <div style={styles.leftSection}>
          <button
            onClick={onNavigateToLanding}
            onMouseEnter={() => setLogoHover(true)}
            onMouseLeave={() => setLogoHover(false)}
            style={{
              ...styles.logoBtn,
              transform: logoHover ? 'scale(1.02)' : 'none',
              borderColor: logoHover ? 'rgba(34, 211, 238, 0.4)' : 'transparent',
              backgroundColor: logoHover ? 'rgba(34, 211, 238, 0.05)' : 'transparent',
            }}
            title="Return to Home (Landing Page)"
            aria-label="ForenIQ Home"
          >
            <img
              src="/foreniq-logo.png"
              alt="ForenIQ"
              style={styles.logoImg}
            />
            <span style={styles.returnHint}>Home ↗</span>
          </button>

          <div style={styles.vDivider} />

          {/* Current Active Module Breadcrumb */}
          <div style={styles.breadcrumbBadge}>
            <span style={styles.breadcrumbIcon}>{currentTabMeta.icon}</span>
            <span style={styles.breadcrumbLabel}>{currentTabMeta.label}</span>
          </div>

          {/* Active Case Context Pill */}
          {activeCase && (
            <div style={styles.activeCaseBadge}>
              <span style={styles.activeCaseDot} />
              <span style={styles.activeCaseLabel}>Case:</span>
              <span style={styles.activeCaseNumber}>{activeCase.case_number}</span>
              {activeCase.title && (
                <span style={styles.activeCaseName}>— {activeCase.title}</span>
              )}
              {onClearActiveCase && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onClearActiveCase();
                  }}
                  style={styles.clearScopeBtn}
                  title="Exit case view"
                  aria-label="Deselect active case"
                >
                  ✕
                </button>
              )}
            </div>
          )}
        </div>

        {/* CENTER SECTION: Global Quick Search */}
        <div style={styles.centerSection}>
          <form
            onSubmit={handleSearchSubmit}
            style={{
              ...styles.searchBox,
              borderColor: isSearchFocused ? '#22D3EE' : '#263449',
              boxShadow: isSearchFocused ? '0 0 12px rgba(34, 211, 238, 0.2)' : 'none',
            }}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#94A3B8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={styles.searchIcon}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              id="global-forensic-search-input"
              type="text"
              placeholder="Quick search evidence, suspects, keywords, phone numbers..."
              value={searchVal}
              onChange={(e) => setSearchVal(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
              style={styles.searchInput}
            />
            <kbd style={styles.searchKbd}>⌘K</kbd>
          </form>
        </div>

        {/* RIGHT SECTION: Quick Actions, Clock, Security, Notifications, User */}
        <div style={styles.rightSection}>
          {/* Quick Action: New Case */}
          <button
            onClick={() => {
              if (onNewCase) {
                onNewCase();
              } else if (onSelectTab) {
                onSelectTab('cases');
              }
            }}
            style={styles.newCaseBtn}
            title="Create or scope a new forensic case"
          >
            <span style={styles.plusIcon}>+</span>
            <span>New Case</span>
          </button>

          {/* Forensic Synchronized UTC Clock */}
          <div
            style={styles.clockPill}
            title={`Cryptographically synchronized forensic clock.\nLocal Time: ${localTime}`}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#22D3EE"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span style={styles.clockText}>{utcTime || 'UTC --:--:--'}</span>
          </div>


          {/* Activity / Notification Center */}
          <div style={styles.notifContainer} ref={notifRef}>
            <button
              onClick={() => setShowNotifications((prev) => !prev)}
              style={{
                ...styles.iconBtn,
                backgroundColor: showNotifications ? 'rgba(34, 211, 238, 0.15)' : '#172033',
                borderColor: showNotifications ? '#22D3EE' : '#263449',
              }}
              title="Forensic Activity & Notifications"
              aria-label="Activity notifications"
            >
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke={unreadCount > 0 ? '#22D3EE' : '#94A3B8'}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {unreadCount > 0 && (
                <span style={styles.notifBadge}>{unreadCount}</span>
              )}
            </button>

            {/* Notifications Popover Dropdown */}
            {showNotifications && (
              <div style={styles.notifDropdown}>
                <div style={styles.notifHeader}>
                  <div style={styles.notifTitle}>
                    <span>Activity &amp; Integrity Logs</span>
                    {unreadCount > 0 && (
                      <span style={styles.notifCountPill}>{unreadCount} new</span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      style={styles.markReadBtn}
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div style={styles.notifList}>
                  {notifications.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        ...styles.notifItem,
                        backgroundColor: item.unread
                          ? 'rgba(34, 211, 238, 0.04)'
                          : 'transparent',
                      }}
                    >
                      <div style={styles.notifItemHeader}>
                        <span style={styles.notifItemTitle}>{item.title}</span>
                        <span style={styles.notifItemTime}>{item.time}</span>
                      </div>
                      <p style={styles.notifItemDesc}>{item.desc}</p>
                    </div>
                  ))}
                </div>

                <div style={styles.notifFooter}>
                  <button
                    onClick={() => {
                      setShowNotifications(false);
                      onSelectTab?.('audit');
                    }}
                    style={styles.viewAuditBtn}
                  >
                    View Immutable Audit Vault →
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Quick Help Guide Button */}
          <button
            onClick={() => setShowHelpModal(true)}
            style={styles.iconBtn}
            title="Forensic Investigator Quick Guide & Shortcuts"
            aria-label="Help Guide"
          >
            <span style={styles.helpQuestion}>?</span>
          </button>

          {/* User Profile Card */}
          {user && (
            <div style={styles.userProfileCard}>
              <div style={styles.avatarCircle}>{userInitials}</div>
              <div style={styles.userDetails}>
                <span style={styles.userName}>{user.name || user.email}</span>
                <span style={styles.userRoleBadge}>{user.role || 'Examiner'}</span>
              </div>
            </div>
          )}

          {/* Sign Out */}
          <button
            onClick={() => logout()}
            onMouseEnter={() => setLogoutHover(true)}
            onMouseLeave={() => setLogoutHover(false)}
            style={{
              ...styles.logoutBtn,
              backgroundColor: logoutHover
                ? 'rgba(239, 68, 68, 0.15)'
                : 'rgba(239, 68, 68, 0.08)',
              borderColor: logoutHover
                ? 'rgba(239, 68, 68, 0.45)'
                : 'rgba(239, 68, 68, 0.25)',
            }}
            title="Sign Out of Forensic Session"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Forensic Quick Help Guide Modal */}
      {showHelpModal && (
        <div style={styles.modalOverlay} onClick={() => setShowHelpModal(false)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div style={styles.modalHeaderLeft}>
                <span style={styles.modalShieldIcon}>🛡️</span>
                <div>
                  <h3 style={styles.modalTitle}>Forensic Investigator Operating Guide</h3>
                  <p style={styles.modalSubtitle}>Standardized workflow for UFDR data analysis &amp; chain of custody</p>
                </div>
              </div>
              <button
                onClick={() => setShowHelpModal(false)}
                style={styles.modalCloseBtn}
              >
                ✕
              </button>
            </div>

            <div style={styles.modalBody}>
              <div style={styles.guideStep}>
                <div style={styles.stepNumber}>01</div>
                <div>
                  <h4 style={styles.stepTitle}>Scope Case Boundary &amp; Ingest Evidence</h4>
                  <p style={styles.stepDesc}>
                    Create or select a case in the <strong>Cases Registry</strong>. Upload Cellebrite UFDR, XRY, or Oxygen extraction archives into the <strong>Evidence Vault</strong>. Cryptographic SHA-256 hashes are automatically verified and locked.
                  </p>
                </div>
              </div>

              <div style={styles.guideStep}>
                <div style={styles.stepNumber}>02</div>
                <div>
                  <h4 style={styles.stepTitle}>Reconstruct Unified Timelines &amp; Social Graphs</h4>
                  <p style={styles.stepDesc}>
                    Navigate to <strong>Timeline</strong> to synchronize multi-device chronological events. Use <strong>Communication Graph</strong> to map suspect interaction topologies and identify central coordinators.
                  </p>
                </div>
              </div>

              <div style={styles.guideStep}>
                <div style={styles.stepNumber}>03</div>
                <div>
                  <h4 style={styles.stepTitle}>Query with Evidence-Grounded AI Assistant</h4>
                  <p style={styles.stepDesc}>
                    Use the <strong>AI Assistant</strong> to ask complex questions in natural language. Every finding is strictly cited with direct artifact IDs, timestamps, and confidence scores—no speculative claims.
                  </p>
                </div>
              </div>

              <div style={styles.guideStep}>
                <div style={styles.stepNumber}>04</div>
                <div>
                  <h4 style={styles.stepTitle}>Export Court-Ready Forensic Reports</h4>
                  <p style={styles.stepDesc}>
                    Synthesize verified evidence into ISO/IEC 27037 compliant documents in <strong>Forensic Reports</strong>. Each report is timestamped, sealed with examiner credentials, and ready for legal submission.
                  </p>
                </div>
              </div>

              <div style={styles.shortcutBanner}>
                <div style={styles.shortcutTitle}>⚡ Keyboard Shortcuts</div>
                <div style={styles.shortcutGrid}>
                  <div style={styles.shortcutItem}><kbd style={styles.kbd}>⌘K</kbd> Global Quick Search</div>
                  <div style={styles.shortcutItem}><kbd style={styles.kbd}>Esc</kbd> Close Active Modals</div>
                </div>
              </div>
            </div>

            <div style={styles.modalFooter}>
              <button
                onClick={() => setShowHelpModal(false)}
                style={styles.modalDoneBtn}
              >
                Got It, Return to Workstation
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const styles: Record<string, React.CSSProperties> = {
  header: {
    height: '62px',
    backgroundColor: '#111827',
    borderBottom: '1px solid #263449',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
    flexShrink: 0,
    userSelect: 'none',
    zIndex: 50,
    position: 'relative',
    gap: '16px',
  },
  leftSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexShrink: 0,
  },
  logoBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: 'none',
    border: '1px solid transparent',
    borderRadius: '8px',
    padding: '4px 8px 4px 4px',
    cursor: 'pointer',
    transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
  },
  logoImg: {
    height: '35px',
    width: 'auto',
    display: 'block',
    objectFit: 'contain',
  },
  returnHint: {
    fontSize: '11px',
    fontFamily: "'IBM Plex Sans', sans-serif",
    color: '#94A3B8',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    padding: '2px 6px',
    borderRadius: '5px',
    fontWeight: 500,
  },
  vDivider: {
    width: '1px',
    height: '22px',
    backgroundColor: '#263449',
  },
  breadcrumbBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    padding: '5px 12px',
    borderRadius: '16px',
    fontSize: '12px',
  },
  breadcrumbIcon: {
    fontSize: '13px',
  },
  breadcrumbLabel: {
    color: '#F8FAFC',
    fontWeight: 600,
    fontFamily: "'Space Grotesk', sans-serif",
    letterSpacing: '-0.2px',
  },
  activeCaseBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
    backgroundColor: 'rgba(34, 211, 238, 0.08)',
    border: '1px solid rgba(34, 211, 238, 0.3)',
    padding: '5px 11px',
    borderRadius: '16px',
    fontSize: '12px',
  },
  activeCaseDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#22D3EE',
    boxShadow: '0 0 6px rgba(34, 211, 238, 0.8)',
  },
  activeCaseLabel: {
    color: '#94A3B8',
    fontWeight: 500,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  activeCaseNumber: {
    color: '#22D3EE',
    fontWeight: 700,
    fontFamily: "'IBM Plex Mono', monospace",
  },
  activeCaseName: {
    color: '#E2E8F0',
    fontWeight: 500,
    fontFamily: "'IBM Plex Sans', sans-serif",
    maxWidth: '180px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  clearScopeBtn: {
    background: 'none',
    border: 'none',
    color: '#94A3B8',
    fontSize: '11px',
    padding: '1px 4px',
    borderRadius: '3px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerSection: {
    flex: 1,
    maxWidth: '460px',
    minWidth: '220px',
  },
  searchBox: {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '20px',
    padding: '4px 12px',
    transition: 'all 0.2s ease',
  },
  searchIcon: {
    marginRight: '8px',
    flexShrink: 0,
  },
  searchInput: {
    flex: 1,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#F8FAFC',
    fontSize: '12px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  searchKbd: {
    backgroundColor: '#1E293B',
    color: '#94A3B8',
    fontSize: '10px',
    padding: '2px 5px',
    borderRadius: '4px',
    border: '1px solid #263449',
    fontFamily: "'IBM Plex Mono', monospace",
    marginLeft: '6px',
    flexShrink: 0,
  },
  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexShrink: 0,
  },
  newCaseBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    border: '1px solid #22D3EE',
    padding: '6px 13px',
    borderRadius: '16px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 8px rgba(34, 211, 238, 0.25)',
  },
  plusIcon: {
    fontSize: '14px',
    fontWeight: 800,
    lineHeight: 1,
  },
  clockPill: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    padding: '5px 10px',
    borderRadius: '16px',
    fontSize: '11px',
    cursor: 'help',
  },
  clockText: {
    color: '#E2E8F0',
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
    fontSize: '11px',
    letterSpacing: '0.3px',
  },
  notifContainer: {
    position: 'relative',
  },
  iconBtn: {
    width: '32px',
    height: '32px',
    borderRadius: '50%',
    backgroundColor: '#172033',
    border: '1px solid #263449',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    position: 'relative',
    transition: 'all 0.2s ease',
  },
  notifBadge: {
    position: 'absolute',
    top: '-3px',
    right: '-3px',
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    fontSize: '9px',
    fontWeight: 800,
    borderRadius: '10px',
    padding: '1px 4px',
    lineHeight: 1.2,
    boxShadow: '0 0 6px rgba(34, 211, 238, 0.8)',
  },
  helpQuestion: {
    fontSize: '13px',
    fontWeight: 700,
    color: '#94A3B8',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  notifDropdown: {
    position: 'absolute',
    top: '42px',
    right: 0,
    width: '340px',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '12px',
    boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
    zIndex: 100,
    overflow: 'hidden',
  },
  notifHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 14px',
    borderBottom: '1px solid #263449',
    backgroundColor: '#172033',
  },
  notifTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
    fontWeight: 700,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  notifCountPill: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#0B1220',
    backgroundColor: '#22D3EE',
    padding: '1px 6px',
    borderRadius: '8px',
  },
  markReadBtn: {
    background: 'none',
    border: 'none',
    color: '#22D3EE',
    fontSize: '11px',
    cursor: 'pointer',
    fontWeight: 600,
  },
  notifList: {
    maxHeight: '260px',
    overflowY: 'auto',
  },
  notifItem: {
    padding: '12px 14px',
    borderBottom: '1px solid rgba(38, 52, 73, 0.5)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  notifItemHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  notifItemTitle: {
    fontSize: '12px',
    fontWeight: 600,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  notifItemTime: {
    fontSize: '10px',
    color: '#64748B',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  notifItemDesc: {
    fontSize: '11px',
    color: '#94A3B8',
    margin: 0,
    lineHeight: 1.4,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  notifFooter: {
    padding: '10px 14px',
    backgroundColor: '#172033',
    borderTop: '1px solid #263449',
    textAlign: 'center',
  },
  viewAuditBtn: {
    background: 'none',
    border: 'none',
    color: '#22D3EE',
    fontSize: '11px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  userProfileCard: {
    display: 'flex',
    alignItems: 'center',
    gap: '9px',
    backgroundColor: '#172033',
    padding: '3px 10px 3px 5px',
    borderRadius: '24px',
    border: '1px solid #263449',
  },
  avatarCircle: {
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    background: 'linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)',
    color: '#0B1220',
    fontSize: '11px',
    fontWeight: 800,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  userDetails: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
  },
  userName: {
    color: '#F8FAFC',
    fontWeight: 600,
    fontSize: '12px',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  userRoleBadge: {
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    color: '#22D3EE',
    border: '1px solid rgba(34, 211, 238, 0.3)',
    padding: '1px 6px',
    borderRadius: '6px',
    fontFamily: "'IBM Plex Mono', monospace",
  },
  logoutBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    color: '#F87171',
    border: '1px solid rgba(239, 68, 68, 0.25)',
    fontSize: '12px',
    fontWeight: 600,
    fontFamily: "'IBM Plex Sans', sans-serif",
    padding: '6px 12px',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  // Modal styles
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(11, 18, 32, 0.8)',
    backdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 200,
  },
  modalContent: {
    width: '640px',
    maxWidth: '92vw',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '16px',
    boxShadow: '0 24px 60px rgba(0, 0, 0, 0.6)',
    overflow: 'hidden',
  },
  modalHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '18px 24px',
    backgroundColor: '#172033',
    borderBottom: '1px solid #263449',
  },
  modalHeaderLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  modalShieldIcon: {
    fontSize: '24px',
  },
  modalTitle: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 700,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  modalSubtitle: {
    margin: '3px 0 0 0',
    fontSize: '12px',
    color: '#94A3B8',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  modalCloseBtn: {
    background: 'none',
    border: 'none',
    color: '#94A3B8',
    fontSize: '16px',
    cursor: 'pointer',
    padding: '4px',
  },
  modalBody: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '18px',
    maxHeight: '65vh',
    overflowY: 'auto',
  },
  guideStep: {
    display: 'flex',
    gap: '16px',
    alignItems: 'flex-start',
  },
  stepNumber: {
    width: '32px',
    height: '32px',
    borderRadius: '8px',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    border: '1px solid rgba(34, 211, 238, 0.3)',
    color: '#22D3EE',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 800,
    fontFamily: "'IBM Plex Mono', monospace",
    flexShrink: 0,
  },
  stepTitle: {
    margin: '0 0 4px 0',
    fontSize: '14px',
    fontWeight: 600,
    color: '#F8FAFC',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  stepDesc: {
    margin: 0,
    fontSize: '12px',
    color: '#94A3B8',
    lineHeight: 1.5,
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  shortcutBanner: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '10px',
    padding: '14px 18px',
    marginTop: '6px',
  },
  shortcutTitle: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#22D3EE',
    marginBottom: '8px',
    fontFamily: "'Space Grotesk', sans-serif",
  },
  shortcutGrid: {
    display: 'flex',
    gap: '20px',
    fontSize: '12px',
    color: '#E2E8F0',
    fontFamily: "'IBM Plex Sans', sans-serif",
  },
  shortcutItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  kbd: {
    backgroundColor: '#0B1220',
    border: '1px solid #263449',
    padding: '2px 6px',
    borderRadius: '4px',
    fontSize: '10px',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#22D3EE',
  },
  modalFooter: {
    padding: '14px 24px',
    backgroundColor: '#172033',
    borderTop: '1px solid #263449',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  modalDoneBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    border: 'none',
    padding: '9px 18px',
    borderRadius: '6px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: "'Space Grotesk', sans-serif",
    cursor: 'pointer',
  },
};
