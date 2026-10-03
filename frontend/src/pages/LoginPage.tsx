import React, { useState } from 'react';
import { useAuth } from '../services/authContext';

export const LoginPage: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!email || !password) {
      setErrorMsg('Please enter both your investigative email and password.');
      return;
    }

    try {
      await login({ email, password });
    } catch (err: any) {
      setErrorMsg(err.message || 'Authentication failed. Please verify your credentials.');
    }
  };

  const handleFillAdmin = () => {
    setEmail('admin@ufdr.org');
    setPassword('helloitsme');
  };

  return (
    <div style={styles.container}>
      <div style={styles.loginCard}>
        {/* Header Branding */}
        <div style={styles.brandHeader}>
          <img
            src="/foreniq-logo.png"
            alt="ForenIQ"
            style={{ height: '46px', width: 'auto', display: 'block', margin: '0 auto 16px auto', objectFit: 'contain' }}
          />
          <div style={styles.badge}>UFDR FORENSICS</div>
          <h1 style={styles.title}>Investigator Workstation</h1>
          <p style={styles.subtitle}>
            AI-Driven Intelligent UFDR Analysis System — Digital Forensic Investigation Platform
          </p>
        </div>

        {/* Security / Dev Hint Callout */}
        <div style={styles.hintBox}>
          <div style={styles.hintHeader}>
            <span style={styles.hintIcon}>🛡</span>
            <strong>BOOTSTRAP ADMIN CREDENTIALS</strong>
          </div>
          <div style={styles.hintText}>
            Email: <code style={styles.code}>admin@ufdr.org</code>
            <br />
            Password: <code style={styles.code}>helloitsme</code>
          </div>
          <button type="button" onClick={handleFillAdmin} style={styles.autofillBtn}>
            Autofill Admin Credentials
          </button>
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div style={styles.errorAlert}>
            <span style={styles.errorIcon}>⚠</span>
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.fieldGroup}>
            <label style={styles.label}>INVESTIGATOR EMAIL</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. detective@ufdr.org"
              required
              autoFocus
              style={styles.input}
            />
          </div>

          <div style={styles.fieldGroup}>
            <label style={styles.label}>PASSWORD</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              style={styles.input}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              ...styles.submitBtn,
              opacity: isLoading ? 0.7 : 1,
              cursor: isLoading ? 'not-allowed' : 'pointer',
            }}
          >
            {isLoading ? 'AUTHENTICATING...' : 'ACCESS FORENSIC WORKSTATION'}
          </button>
        </form>

        <div style={styles.cardFooter}>
          <span>Security Standard: Argon2id Hashing • JWT RS/HS256 • Role-Based Case Scoping</span>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    height: '100vh',
    width: '100vw',
    backgroundColor: 'var(--bg-primary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '20px',
  },
  loginCard: {
    width: '100%',
    maxWidth: '460px',
    backgroundColor: 'var(--bg-surface)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '8px',
    padding: '36px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  brandHeader: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    gap: '8px',
  },
  badge: {
    backgroundColor: 'var(--accent-blue)',
    color: '#ffffff',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    padding: '4px 10px',
    borderRadius: '4px',
    letterSpacing: '1px',
  },
  title: {
    fontSize: '20px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    letterSpacing: '-0.3px',
  },
  subtitle: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    lineHeight: 1.4,
  },
  hintBox: {
    backgroundColor: 'rgba(56, 189, 248, 0.08)',
    border: '1px solid rgba(56, 189, 248, 0.25)',
    borderRadius: '6px',
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  hintHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '11px',
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.5px',
  },
  hintIcon: {
    fontSize: '12px',
  },
  hintText: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    lineHeight: 1.5,
  },
  code: {
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    padding: '2px 6px',
    borderRadius: '3px',
    color: 'var(--text-primary)',
  },
  autofillBtn: {
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    color: 'var(--accent-cyan)',
    border: '1px solid rgba(56, 189, 248, 0.4)',
    fontSize: '11px',
    fontWeight: 600,
    padding: '4px 10px',
    borderRadius: '4px',
    marginTop: '4px',
  },
  errorAlert: {
    backgroundColor: 'rgba(244, 63, 94, 0.12)',
    border: '1px solid rgba(244, 63, 94, 0.3)',
    borderRadius: '4px',
    padding: '10px 14px',
    fontSize: '12px',
    color: 'var(--accent-rose)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  errorIcon: {
    fontSize: '14px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '10px',
    fontWeight: 700,
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.8px',
  },
  input: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '4px',
    padding: '10px 12px',
    color: 'var(--text-primary)',
    fontSize: '13px',
    fontFamily: 'inherit',
    outline: 'none',
  },
  submitBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    fontWeight: 800,
    fontSize: '12px',
    letterSpacing: '0.8px',
    padding: '12px',
    borderRadius: '4px',
    marginTop: '6px',
    boxShadow: '0 4px 14px rgba(34, 211, 238, 0.3)',
    transition: 'all 0.2s',
  },
  cardFooter: {
    textAlign: 'center',
    fontSize: '10px',
    color: 'var(--text-muted)',
    borderTop: '1px solid var(--border-subtle)',
    paddingTop: '14px',
  },
};
