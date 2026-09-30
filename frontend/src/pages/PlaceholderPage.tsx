import React from 'react';
import type { NavigationItem } from '../types/navigation';

interface PlaceholderPageProps {
  item: NavigationItem;
}

export const PlaceholderPage: React.FC<PlaceholderPageProps> = ({ item }) => {
  return (
    <div style={styles.container}>
      {/* Top Banner / Action Bar */}
      <div style={styles.headerBar}>
        <div>
          <div style={styles.breadcrumb}>
            WORKSPACE / {item.category.toUpperCase()} / {item.label.toUpperCase()}
          </div>
          <h1 style={styles.title}>{item.label}</h1>
        </div>
        <div style={styles.badgeContainer}>
          <span style={styles.phaseTag}>{item.plannedPhase}</span>
          <span style={styles.statusBadge}>STATUS: ARCHITECTURAL SPECIFICATION READY</span>
        </div>
      </div>

      {/* Main Notice Box */}
      <div style={styles.noticeCard}>
        <div style={styles.noticeIcon}>ℹ</div>
        <div style={styles.noticeContent}>
          <h3 style={styles.noticeHeading}>Module Foundation Established</h3>
          <p style={styles.noticeText}>
            This module will be available in a future development phase. The underlying API contracts,
            security boundaries, and canonical data models have been architected in Phase 0 and Phase 1.
          </p>
        </div>
      </div>

      {/* Architectural Specifications Grid */}
      <div style={styles.detailsGrid}>
        {/* Module Scope Card */}
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>Planned Functional Scope</h2>
          <p style={styles.cardDescription}>{item.description}</p>
          <div style={styles.specList}>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>✓</span>
              <span>Complies with strict case-level authorization scoping.</span>
            </div>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>✓</span>
              <span>Read-only direct database isolation; writes mediated via API services.</span>
            </div>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>✓</span>
              <span>All user actions automatically logged to append-only forensic audit trail.</span>
            </div>
          </div>
        </div>

        {/* Forensic Integrity Safeguards */}
        <div style={styles.card}>
          <h2 style={styles.cardTitle}>Forensic Integrity Guarantees</h2>
          <div style={styles.specList}>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>•</span>
              <span><strong>Absolute Source of Truth:</strong> Canonical evidence records; zero synthesized or hallucinated facts.</span>
            </div>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>•</span>
              <span><strong>Traceability Lineage:</strong> Evidence → Artifact → Record → Analysis → Finding → Report.</span>
            </div>
            <div style={styles.specItem}>
              <span style={styles.specBullet}>•</span>
              <span><strong>Non-Autonomous Accusations:</strong> Strictly assists examiners; never declares guilt or malice.</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Phase Note */}
      <div style={styles.footerInfo}>
        <span>Active Phase: <strong>Phase 1 — Project Foundation & Application Architecture</strong></span>
        <span>Engine Build: <strong>0.1.0-foundation</strong></span>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px 32px',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
    height: '100%',
    overflowY: 'auto',
  },
  headerBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '16px',
  },
  breadcrumb: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    letterSpacing: '0.5px',
    marginBottom: '4px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    letterSpacing: '-0.3px',
  },
  badgeContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '6px',
  },
  phaseTag: {
    backgroundColor: 'rgba(56, 189, 248, 0.12)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.25)',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 500,
    padding: '4px 10px',
    borderRadius: '4px',
  },
  statusBadge: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  noticeCard: {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderLeft: '4px solid var(--accent-cyan)',
    borderRadius: '6px',
    padding: '16px 20px',
    display: 'flex',
    gap: '16px',
    alignItems: 'flex-start',
  },
  noticeIcon: {
    color: 'var(--accent-cyan)',
    fontSize: '18px',
    fontWeight: 700,
    marginTop: '2px',
  },
  noticeContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  noticeHeading: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  noticeText: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
  },
  detailsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
    gap: '16px',
  },
  card: {
    backgroundColor: 'var(--bg-card)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  cardTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '8px',
  },
  cardDescription: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
  },
  specList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  specItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    fontSize: '12px',
    color: 'var(--text-secondary)',
    lineHeight: 1.4,
  },
  specBullet: {
    color: 'var(--accent-cyan)',
    fontWeight: 700,
  },
  footerInfo: {
    marginTop: 'auto',
    paddingTop: '16px',
    borderTop: '1px solid var(--border-subtle)',
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
  },
};
