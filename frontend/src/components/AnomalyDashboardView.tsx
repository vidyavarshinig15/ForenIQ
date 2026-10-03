import React, { useState } from 'react';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type {
  AnomalyAlgorithm,
  AnomalyDetectionRequest,
  AnomalyDetectionResponse,
  AnomalyResult,
  TemporalWindowSize,
} from '../types/timeline_anomaly';

interface AnomalyDashboardViewProps {
  caseId: string;
  caseData?: Case | null;
  onNavigateToGraph?: (centerEntity?: string) => void;
}

export const AnomalyDashboardView: React.FC<AnomalyDashboardViewProps> = ({
  caseId,
  caseData,
  onNavigateToGraph,
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [response, setResponse] = useState<AnomalyDetectionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Configuration options
  const [windowSize, setWindowSize] = useState<TemporalWindowSize>('15m');
  const [algorithm, setAlgorithm] = useState<AnomalyAlgorithm>('ISOLATION_FOREST');
  const [contamination, setContamination] = useState<number>(0.05);
  const [targetEntity, setTargetEntity] = useState<string>('');
  const [targetApp, setTargetApp] = useState<string>('');

  // Selected anomaly details modal
  const [selectedAnomaly, setSelectedAnomaly] = useState<AnomalyResult | null>(null);

  const runDetection = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: AnomalyDetectionRequest = {
        window_size: windowSize,
        algorithm: algorithm,
        contamination: contamination,
        target_entity: targetEntity || undefined,
        target_application: targetApp || undefined,
        score_threshold: 0.60,
      };
      const res = await apiClient.detectAnomalies(caseId, payload);
      setResponse(res);
      if (res.anomalies.length > 0) {
        setSelectedAnomaly(res.anomalies[0]);
      }
    } catch (err: any) {
      setError(err?.message || 'Anomaly detection execution failed');
    } finally {
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL_ANOMALY':
        return '#EF4444'; // Red only for genuinely critical
      case 'HIGH_ANOMALY':
      case 'MODERATE_ANOMALY':
        return '#F59E0B'; // Amber as primary anomaly/warning color
      case 'LOW_ANOMALY':
        return '#3B82F6'; // AI / primary blue for low severity
      default:
        return '#94A3B8';
    }
  };

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <div style={styles.badge}>STATISTICAL ANOMALY DETECTION</div>
          <h2 style={styles.title}>Forensic Behavioral & Temporal Anomaly Analysis</h2>
          <p style={styles.subtitle}>
            Multidimensional Isolation Forest & baseline statistical modeling across temporal windows. All findings represent statistical deviations, not guilt or criminal intent.
          </p>
        </div>
        <div style={styles.caseBadge}>
          <span style={styles.caseLabel}>CASE:</span> {caseData?.case_number || caseId}
        </div>
      </div>

      {/* Control Panel */}
      <div style={styles.controlPanel}>
        <div style={styles.controlRow}>
          <div style={styles.controlGroup}>
            <label style={styles.label}>TEMPORAL WINDOW</label>
            <select
              value={windowSize}
              onChange={(e) => setWindowSize(e.target.value as TemporalWindowSize)}
              style={styles.select}
            >
              <option value="1m">1 Minute</option>
              <option value="5m">5 Minutes</option>
              <option value="15m">15 Minutes (Default)</option>
              <option value="30m">30 Minutes</option>
              <option value="1h">1 Hour</option>
              <option value="6h">6 Hours</option>
              <option value="24h">24 Hours</option>
            </select>
          </div>

          <div style={styles.controlGroup}>
            <label style={styles.label}>DETECTION ALGORITHM</label>
            <select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value as AnomalyAlgorithm)}
              style={styles.select}
            >
              <option value="ISOLATION_FOREST">Isolation Forest (Multivariate)</option>
              <option value="STATISTICAL_ZSCORE">Statistical Z-Score (Univariate)</option>
            </select>
          </div>

          <div style={styles.controlGroup}>
            <label style={styles.label}>CONTAMINATION ({contamination})</label>
            <input
              type="range"
              min="0.01"
              max="0.20"
              step="0.01"
              value={contamination}
              onChange={(e) => setContamination(parseFloat(e.target.value))}
              style={styles.range}
            />
          </div>

          <div style={styles.controlGroup}>
            <label style={styles.label}>TARGET PARTICIPANT (OPTIONAL)</label>
            <input
              type="text"
              placeholder="e.g. +919876543210"
              value={targetEntity}
              onChange={(e) => setTargetEntity(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.controlGroup}>
            <label style={styles.label}>TARGET APP (OPTIONAL)</label>
            <input
              type="text"
              placeholder="e.g. WhatsApp"
              value={targetApp}
              onChange={(e) => setTargetApp(e.target.value)}
              style={styles.input}
            />
          </div>

          <button onClick={runDetection} disabled={loading} style={styles.runBtn}>
            {loading ? 'ANALYZING TIMELINE...' : '🚀 RUN ANOMALY DETECTION'}
          </button>
        </div>
      </div>

      {error && <div style={styles.errorBanner}>{error}</div>}

      {/* Results Overview */}
      {response && (
        <div style={styles.statsStrip}>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{response.total_windows_analyzed}</span>
            <span style={styles.statLbl}>TOTAL WINDOWS</span>
          </div>
          <div style={styles.statItem}>
            <span style={{ ...styles.statVal, color: '#ffb86c' }}>{response.anomalies_detected}</span>
            <span style={styles.statLbl}>ANOMALIES DETECTED</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statVal}>
              {response.total_windows_analyzed > 0
                ? ((response.anomalies_detected / response.total_windows_analyzed) * 100).toFixed(1) + '%'
                : '0%'}
            </span>
            <span style={styles.statLbl}>ANOMALY RATE</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{response.model_metadata.execution_time_ms} ms</span>
            <span style={styles.statLbl}>PIPELINE LATENCY</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{response.algorithm}</span>
            <span style={styles.statLbl}>MODEL APPLIED</span>
          </div>
        </div>
      )}

      {/* Main Analysis Section */}
      <div style={styles.mainLayout}>
        {/* Anomaly Cards List */}
        <div style={styles.cardsContainer}>
          {!response && !loading && (
            <div style={styles.placeholderBox}>
              <div style={{ fontSize: '40px' }}>📊</div>
              <div style={{ fontWeight: 700, fontSize: '15px' }}>Ready to Execute Anomaly Detection</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '400px', textAlign: 'center' }}>
                Select temporal window parameters and click "Run Anomaly Detection" to detect statistical bursts, off-hours activity, and communication spikes.
              </div>
            </div>
          )}

          {response && response.anomalies.length === 0 && (
            <div style={styles.placeholderBox}>
              <div style={{ fontSize: '40px' }}>✅</div>
              <div style={{ fontWeight: 700, fontSize: '15px' }}>No Statistical Anomalies Detected</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                All observed time windows fall within standard statistical baseline bounds.
              </div>
            </div>
          )}

          {response?.anomalies.map((anom) => {
            const isSelected = selectedAnomaly?.anomaly_id === anom.anomaly_id;
            return (
              <div
                key={anom.anomaly_id}
                onClick={() => setSelectedAnomaly(anom)}
                style={{
                  ...styles.anomalyCard,
                  borderColor: isSelected ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                  backgroundColor: isSelected ? 'rgba(0, 240, 255, 0.05)' : 'var(--bg-secondary)',
                }}
              >
                <div style={styles.cardHeader}>
                  <span style={styles.cardTime}>
                    {new Date(anom.start_time).toLocaleString()} → {new Date(anom.end_time).toLocaleTimeString()}
                  </span>
                  <span
                    style={{
                      ...styles.severityBadge,
                      color: getSeverityColor(anom.severity),
                      borderColor: getSeverityColor(anom.severity),
                    }}
                  >
                    {anom.severity} ({Math.round(anom.anomaly_score * 100)}%)
                  </span>
                </div>

                <div style={styles.cardTitle}>{anom.anomaly_type.replace(/_/g, ' ')}</div>
                <div style={styles.cardExplanation}>{anom.factual_explanation}</div>

                <div style={styles.cardTags}>
                  <span>Events: {anom.supporting_event_ids.length}</span>
                  {anom.entities_involved.length > 0 && (
                    <span>Entities: {anom.entities_involved.slice(0, 3).join(', ')}</span>
                  )}
                  {anom.applications_involved.length > 0 && (
                    <span>Apps: {anom.applications_involved.join(', ')}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Anomaly Deep-Dive Inspector */}
        {selectedAnomaly && (
          <div style={styles.inspectorContainer}>
            <div style={styles.inspectorHeader}>
              <h3 style={styles.inspectorTitle}>ANOMALY CONTEXT & BASELINE COMPARISON</h3>
              <button onClick={() => setSelectedAnomaly(null)} style={styles.closeBtn}>
                ✕
              </button>
            </div>

            <div style={styles.inspectorSection}>
              <div style={styles.sectionLabel}>TIME WINDOW</div>
              <div style={styles.sectionValue}>
                {new Date(selectedAnomaly.start_time).toUTCString()}
                <br />
                <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>to</span>{' '}
                {new Date(selectedAnomaly.end_time).toUTCString()}
              </div>
            </div>

            <div style={styles.inspectorSection}>
              <div style={styles.sectionLabel}>STATISTICAL ANOMALY SCORE</div>
              <div style={styles.scoreBarContainer}>
                <div
                  style={{
                    ...styles.scoreBarFill,
                    width: `${Math.round(selectedAnomaly.anomaly_score * 100)}%`,
                    backgroundColor: getSeverityColor(selectedAnomaly.severity),
                  }}
                />
              </div>
              <div style={styles.scoreText}>
                Normalized Score: <strong>{selectedAnomaly.anomaly_score}</strong> | Model: {selectedAnomaly.algorithm}
              </div>
            </div>

            <div style={styles.inspectorSection}>
              <div style={styles.sectionLabel}>FACTUAL OBSERVATION</div>
              <div style={styles.explanationBox}>{selectedAnomaly.factual_explanation}</div>
            </div>

            {/* Feature Breakdown Table */}
            <div style={styles.inspectorSection}>
              <div style={styles.sectionLabel}>DEVIATION FROM BASELINE</div>
              <div style={styles.metricTable}>
                {selectedAnomaly.baseline_metrics.slice(0, 5).map((m) => (
                  <div key={m.feature_name} style={styles.metricRow}>
                    <span style={styles.metricFeat}>{m.feature_name}</span>
                    <span style={styles.metricObs}>Obs: {m.observed_value}</span>
                    <span style={styles.metricBase}>Median: {m.baseline_median}</span>
                    <span style={styles.metricZ}>z: {m.z_score}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Evidence Traceability */}
            <div style={styles.inspectorSection}>
              <div style={styles.sectionLabel}>SUPPORTING FORENSIC EVIDENCE ({selectedAnomaly.supporting_artifact_ids.length})</div>
              <div style={styles.artList}>
                {selectedAnomaly.supporting_artifact_ids.slice(0, 6).map((id, idx) => (
                  <div key={id || idx} style={styles.artBadge}>
                    Artifact: {id}
                  </div>
                ))}
                {selectedAnomaly.supporting_artifact_ids.length > 6 && (
                  <div style={styles.moreBadge}>+{selectedAnomaly.supporting_artifact_ids.length - 6} more</div>
                )}
              </div>
            </div>

            {/* Action Bridge */}
            {onNavigateToGraph && selectedAnomaly.entities_involved.length > 0 && (
              <button
                onClick={() => onNavigateToGraph(selectedAnomaly.entities_involved[0])}
                style={styles.bridgeBtn}
              >
                🕸️ VIEW IN COMMUNICATION GRAPH →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    padding: '24px',
    backgroundColor: '#0B1220',
    color: '#F8FAFC',
    boxSizing: 'border-box',
    overflowY: 'auto',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '20px',
  },
  badge: {
    display: 'inline-block',
    fontSize: '10px',
    fontWeight: 700,
    fontFamily: '"IBM Plex Mono", monospace',
    color: '#22D3EE',
    letterSpacing: '0.05em',
    marginBottom: '4px',
  },
  title: {
    fontFamily: '"Space Grotesk", sans-serif',
    fontSize: '22px',
    fontWeight: 700,
    margin: 0,
    color: '#F8FAFC',
    letterSpacing: '-0.02em',
  },
  subtitle: {
    fontSize: '13px',
    color: '#94A3B8',
    margin: '4px 0 0 0',
    maxWidth: '700px',
  },
  caseBadge: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    padding: '6px 12px',
    borderRadius: '2px',
    fontSize: '12px',
    fontFamily: '"IBM Plex Mono", monospace',
    color: '#22D3EE',
  },
  caseLabel: {
    color: '#64748B',
    fontWeight: 700,
  },
  controlPanel: {
    backgroundColor: '#111827',
    padding: '16px',
    borderRadius: '4px',
    border: '1px solid #263449',
    marginBottom: '16px',
  },
  controlRow: {
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-end',
    flexWrap: 'wrap',
  },
  controlGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    flex: 1,
    minWidth: '160px',
  },
  label: {
    fontSize: '10px',
    fontFamily: '"IBM Plex Mono", monospace',
    fontWeight: 700,
    color: '#64748B',
    letterSpacing: '0.05em',
  },
  select: {
    backgroundColor: '#0B1220',
    border: '1px solid #263449',
    color: '#F8FAFC',
    padding: '8px 12px',
    borderRadius: '2px',
    fontSize: '12px',
    outline: 'none',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  input: {
    backgroundColor: '#0B1220',
    border: '1px solid #263449',
    color: '#F8FAFC',
    padding: '8px 12px',
    borderRadius: '2px',
    fontSize: '12px',
    outline: 'none',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  range: {
    marginTop: '6px',
    accentColor: '#22D3EE',
  },
  runBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '2px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: '"Space Grotesk", sans-serif',
    cursor: 'pointer',
    height: '35px',
    letterSpacing: '0.05em',
  },
  statsStrip: {
    display: 'flex',
    gap: '16px',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    padding: '10px 16px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
    marginBottom: '16px',
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    borderRight: '1px solid var(--border-subtle)',
    paddingRight: '16px',
  },
  statVal: {
    fontSize: '14px',
    fontWeight: 700,
    color: 'var(--accent-cyan)',
    fontFamily: 'var(--font-mono)',
  },
  statLbl: {
    fontSize: '9px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  mainLayout: {
    display: 'flex',
    gap: '20px',
    flex: 1,
  },
  cardsContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  anomalyCard: {
    border: '1px solid',
    borderRadius: '6px',
    padding: '16px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  cardTime: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  severityBadge: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    border: '1px solid',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  cardTitle: {
    fontSize: '14px',
    fontWeight: 700,
    marginBottom: '4px',
    color: 'var(--text-primary)',
  },
  cardExplanation: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    lineHeight: '1.4',
    marginBottom: '8px',
  },
  cardTags: {
    display: 'flex',
    gap: '12px',
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  inspectorContainer: {
    width: '400px',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    overflowY: 'auto',
  },
  inspectorHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '10px',
  },
  inspectorTitle: {
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--accent-cyan)',
    margin: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
  },
  inspectorSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  sectionLabel: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    color: 'var(--text-muted)',
  },
  sectionValue: {
    fontSize: '12px',
    lineHeight: '1.4',
  },
  scoreBarContainer: {
    height: '6px',
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  scoreBarFill: {
    height: '100%',
  },
  scoreText: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  explanationBox: {
    backgroundColor: 'var(--bg-primary)',
    padding: '10px',
    borderRadius: '4px',
    fontSize: '12px',
    lineHeight: '1.4',
    border: '1px solid var(--border-subtle)',
  },
  metricTable: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    padding: '4px 8px',
    borderRadius: '3px',
  },
  metricFeat: {
    color: 'var(--text-primary)',
    fontWeight: 600,
  },
  metricObs: {
    color: 'var(--accent-cyan)',
  },
  metricBase: {
    color: 'var(--text-muted)',
  },
  metricZ: {
    color: '#ffb86c',
  },
  artList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  artBadge: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    backgroundColor: 'var(--bg-primary)',
    padding: '4px 6px',
    borderRadius: '3px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  moreBadge: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--accent-cyan)',
  },
  bridgeBtn: {
    backgroundColor: 'rgba(0, 240, 255, 0.1)',
    border: '1px solid var(--accent-cyan)',
    color: 'var(--accent-cyan)',
    padding: '10px',
    borderRadius: '4px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    cursor: 'pointer',
    marginTop: '8px',
  },
  placeholderBox: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px',
    gap: '12px',
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: '6px',
    border: '1px dashed var(--border-subtle)',
  },
  errorBanner: {
    backgroundColor: 'rgba(255, 60, 60, 0.1)',
    border: '1px solid rgba(255, 60, 60, 0.3)',
    color: '#ff6b6b',
    padding: '12px',
    borderRadius: '4px',
    fontSize: '12px',
    marginBottom: '16px',
  },
};
