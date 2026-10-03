import React, { useEffect, useState } from 'react';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type { ArtifactType, TimelineEvent, TimelineFilterRequest, TimelineResponse } from '../types/timeline_anomaly';

interface TimelineViewProps {
  caseId: string;
  caseData?: Case | null;
}

export const TimelineView: React.FC<TimelineViewProps> = ({ caseId, caseData }) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [timelineData, setTimelineData] = useState<TimelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [startTime, setStartTime] = useState<string>('');
  const [endTime, setEndTime] = useState<string>('');
  const [entityQuery, setEntityQuery] = useState<string>('');
  const [selectedTypes, setSelectedTypes] = useState<ArtifactType[]>([
    'CALL',
    'MESSAGE',
    'LOCATION',
    'APPLICATION',
    'BROWSER',
    'FILESYSTEM',
  ]);

  // Selected event for drawer
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);

  const fetchTimeline = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload: TimelineFilterRequest = {
        start_time: startTime || undefined,
        end_time: endTime || undefined,
        entity_value: entityQuery || undefined,
        artifact_types: selectedTypes.length > 0 ? selectedTypes : undefined,
        limit: 1000,
        offset: 0,
      };
      const res = await apiClient.queryTimeline(caseId, payload);
      setTimelineData(res);
      if (res.events.length > 0 && !selectedEvent) {
        setSelectedEvent(res.events[0]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch timeline records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      fetchTimeline();
    }
  }, [caseId]);

  const toggleType = (t: ArtifactType) => {
    if (selectedTypes.includes(t)) {
      setSelectedTypes(selectedTypes.filter((x) => x !== t));
    } else {
      setSelectedTypes([...selectedTypes, t]);
    }
  };

  const getEventIcon = (type: ArtifactType) => {
    switch (type) {
      case 'CALL':
        return '📞';
      case 'MESSAGE':
        return '💬';
      case 'LOCATION':
        return '📍';
      case 'APPLICATION':
        return '📱';
      case 'BROWSER':
        return '🌐';
      case 'FILESYSTEM':
        return '📁';
      default:
        return '📄';
    }
  };

  return (
    <div style={styles.container}>
      {/* Top Header */}
      <div style={styles.header}>
        <div>
          <div style={styles.badge}>CASE SCOPED FORENSIC TIMELINE</div>
          <h2 style={styles.title}>Unified Chronological Timeline</h2>
          <p style={styles.subtitle}>
            Normalized multi-source forensic events ordered chronologically with complete lineage and evidence traceability.
          </p>
        </div>
        <div style={styles.caseBadge}>
          <span style={styles.caseLabel}>CASE:</span> {caseData?.case_number || caseId}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div style={styles.filterToolbar}>
        <div style={styles.filterGroup}>
          <label style={styles.filterLabel}>START DATE / TIME</label>
          <input
            type="datetime-local"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            style={styles.input}
          />
        </div>

        <div style={styles.filterGroup}>
          <label style={styles.filterLabel}>END DATE / TIME</label>
          <input
            type="datetime-local"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            style={styles.input}
          />
        </div>

        <div style={styles.filterGroup}>
          <label style={styles.filterLabel}>SEARCH PARTICIPANT / NUMBER</label>
          <input
            type="text"
            placeholder="e.g. +919876543210 or Rahul"
            value={entityQuery}
            onChange={(e) => setEntityQuery(e.target.value)}
            style={styles.input}
          />
        </div>

        <button onClick={fetchTimeline} disabled={loading} style={styles.applyBtn}>
          {loading ? 'FILTERING...' : '⚡ APPLY FILTERS'}
        </button>
      </div>

      {/* Artifact Type Checkbox Ribbon */}
      <div style={styles.typeRibbon}>
        <span style={styles.ribbonLabel}>EVENT CATEGORIES:</span>
        {(['CALL', 'MESSAGE', 'LOCATION', 'APPLICATION', 'BROWSER', 'FILESYSTEM'] as ArtifactType[]).map((t) => (
          <button
            key={t}
            onClick={() => toggleType(t)}
            style={{
              ...styles.typeBtn,
              backgroundColor: selectedTypes.includes(t) ? 'rgba(0, 240, 255, 0.15)' : 'rgba(255, 255, 255, 0.05)',
              borderColor: selectedTypes.includes(t) ? 'var(--accent-cyan)' : 'var(--border-subtle)',
              color: selectedTypes.includes(t) ? 'var(--accent-cyan)' : 'var(--text-muted)',
            }}
          >
            {getEventIcon(t)} {t}
          </button>
        ))}
      </div>

      {/* Summary Stats Strip */}
      {timelineData && (
        <div style={styles.statsStrip}>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{timelineData.total_events}</span>
            <span style={styles.statLbl}>TOTAL EVENTS</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{timelineData.earliest_timestamp?.split('T')[0] || 'N/A'}</span>
            <span style={styles.statLbl}>EARLIEST BOUND</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statVal}>{timelineData.latest_timestamp?.split('T')[0] || 'N/A'}</span>
            <span style={styles.statLbl}>LATEST BOUND</span>
          </div>
          {Object.entries(timelineData.event_distribution).map(([type, count]) => (
            <div key={type} style={styles.statItem}>
              <span style={styles.statVal}>{count}</span>
              <span style={styles.statLbl}>{type}</span>
            </div>
          ))}
        </div>
      )}

      {/* Main Timeline Body */}
      <div style={styles.mainLayout}>
        {/* Events Feed */}
        <div style={styles.feedContainer}>
          {error && <div style={styles.errorBanner}>{error}</div>}

          {timelineData && timelineData.events.length === 0 ? (
            <div style={styles.emptyPrompt}>
              <div style={{ fontSize: '32px' }}>⏱️</div>
              <div>No timeline events match the selected criteria.</div>
            </div>
          ) : (
            timelineData?.events.map((ev, idx) => {
              const isSelected = selectedEvent?.event_id === ev.event_id;
              return (
                <div
                  key={ev.event_id || idx}
                  onClick={() => setSelectedEvent(ev)}
                  style={{
                    ...styles.eventCard,
                    borderColor: isSelected ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                    backgroundColor: isSelected ? 'rgba(0, 240, 255, 0.08)' : 'var(--bg-card)',
                  }}
                >
                  <div style={styles.cardHeader}>
                    <span style={styles.eventTime}>
                      {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : 'Timestamp Unavailable'}
                    </span>
                    <span style={styles.eventTypeBadge}>
                      {getEventIcon(ev.event_type)} {ev.event_type}
                    </span>
                  </div>

                  <div style={styles.cardBody}>
                    <div style={styles.cardActors}>
                      {ev.actor && <span style={styles.actorName}>👤 {ev.actor}</span>}
                      {ev.actor && ev.target && <span style={styles.arrow}>→</span>}
                      {ev.target && <span style={styles.targetName}>🎯 {ev.target}</span>}
                    </div>

                    {ev.content_summary && <div style={styles.contentSummary}>{ev.content_summary}</div>}

                    <div style={styles.cardMeta}>
                      {ev.application && <span>App: {ev.application}</span>}
                      {ev.device && <span>Device: {ev.device}</span>}
                      <span>Source: {ev.source_file}</span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Selected Event Details Inspector Drawer */}
        {selectedEvent && (
          <div style={styles.inspectorDrawer}>
            <div style={styles.drawerHeader}>
              <h3 style={styles.drawerTitle}>EVENT INSPECTOR</h3>
              <button onClick={() => setSelectedEvent(null)} style={styles.closeBtn}>
                ✕
              </button>
            </div>

            <div style={styles.drawerSection}>
              <div style={styles.drawerLabel}>TIMESTAMP</div>
              <div style={styles.drawerValue}>
                {selectedEvent.timestamp ? new Date(selectedEvent.timestamp).toUTCString() : 'N/A'}
              </div>
              <div style={styles.drawerSubtext}>
                Precision: {selectedEvent.timestamp_precision} | Status: {selectedEvent.timestamp_status}
              </div>
            </div>

            <div style={styles.drawerSection}>
              <div style={styles.drawerLabel}>EVENT TYPE & APPLICATION</div>
              <div style={styles.drawerValue}>
                {selectedEvent.event_type} {selectedEvent.application ? `(${selectedEvent.application})` : ''}
              </div>
            </div>

            <div style={styles.drawerSection}>
              <div style={styles.drawerLabel}>ACTOR & TARGET</div>
              <div style={styles.drawerValue}>
                From: {selectedEvent.actor || 'N/A'}
                <br />
                To: {selectedEvent.target || 'N/A'}
              </div>
            </div>

            {selectedEvent.content_summary && (
              <div style={styles.drawerSection}>
                <div style={styles.drawerLabel}>CONTENT SUMMARY</div>
                <div style={styles.drawerValue}>{selectedEvent.content_summary}</div>
              </div>
            )}

            <div style={styles.drawerSection}>
              <div style={styles.drawerLabel}>FORENSIC TRACEABILITY</div>
              <div style={styles.drawerSubtext}>
                <strong>Artifact ID:</strong> {selectedEvent.artifact_id}
                <br />
                <strong>Evidence ID:</strong> {selectedEvent.evidence_id}
                <br />
                <strong>Source File:</strong> {selectedEvent.source_file}
                <br />
                <strong>Source Path:</strong> {selectedEvent.source_path}
              </div>
            </div>

            {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
              <div style={styles.drawerSection}>
                <div style={styles.drawerLabel}>METADATA ATTRIBUTES</div>
                <pre style={styles.metaJson}>{JSON.stringify(selectedEvent.metadata, null, 2)}</pre>
              </div>
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
    backgroundColor: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    boxSizing: 'border-box',
    overflowY: 'auto',
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
    fontFamily: 'var(--font-mono)',
    color: 'var(--accent-cyan)',
    letterSpacing: '1px',
    marginBottom: '4px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 800,
    margin: 0,
    color: 'var(--text-primary)',
  },
  subtitle: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    margin: '4px 0 0 0',
  },
  caseBadge: {
    backgroundColor: 'rgba(0, 240, 255, 0.08)',
    border: '1px solid rgba(0, 240, 255, 0.2)',
    padding: '6px 12px',
    borderRadius: '4px',
    fontSize: '12px',
    fontFamily: 'var(--font-mono)',
  },
  caseLabel: {
    color: 'var(--text-muted)',
    fontWeight: 700,
  },
  filterToolbar: {
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-end',
    backgroundColor: 'var(--bg-secondary)',
    padding: '16px',
    borderRadius: '6px',
    border: '1px solid var(--border-subtle)',
    marginBottom: '12px',
    flexWrap: 'wrap',
  },
  filterGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    flex: 1,
    minWidth: '180px',
  },
  filterLabel: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    color: 'var(--text-muted)',
  },
  input: {
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-subtle)',
    color: 'var(--text-primary)',
    padding: '8px 12px',
    borderRadius: '4px',
    fontSize: '12px',
    outline: 'none',
  },
  applyBtn: {
    backgroundColor: 'var(--accent-cyan)',
    color: '#000000',
    border: 'none',
    padding: '9px 18px',
    borderRadius: '4px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
    height: '35px',
  },
  typeRibbon: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  ribbonLabel: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    marginRight: '4px',
  },
  typeBtn: {
    border: '1px solid',
    borderRadius: '4px',
    padding: '4px 10px',
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  },
  statsStrip: {
    display: 'flex',
    gap: '16px',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    padding: '10px 16px',
    borderRadius: '4px',
    border: '1px solid var(--border-subtle)',
    marginBottom: '16px',
    overflowX: 'auto',
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
    minHeight: '400px',
  },
  feedContainer: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    overflowY: 'auto',
  },
  eventCard: {
    border: '1px solid',
    borderRadius: '6px',
    padding: '14px',
    cursor: 'pointer',
    transition: 'border-color 0.2s',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  eventTime: {
    fontSize: '11px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
  },
  eventTypeBadge: {
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  cardBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  cardActors: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    fontWeight: 600,
  },
  actorName: {
    color: 'var(--text-primary)',
  },
  arrow: {
    color: 'var(--accent-cyan)',
  },
  targetName: {
    color: 'var(--accent-cyan)',
  },
  contentSummary: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    lineHeight: '1.4',
  },
  cardMeta: {
    display: 'flex',
    gap: '12px',
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    marginTop: '4px',
  },
  inspectorDrawer: {
    width: '380px',
    backgroundColor: 'var(--bg-secondary)',
    border: '1px solid var(--border-subtle)',
    borderRadius: '6px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    overflowY: 'auto',
  },
  drawerHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid var(--border-subtle)',
    paddingBottom: '10px',
  },
  drawerTitle: {
    fontSize: '13px',
    fontFamily: 'var(--font-mono)',
    color: 'var(--accent-cyan)',
    margin: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    fontSize: '14px',
  },
  drawerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  drawerLabel: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    fontWeight: 700,
    color: 'var(--text-muted)',
  },
  drawerValue: {
    fontSize: '12px',
    color: 'var(--text-primary)',
    lineHeight: '1.4',
  },
  drawerSubtext: {
    fontSize: '11px',
    color: 'var(--text-muted)',
    fontFamily: 'var(--font-mono)',
    lineHeight: '1.5',
    marginTop: '2px',
  },
  metaJson: {
    fontSize: '10px',
    fontFamily: 'var(--font-mono)',
    backgroundColor: 'var(--bg-primary)',
    padding: '8px',
    borderRadius: '4px',
    color: 'var(--accent-cyan)',
    overflowX: 'auto',
  },
  errorBanner: {
    backgroundColor: 'rgba(255, 60, 60, 0.1)',
    border: '1px solid rgba(255, 60, 60, 0.3)',
    color: '#ff6b6b',
    padding: '12px',
    borderRadius: '4px',
    fontSize: '12px',
  },
  emptyPrompt: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px',
    color: 'var(--text-muted)',
    gap: '10px',
  },
};
