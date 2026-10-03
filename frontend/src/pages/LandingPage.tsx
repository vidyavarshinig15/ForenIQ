import React, { useState } from 'react';
import { useAuth } from '../services/authContext';

interface LandingPageProps {
  onOpenLoginModal?: () => void;
  onNavigateToWorkstation?: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigateToWorkstation,
}) => {
  const { isAuthenticated, login, isLoading } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleOpenLogin = () => {
    if (isAuthenticated && onNavigateToWorkstation) {
      onNavigateToWorkstation();
    } else {
      setShowLoginModal(true);
    }
  };

  const handleCloseLogin = () => {
    setShowLoginModal(false);
    setErrorMsg(null);
  };

  const handleAutofillAdmin = () => {
    setEmail('admin@ufdr.org');
    setPassword('helloitsme');
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!email || !password) {
      setErrorMsg('Please enter both your investigative email and password.');
      return;
    }
    try {
      await login({ email, password });
      setShowLoginModal(false);
      if (onNavigateToWorkstation) {
        onNavigateToWorkstation();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed. Please verify credentials.');
    }
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div style={styles.pageWrapper}>
      {/* Responsive Typography Overrides */}
      <style>{`
        .foreniq-hero-heading {
          font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif !important;
          font-weight: 700 !important;
          line-height: 1.02 !important;
          letter-spacing: -1.5px !important;
          font-size: 68px !important;
        }
        @media (max-width: 1024px) {
          .foreniq-hero-heading {
            font-size: 52px !important;
            letter-spacing: -1px !important;
          }
        }
        @media (max-width: 640px) {
          .foreniq-hero-heading {
            font-size: 40px !important;
            letter-spacing: -0.5px !important;
          }
        }

        .foreniq-section-heading {
          font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif !important;
          font-weight: 700 !important;
          letter-spacing: -0.8px !important;
          font-size: 40px !important;
        }
        @media (max-width: 1024px) {
          .foreniq-section-heading {
            font-size: 34px !important;
          }
        }
        @media (max-width: 640px) {
          .foreniq-section-heading {
            font-size: 28px !important;
          }
        }
      `}</style>

      {/* ---------------- NAVIGATION BAR ---------------- */}
      <header style={styles.navbar}>
        <div style={styles.navContainer}>
          {/* Logo Brand */}
          <div style={styles.brandContainer} onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <img
              src="/foreniq-logo.png"
              alt="ForenIQ"
              style={{ height: '48px', width: 'auto', display: 'block', objectFit: 'contain' }}
            />
          </div>

          {/* Navigation Links */}
          <nav style={styles.navLinks}>
            <button style={styles.navLink} onClick={() => scrollToSection('features')}>
              Features
            </button>
            <button style={styles.navLink} onClick={() => scrollToSection('how-it-works')}>
              How It Works
            </button>
            <button style={styles.navLink} onClick={() => scrollToSection('security')}>
              Security
            </button>
            <button style={styles.navLink} onClick={() => scrollToSection('contact')}>
              Contact
            </button>
          </nav>

          {/* Right Action */}
          <div style={styles.navRight}>
            {isAuthenticated ? (
              <button style={styles.pillButton} onClick={onNavigateToWorkstation}>
                Open Workstation →
              </button>
            ) : (
              <button style={styles.pillButton} onClick={handleOpenLogin}>
                Sign In / Login →
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ---------------- HERO SECTION (Centered Alignment Preserved) ---------------- */}
      <section style={styles.heroSection}>
        <div style={styles.ambientGlow} />
        <div style={styles.heroContent}>
          <h1 className="foreniq-hero-heading" style={styles.heroHeading}>
            <span style={styles.heroNavy}>Intelligent Forensic</span>
            <span style={styles.heroNavy}>Ecosystem.</span>
            <span style={styles.heroGreen}>Verifiable Analysis.</span>
          </h1>

          <p style={styles.heroSubtitle}>
            The high-clarity digital toolkit for Universal Forensic Data Extractions. Stop guessing, start streamlining your forensic investigations with verifiable citations.
          </p>

          <div style={styles.heroCtaWrapper}>
            <div style={styles.heroButtonGroup}>
              <button style={styles.heroPrimaryButton} onClick={handleOpenLogin}>
                <span>{isAuthenticated ? 'Open Forensic Workstation' : 'Launch Workstation'}</span>
                <span style={{ fontSize: '16px' }}>→</span>
              </button>
              <button style={styles.heroSecondaryButton} onClick={() => scrollToSection('features')}>
                Explore Platform
              </button>
            </div>
            <span style={styles.heroSubtext}>
              Available for certified forensic examiners, federal investigators, and cyber incident responders
            </span>
          </div>
        </div>
      </section>

      {/* ---------------- STATS TICKER STRIP ---------------- */}
      <section style={styles.statsStrip}>
        <div style={styles.statsContainer}>
          <div style={styles.statItem}>
            <div style={styles.statNumber}>SHA-256</div>
            <div style={styles.statLabel}>Cryptographic Baseline</div>
          </div>
          <div style={styles.statDivider} />
          <div style={styles.statItem}>
            <div style={styles.statNumber}>100% Offline</div>
            <div style={styles.statLabel}>Air-Gapped AI Inference</div>
          </div>
          <div style={styles.statDivider} />
          <div style={styles.statItem}>
            <div style={styles.statNumber}>ISO/IEC 27037</div>
            <div style={styles.statLabel}>Digital Custody Standard</div>
          </div>
        </div>
      </section>

      {/* ---------------- FEATURES SECTION (3 Cards) ---------------- */}
      <section id="features" style={styles.featuresSection}>
        <div style={styles.featuresHeader}>
          <h2 className="foreniq-section-heading" style={styles.featuresTitle}>Features</h2>
          <p style={styles.featuresSubtitle}>
            Modular forensic pipeline engineered for verifiable evidence analysis
          </p>
        </div>

        <div style={styles.cardsGrid}>
          {/* Card 1: UFDR Ingestion */}
          <div style={styles.card}>
            <div style={styles.cardIconBox}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
              </svg>
            </div>
            <h3 style={styles.cardTitle}>UFDR Ingestion</h3>

            <div style={styles.stepList}>
              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>01</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Archive Validation</div>
                  <div style={styles.stepDesc}>
                    Streaming archive inspection with SHA-256 baseline and Zip-Slip traversal rejection.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>02</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Extraction Parsing</div>
                  <div style={styles.stepDesc}>
                    Extracts calls, SMS, WhatsApp, contacts, and media metadata deterministically.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>03</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Tamper-Proof Ledger</div>
                  <div style={styles.stepDesc}>
                    Cryptographic chain-of-custody logging with immutable event tracking.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>04</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Canonical Structuring</div>
                  <div style={styles.stepDesc}>
                    Normalizes vendor-specific mobile extractions into standard forensic schemas.
                  </div>
                </div>
              </div>
            </div>

            <div style={styles.cardFooterLink} onClick={handleOpenLogin}>
              Explore Ingestion Pipeline →
            </div>
          </div>

          {/* Card 2: AI Search & Graph */}
          <div style={styles.card}>
            <div style={styles.cardIconBox}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>
            <h3 style={styles.cardTitle}>AI Search &amp; Graph</h3>

            <div style={styles.stepList}>
              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>01</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Hybrid Search</div>
                  <div style={styles.stepDesc}>
                    Dense vector semantic search combined with exact BM25 identifier matching.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>02</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Entity Recognition</div>
                  <div style={styles.stepDesc}>
                    Automatic NER extraction for suspects, phone numbers, and crypto addresses.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>03</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Network Analysis</div>
                  <div style={styles.stepDesc}>
                    Communication centrality, degree metrics, and Louvain community clusters.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>04</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Anomaly Detection</div>
                  <div style={styles.stepDesc}>
                    Unsupervised temporal anomaly detection flags burst communications and spikes.
                  </div>
                </div>
              </div>
            </div>

            <div style={styles.cardFooterLink} onClick={handleOpenLogin}>
              Explore AI Search &amp; Graph →
            </div>
          </div>

          {/* Card 3: Court-Ready Reports */}
          <div style={styles.card}>
            <div style={styles.cardIconBox}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                <path d="M6 12v5c3 3 9 3 12 0v-5" />
              </svg>
            </div>
            <h3 style={styles.cardTitle}>Court-Ready Reports</h3>

            <div style={styles.stepList}>
              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>01</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Citation Guardrails</div>
                  <div style={styles.stepDesc}>
                    RAG assistant grounded strictly in verified case records with zero hallucinations.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>02</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Finding Synthesis</div>
                  <div style={styles.stepDesc}>
                    Tag, curate, and annotate critical evidence items directly into case chapters.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>03</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Referential Audit</div>
                  <div style={styles.stepDesc}>
                    Strict validation ensuring every claim has a cryptographic evidence hash.
                  </div>
                </div>
              </div>

              <div style={styles.stepRow}>
                <div style={styles.stepCircle}>04</div>
                <div style={styles.stepContent}>
                  <div style={styles.stepTitle}>Forensic Export</div>
                  <div style={styles.stepDesc}>
                    Export verifiable PDF, JSON, and CSV forensic packages instantly.
                  </div>
                </div>
              </div>
            </div>

            <div style={styles.cardFooterLink} onClick={handleOpenLogin}>
              Explore Court Reporting Engine →
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- HOW IT WORKS SECTION ---------------- */}
      <section id="how-it-works" style={styles.howItWorksSection}>
        <div style={styles.howItWorksContainer}>
          <div style={styles.howHeader}>
            <span style={styles.badgePill}>WORKFLOW PIPELINE</span>
            <h2 style={styles.howTitle}>How ForenIQ Operates in 3 Clear Steps</h2>
            <p style={styles.howSubtitle}>
              Engineered strictly for forensic integrity, multi-case scoping, and zero data leakage.
            </p>
          </div>

          <div style={styles.pipelineGrid}>
            <div style={styles.pipelineStep}>
              <div style={styles.pipelineNum}>1</div>
              <h4 style={styles.pipelineStepTitle}>Ingest &amp; Compute Baseline</h4>
              <p style={styles.pipelineStepText}>
                Upload raw Universal Forensic Data Extractions (.ufdr / .zip). ForenIQ computes SHA-256 baselines and safely unpacks raw SQLite dumps and XML artifacts.
              </p>
            </div>

            <div style={styles.pipelineStep}>
              <div style={styles.pipelineNum}>2</div>
              <h4 style={styles.pipelineStepTitle}>Correlate &amp; Investigate</h4>
              <p style={styles.pipelineStepText}>
                Ask natural questions like <em>"Show encrypted messages sent after midnight."</em> Explore social interaction graphs and anomalous temporal activity.
              </p>
            </div>

            <div style={styles.pipelineStep}>
              <div style={styles.pipelineNum}>3</div>
              <h4 style={styles.pipelineStepTitle}>Generate Court-Ready Report</h4>
              <p style={styles.pipelineStepText}>
                Compile verified evidence findings, complete chain-of-custody ledgers, and export signed PDFs that stand up to forensic scrutiny in courtroom hearings.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- SECURITY & COMPLIANCE BANNER ---------------- */}
      <section id="security" style={styles.securityBanner}>
        <div style={styles.securityInner}>
          <div style={styles.securityShield}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div style={styles.securityText}>
            <h3 style={styles.securityTitle}>Air-Gapped Privacy &amp; Integrity Guarantee</h3>
            <p style={styles.securityDesc}>
              ForenIQ runs 100% on-premises with local SentenceTransformers embeddings and deterministic RAG verification. Evidence archives remain read-only and immutable at all times.
            </p>
          </div>
          <button style={styles.securityButton} onClick={handleOpenLogin}>
            Open Workstation
          </button>
        </div>
      </section>

      {/* ---------------- FOOTER (3-Column Layout) ---------------- */}
      <footer id="contact" style={styles.footer}>
        <div style={styles.footerContainer}>
          {/* Col 1: Brand */}
          <div style={styles.footerColBrand}>
            <img
              src="/foreniq-logo.png"
              alt="ForenIQ"
              style={{ height: '36px', width: 'auto', display: 'block', objectFit: 'contain', marginBottom: '14px' }}
            />
            <p style={styles.footerDescription}>
              A unified digital forensic ecosystem to help investigators correlate evidence faster and maintain an untampered chain of custody.
            </p>
          </div>

          {/* Col 2: Product */}
          <div style={styles.footerCol}>
            <h4 style={styles.footerColTitle}>Product</h4>
            <div style={styles.footerLinkList}>
              <span style={styles.footerLink} onClick={() => scrollToSection('how-it-works')}>How It Works</span>
              <span style={styles.footerLink} onClick={() => scrollToSection('features')}>Features</span>
              <span style={styles.footerLink} onClick={handleOpenLogin}>Evidence Ingestion</span>
              <span style={styles.footerLink} onClick={handleOpenLogin}>Communication Graph</span>
              <span style={styles.footerLink} onClick={handleOpenLogin}>Forensic Reports</span>
            </div>
          </div>

          {/* Col 3: Contact */}
          <div style={styles.footerCol}>
            <h4 style={styles.footerColTitle}>Contact</h4>
            <div style={styles.footerContactList}>
              <div style={styles.footerContactItem}>investigations@foreniq.gov</div>
              <div style={styles.footerContactItem}>Ph no: +1 (800) 555-UFDR</div>
              <div style={styles.footerAddressBlock}>
                <div style={styles.footerAddressLabel}>Address:</div>
                <div style={styles.footerAddressText}>
                  National Cyber Forensic Command<br />
                  Digital Evidence Division, Phase 1<br />
                  Federal Forensic Directorate
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div style={styles.footerBottomBar}>
          <div style={styles.footerCopyright}>
            © 2026 ForenIQ - All rights reserved
          </div>
        </div>
      </footer>

      {/* ---------------- LOGIN MODAL ---------------- */}
      {showLoginModal && (
        <div style={styles.modalOverlay} onClick={handleCloseLogin}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div style={styles.modalTitleBox}>
                <span style={styles.modalBadge}>SECURE AUTHENTICATION</span>
                <h3 style={styles.modalTitle}>Forensic Investigator Login</h3>
              </div>
              <button style={styles.modalCloseBtn} onClick={handleCloseLogin}>
                ✕
              </button>
            </div>

            {/* Demo Autofill Box */}
            <div style={styles.demoBox}>
              <div style={styles.demoBoxHeader}>
                <span>🛡</span>
                <strong>BOOTSTRAP ADMIN CREDENTIALS</strong>
              </div>
              <div style={styles.demoBoxText}>
                Email: <code style={styles.demoCode}>admin@ufdr.org</code> | Password: <code style={styles.demoCode}>helloitsme</code>
              </div>
              <button type="button" onClick={handleAutofillAdmin} style={styles.autofillBtn}>
                Autofill Credentials
              </button>
            </div>

            {errorMsg && (
              <div style={styles.errorBox}>
                <span>⚠</span>
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleLoginSubmit} style={styles.loginForm}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>INVESTIGATOR EMAIL</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@ufdr.org"
                  required
                  autoFocus
                  style={styles.formInput}
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.formLabel}>PASSWORD</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                  style={styles.formInput}
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                style={{
                  ...styles.modalSubmitBtn,
                  opacity: isLoading ? 0.7 : 1,
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {isLoading ? 'AUTHENTICATING...' : 'ACCESS FORENSIC WORKSTATION'}
              </button>
            </form>

            <div style={styles.modalFooter}>
              <span>Argon2id Hashing • JWT RS/HS256 • Case-Scoped RBAC Enforcement</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  pageWrapper: {
    backgroundColor: '#0B1220',
    color: '#F8FAFC',
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    minHeight: '100vh',
    width: '100%',
    position: 'relative',
    backgroundImage: 'radial-gradient(rgba(38, 52, 73, 0.35) 1px, transparent 1px)',
    backgroundSize: '24px 24px',
  },

  /* Navbar */
  navbar: {
    position: 'sticky',
    top: 0,
    zIndex: 100,
    backgroundColor: 'rgba(11, 18, 32, 0.95)',
    backdropFilter: 'blur(8px)',
    borderBottom: '1px solid #263449',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
  },
  navContainer: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '16px 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    cursor: 'pointer',
    userSelect: 'none',
  },
  logoSeal: {
    width: '38px',
    height: '38px',
    borderRadius: '50%',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    border: '1.5px solid #22D3EE',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sealSvg: {
    color: '#22D3EE',
  },
  brandTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '22px',
    fontWeight: 750,
    letterSpacing: '-0.5px',
  },
  brandDark: {
    color: '#F8FAFC',
  },
  brandGreen: {
    color: '#22D3EE',
  },
  navLinks: {
    display: 'flex',
    alignItems: 'center',
    gap: '32px',
  },
  navLink: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    fontWeight: 600,
    color: '#94A3B8',
    letterSpacing: '0.04em',
    padding: '6px 0',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    transition: 'color 0.2s',
  },
  navRight: {
    display: 'flex',
    alignItems: 'center',
  },
  pillButton: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    background: 'linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)',
    color: '#0B1220',
    fontSize: '13px',
    fontWeight: 700,
    letterSpacing: '0.02em',
    padding: '9px 20px',
    borderRadius: '24px',
    border: 'none',
    cursor: 'pointer',
    boxShadow: '0 2px 14px rgba(34, 211, 238, 0.3)',
    transition: 'all 0.2s ease',
  },

  /* Hero Section (Centered Alignment Preserved) */
  heroSection: {
    backgroundColor: 'transparent',
    padding: '90px 24px 70px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  ambientGlow: {
    position: 'absolute',
    top: '10%',
    left: '50%',
    transform: 'translateX(-50%)',
    width: '600px',
    height: '400px',
    background: 'radial-gradient(circle, rgba(34, 211, 238, 0.12) 0%, rgba(59, 130, 246, 0.05) 50%, transparent 70%)',
    pointerEvents: 'none',
    zIndex: 0,
    filter: 'blur(40px)',
  },
  heroContent: {
    maxWidth: '850px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '20px',
    position: 'relative',
    zIndex: 1,
  },
  heroBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 16px',
    borderRadius: '24px',
    backgroundColor: 'rgba(34, 211, 238, 0.08)',
    border: '1px solid rgba(34, 211, 238, 0.25)',
    color: '#22D3EE',
    fontSize: '12px',
    fontWeight: 600,
    fontFamily: "'Space Grotesk', sans-serif",
    letterSpacing: '0.2px',
    boxShadow: '0 2px 10px rgba(34, 211, 238, 0.1)',
  },
  heroBadgeDot: {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    backgroundColor: '#22D3EE',
    boxShadow: '0 0 8px #22D3EE',
  },
  heroHeading: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '68px',
    fontWeight: 750,
    lineHeight: 1.02,
    letterSpacing: '-1.5px',
  },
  heroNavy: {
    color: '#F8FAFC',
  },
  heroGreen: {
    color: '#22D3EE',
  },
  heroSubtitle: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '17px',
    color: '#94A3B8',
    lineHeight: 1.6,
    maxWidth: '680px',
    fontWeight: 400,
    marginTop: '6px',
  },
  heroCtaWrapper: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '14px',
    marginTop: '10px',
  },
  heroButtonGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  heroPrimaryButton: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    background: 'linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)',
    color: '#0B1220',
    fontSize: '15px',
    fontWeight: 700,
    padding: '14px 34px',
    borderRadius: '30px',
    border: 'none',
    cursor: 'pointer',
    boxShadow: '0 4px 20px rgba(34, 211, 238, 0.35)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    transition: 'all 0.2s ease',
  },
  heroSecondaryButton: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    backgroundColor: '#172033',
    color: '#F8FAFC',
    border: '1px solid #263449',
    fontSize: '15px',
    fontWeight: 600,
    padding: '14px 28px',
    borderRadius: '30px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  heroSubtext: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '13px',
    color: '#64748B',
    fontStyle: 'italic',
  },

  /* Stats Strip */
  statsStrip: {
    backgroundColor: '#111827',
    borderTop: '1px solid #263449',
    borderBottom: '1px solid #263449',
    padding: '24px',
  },
  statsContainer: {
    maxWidth: '1100px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-around',
    flexWrap: 'wrap',
    gap: '20px',
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '4px',
  },
  statNumber: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '22px',
    fontWeight: 700,
    color: '#22D3EE',
    letterSpacing: '-0.5px',
  },
  statLabel: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '12px',
    fontWeight: 500,
    color: '#94A3B8',
    letterSpacing: '0.3px',
  },
  statDivider: {
    width: '1px',
    height: '36px',
    backgroundColor: '#263449',
  },

  /* Features Section (3 Cards) */
  featuresSection: {
    padding: '80px 24px',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  featuresHeader: {
    textAlign: 'center',
    marginBottom: '50px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  featuresTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '40px',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.8px',
  },
  featuresSubtitle: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '13px',
    fontWeight: 650,
    color: '#22D3EE',
    letterSpacing: '2px',
  },
  cardsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: '28px',
  },
  card: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '24px',
    padding: '36px 32px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    transition: 'transform 0.2s, box-shadow 0.2s',
  },
  cardIconBox: {
    marginBottom: '16px',
  },
  cardTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '26px',
    fontWeight: 700,
    color: '#F8FAFC',
    marginBottom: '28px',
    letterSpacing: '-0.4px',
  },
  stepList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '22px',
    flex: 1,
  },
  stepRow: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '14px',
  },
  stepCircle: {
    fontFamily: "'IBM Plex Mono', monospace",
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    border: '1.5px solid #22D3EE',
    backgroundColor: 'rgba(34, 211, 238, 0.1)',
    color: '#22D3EE',
    fontSize: '12px',
    fontWeight: 700,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: '2px',
  },
  stepContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '3px',
  },
  stepTitle: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '15px',
    fontWeight: 650,
    color: '#F8FAFC',
  },
  stepDesc: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    color: '#94A3B8',
    lineHeight: 1.55,
    fontWeight: 400,
  },
  cardFooterLink: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    marginTop: '36px',
    paddingTop: '16px',
    borderTop: '1px solid #263449',
    fontSize: '12px',
    fontWeight: 700,
    color: '#22D3EE',
    letterSpacing: '1px',
    cursor: 'pointer',
    textAlign: 'center',
    userSelect: 'none',
  },

  /* How It Works */
  howItWorksSection: {
    backgroundColor: '#111827',
    borderTop: '1px solid #263449',
    borderBottom: '1px solid #263449',
    padding: '80px 24px',
  },
  howItWorksContainer: {
    maxWidth: '1100px',
    margin: '0 auto',
  },
  howHeader: {
    textAlign: 'center',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '50px',
  },
  badgePill: {
    fontFamily: "'IBM Plex Mono', monospace",
    backgroundColor: '#1E293B',
    border: '1px solid #263449',
    color: '#22D3EE',
    fontSize: '11px',
    fontWeight: 600,
    letterSpacing: '1.5px',
    padding: '4px 12px',
    borderRadius: '9999px',
  },
  howTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '36px',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.6px',
  },
  howSubtitle: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '16px',
    color: '#94A3B8',
    lineHeight: 1.6,
    maxWidth: '580px',
  },
  pipelineGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '24px',
  },
  pipelineStep: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '16px',
    padding: '28px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  pipelineNum: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    width: '36px',
    height: '36px',
    borderRadius: '50%',
    backgroundColor: 'rgba(34, 211, 238, 0.15)',
    border: '1.5px solid #22D3EE',
    color: '#22D3EE',
    fontWeight: 700,
    fontSize: '16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  pipelineStepTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '17px',
    fontWeight: 700,
    color: '#F8FAFC',
  },
  pipelineStepText: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    color: '#94A3B8',
    lineHeight: 1.6,
  },

  /* Security Banner */
  securityBanner: {
    backgroundColor: '#172033',
    borderTop: '1px solid #263449',
    borderBottom: '1px solid #263449',
    padding: '40px 24px',
  },
  securityInner: {
    maxWidth: '1100px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '24px',
    flexWrap: 'wrap',
  },
  securityShield: {
    width: '60px',
    height: '60px',
    borderRadius: '16px',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1.5px solid #10B981',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  securityText: {
    flex: 1,
    minWidth: '280px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  securityTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '20px',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.3px',
  },
  securityDesc: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    color: '#94A3B8',
    lineHeight: 1.6,
    maxWidth: '680px',
  },
  securityButton: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    backgroundColor: '#10B981',
    color: '#0B1220',
    fontSize: '14px',
    fontWeight: 700,
    padding: '12px 26px',
    borderRadius: '9999px',
    border: 'none',
    cursor: 'pointer',
    boxShadow: '0 0 16px rgba(16, 185, 129, 0.3)',
  },

  /* Footer (Exact 3-Column Layout) */
  footer: {
    backgroundColor: '#0B1220',
    color: '#94A3B8',
    padding: '70px 24px 30px',
    borderTop: '1px solid #263449',
  },
  footerContainer: {
    maxWidth: '1200px',
    margin: '0 auto',
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 1.5fr',
    gap: '50px',
    marginBottom: '50px',
  },
  footerColBrand: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  footerLogo: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '24px',
    fontWeight: 700,
    letterSpacing: '-0.5px',
  },
  footerLogoDark: {
    color: '#F8FAFC',
  },
  footerLogoGreen: {
    color: '#22D3EE',
  },
  footerDescription: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    lineHeight: 1.6,
    color: '#94A3B8',
    maxWidth: '380px',
  },
  footerCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  footerColTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '18px',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.3px',
  },
  footerLinkList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  footerLink: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '14px',
    color: '#94A3B8',
    cursor: 'pointer',
    transition: 'color 0.2s',
  },
  footerContactList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    fontSize: '14px',
  },
  footerContactItem: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    color: '#94A3B8',
  },
  footerAddressBlock: {
    marginTop: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  footerAddressLabel: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontWeight: 700,
    color: '#F8FAFC',
    fontSize: '14px',
  },
  footerAddressText: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    color: '#94A3B8',
    lineHeight: 1.5,
    fontSize: '14px',
  },
  footerBottomBar: {
    maxWidth: '1200px',
    margin: '0 auto',
    paddingTop: '24px',
    borderTop: '1px solid #263449',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '13px',
    color: '#64748B',
  },
  footerCopyright: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    color: '#64748B',
    fontSize: '13px',
  },

  /* Modal */
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(11, 18, 32, 0.85)',
    backdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
  },
  modalContent: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '16px',
    width: '100%',
    maxWidth: '460px',
    padding: '32px',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
    display: 'flex',
    flexDirection: 'column',
    gap: '18px',
    position: 'relative',
    animation: 'fadeIn 0.2s ease-out',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  modalTitleBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  modalBadge: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '11px',
    fontWeight: 600,
    color: '#22D3EE',
    letterSpacing: '1px',
  },
  modalTitle: {
    fontFamily: "'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif",
    fontSize: '22px',
    fontWeight: 700,
    color: '#F8FAFC',
    letterSpacing: '-0.3px',
  },
  modalCloseBtn: {
    color: '#94A3B8',
    fontSize: '18px',
    padding: '4px',
    lineHeight: 1,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
  },
  demoBox: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '8px',
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  demoBoxHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '11px',
    fontWeight: 700,
    color: '#10B981',
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
  },
  demoBoxText: {
    fontSize: '13px',
    color: '#94A3B8',
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
  },
  demoCode: {
    backgroundColor: '#1E293B',
    color: '#22D3EE',
    padding: '1px 5px',
    borderRadius: '4px',
    fontFamily: "'IBM Plex Mono', monospace",
    fontWeight: 600,
  },
  autofillBtn: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    alignSelf: 'flex-start',
    backgroundColor: '#1E293B',
    border: '1px solid #263449',
    color: '#22D3EE',
    fontSize: '11px',
    fontWeight: 650,
    padding: '5px 12px',
    borderRadius: '9999px',
    cursor: 'pointer',
    marginTop: '4px',
  },
  errorBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid #EF4444',
    borderRadius: '8px',
    padding: '10px 12px',
    fontSize: '13px',
    color: '#EF4444',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
  },
  loginForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  formLabel: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '11px',
    fontWeight: 600,
    color: '#94A3B8',
    letterSpacing: '0.5px',
  },
  formInput: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    backgroundColor: '#111827',
    border: '1.5px solid #263449',
    borderRadius: '6px',
    padding: '12px 14px',
    fontSize: '14px',
    color: '#F8FAFC',
    outline: 'none',
  },
  modalSubmitBtn: {
    fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    fontWeight: 700,
    fontSize: '14px',
    letterSpacing: '0.5px',
    padding: '13px',
    borderRadius: '9999px',
    border: 'none',
    marginTop: '6px',
    boxShadow: '0 0 16px rgba(34, 211, 238, 0.3)',
    cursor: 'pointer',
  },
  modalFooter: {
    fontFamily: "'IBM Plex Mono', monospace",
    textAlign: 'center',
    fontSize: '11px',
    color: '#64748B',
    borderTop: '1px solid #263449',
    paddingTop: '12px',
  },
};
