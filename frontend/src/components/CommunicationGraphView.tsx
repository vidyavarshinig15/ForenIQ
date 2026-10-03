import React, { useEffect, useRef, useState } from 'react';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type {
  EdgeType,
  GraphEdge,
  GraphNode,
  GraphQueryResponse,
  GraphSnapshotRecord,
  NodeType,
} from '../types/graph';

interface CommunicationGraphViewProps {
  caseId: string;
  caseData: Case | null;
}

// Community color palette
const COMMUNITY_COLORS = [
  '#38bdf8', // sky
  '#34d399', // emerald
  '#fbbf24', // amber
  '#f472b6', // pink
  '#a78bfa', // purple
  '#fb923c', // orange
  '#2dd4bf', // teal
  '#818cf8', // indigo
];

// Node type color palette
const NODE_TYPE_COLORS: Record<NodeType, string> = {
  PERSON: '#38bdf8',
  PHONE_NUMBER: '#34d399',
  EMAIL: '#fbbf24',
  ACCOUNT: '#a78bfa',
  DEVICE: '#fb923c',
  APPLICATION: '#2dd4bf',
};

export const CommunicationGraphView: React.FC<CommunicationGraphViewProps> = ({
  caseId,
  caseData,
}) => {
  const [graphData, setGraphData] = useState<GraphQueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters State
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<EdgeType[]>([
    'CALL',
    'SMS',
    'MESSAGE',
    'EMAIL',
  ]);
  const [centerNodeQuery, setCenterNodeQuery] = useState('');
  const [depth, setDepth] = useState(2);
  const [minWeight, setMinWeight] = useState(1);
  const [colorMode, setColorMode] = useState<'community' | 'type'>('community');

  // Selected Entity State for Inspector Drawers
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);

  // Snapshots State
  const [isSnapshotModalOpen, setIsSnapshotModalOpen] = useState(false);
  const [snapshotTitle, setSnapshotTitle] = useState('');
  const [snapshotsList, setSnapshotsList] = useState<GraphSnapshotRecord[]>([]);

  // Canvas / SVG Layout Simulation State
  const [nodePositions, setNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const [zoomLevel, setZoomLevel] = useState(1);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const svgRef = useRef<SVGSVGElement | null>(null);

  const fetchGraph = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const payload = {
        time_range_start: startDate ? new Date(startDate).toISOString() : null,
        time_range_end: endDate ? new Date(endDate).toISOString() : null,
        communication_types: selectedTypes.length > 0 ? selectedTypes : null,
        center_node: centerNodeQuery.trim() || null,
        depth,
        min_weight: minWeight,
        include_metrics: true,
        include_communities: true,
      };

      const res: GraphQueryResponse = await apiClient.queryCommunicationGraph(caseId, payload);
      setGraphData(res);

      // Compute initial 2D circular/force layout
      const positions: Record<string, { x: number; y: number }> = {};
      const total = res.nodes.length;
      const radius = Math.min(320, Math.max(160, total * 22));
      const centerX = 450;
      const centerY = 320;

      res.nodes.forEach((n, i) => {
        // Group by community angle or circular layout
        const angle = (i / Math.max(total, 1)) * 2 * Math.PI;
        positions[n.node_id] = {
          x: centerX + radius * Math.cos(angle) + (Math.random() * 20 - 10),
          y: centerY + radius * Math.sin(angle) + (Math.random() * 20 - 10),
        };
      });
      setNodePositions(positions);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to retrieve communication graph');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [caseId]);

  const loadSnapshots = async () => {
    try {
      const list = await apiClient.listGraphSnapshots(caseId);
      setSnapshotsList(list);
    } catch {
      // ignore
    }
  };

  const handleSaveSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!snapshotTitle.trim()) return;
    try {
      await apiClient.createGraphSnapshot(caseId, {
        title: snapshotTitle.trim(),
        query_params: {
          time_range_start: startDate || null,
          time_range_end: endDate || null,
          communication_types: selectedTypes,
          center_node: centerNodeQuery || null,
          depth,
          min_weight: minWeight,
        },
      });
      setSnapshotTitle('');
      setIsSnapshotModalOpen(false);
      loadSnapshots();
    } catch (err: any) {
      alert(`Snapshot save failed: ${err.message}`);
    }
  };

  const handleTypeToggle = (type: EdgeType) => {
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  // Pan interaction handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as HTMLElement).tagName === 'svg') {
      setIsDragging(true);
      setDragStart({ x: e.clientX - panOffset.x, y: e.clientY - panOffset.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPanOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const getNodeColor = (node: GraphNode) => {
    if (colorMode === 'community' && node.community_id !== undefined && node.community_id !== null) {
      return COMMUNITY_COLORS[node.community_id % COMMUNITY_COLORS.length];
    }
    return NODE_TYPE_COLORS[node.node_type] || '#94a3b8';
  };

  return (
    <div style={styles.container}>
      {/* Top Banner Header */}
      <div style={styles.header}>
        <div style={styles.headerTitleGroup}>
          <div style={styles.headerIcon}>🕸️</div>
          <div>
            <h1 style={styles.headerTitle}>Communication Graph & Social Network Analytics</h1>
            <div style={styles.headerSubtitle}>
              Phase 13 Network Topology • Case: {caseData?.case_number || caseId}
            </div>
          </div>
        </div>

        <div style={styles.headerMetricsBar}>
          {graphData && (
            <div style={styles.metricsGroup}>
              <div style={styles.metricBadge}>
                <span style={styles.mVal}>{graphData.nodes.length}</span>
                <span style={styles.mKey}>NODES</span>
              </div>
              <div style={styles.metricBadge}>
                <span style={styles.mVal}>{graphData.edges.length}</span>
                <span style={styles.mKey}>EDGES</span>
              </div>
              <div style={styles.metricBadge}>
                <span style={styles.mVal}>{graphData.metrics_summary?.density ?? 0}</span>
                <span style={styles.mKey}>DENSITY</span>
              </div>
              <div style={styles.metricBadge}>
                <span style={styles.mVal}>{graphData.communities_summary?.total_communities ?? 0}</span>
                <span style={styles.mKey}>CLUSTERS</span>
              </div>
              <div style={styles.metricBadge}>
                <span style={styles.mVal}>{graphData.latency_ms} ms</span>
                <span style={styles.mKey}>LATENCY</span>
              </div>
            </div>
          )}

          <button
            onClick={() => {
              loadSnapshots();
              setIsSnapshotModalOpen(true);
            }}
            style={styles.snapshotBtn}
          >
            📸 SNAPSHOTS ({snapshotsList.length})
          </button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div style={styles.workspace}>
        {/* Left Filter Controls Sidebar */}
        <aside style={styles.controlsSidebar}>
          <div style={styles.controlsHeader}>
            <span style={styles.controlsTitle}>NETWORK FILTERS</span>
            <button onClick={() => fetchGraph()} style={styles.applyBtn} disabled={isLoading}>
              {isLoading ? 'BUILDING...' : 'APPLY FILTERS ↻'}
            </button>
          </div>

          <div style={styles.filterSection}>
            <label style={styles.inputLabel}>FOCUS ENTITY (EGO-NETWORK):</label>
            <input
              type="text"
              value={centerNodeQuery}
              onChange={(e) => setCenterNodeQuery(e.target.value)}
              placeholder="Search Phone, Person, or Email..."
              style={styles.textInput}
            />
          </div>

          <div style={styles.filterSection}>
            <div style={styles.labelWithVal}>
              <label style={styles.inputLabel}>EXPANSION DEPTH (HOPS):</label>
              <span style={styles.valChip}>{depth}</span>
            </div>
            <input
              type="range"
              min={1}
              max={4}
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              style={styles.rangeInput}
            />
          </div>

          <div style={styles.filterSection}>
            <div style={styles.labelWithVal}>
              <label style={styles.inputLabel}>MIN INTERACTION WEIGHT:</label>
              <span style={styles.valChip}>{minWeight}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={minWeight}
              onChange={(e) => setMinWeight(Number(e.target.value))}
              style={styles.rangeInput}
            />
          </div>

          <div style={styles.filterSection}>
            <label style={styles.inputLabel}>COMMUNICATION CATEGORIES:</label>
            <div style={styles.checkboxGroup}>
              {(['CALL', 'SMS', 'MESSAGE', 'EMAIL'] as EdgeType[]).map((type) => (
                <label key={type} style={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={selectedTypes.includes(type)}
                    onChange={() => handleTypeToggle(type)}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div style={styles.filterSection}>
            <label style={styles.inputLabel}>DATE RANGE (UTC):</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={styles.dateInput}
            />
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={{ ...styles.dateInput, marginTop: '6px' }}
            />
          </div>

          <div style={styles.filterSection}>
            <label style={styles.inputLabel}>NODE COLOR SCHEME:</label>
            <div style={styles.radioGroup}>
              <label style={styles.radioLabel}>
                <input
                  type="radio"
                  name="colorMode"
                  checked={colorMode === 'community'}
                  onChange={() => setColorMode('community')}
                />
                <span>Louvain Communities</span>
              </label>
              <label style={styles.radioLabel}>
                <input
                  type="radio"
                  name="colorMode"
                  checked={colorMode === 'type'}
                  onChange={() => setColorMode('type')}
                />
                <span>Entity Type</span>
              </label>
            </div>
          </div>

          {/* Legal Safety Notice */}
          <div style={styles.safetyBox}>
            <div style={styles.safetyHeading}>FORENSIC NEUTRALITY NOTICE</div>
            <p style={styles.safetyText}>
              Graph centrality and community clusters represent structural network metrics only.
              Centrality does NOT imply criminal involvement, leadership, or intent.
            </p>
          </div>
        </aside>

        {/* Center Network Visualization Canvas */}
        <div style={styles.canvasContainer}>
          {errorMessage && (
            <div style={styles.errorBanner}>
              <span>⚠ {errorMessage}</span>
            </div>
          )}

          {/* Canvas Navigation Toolbar */}
          <div style={styles.canvasToolbar}>
            <button onClick={() => setZoomLevel((z) => Math.min(z + 0.2, 3))} style={styles.toolBtn}>
              + ZOOM IN
            </button>
            <button onClick={() => setZoomLevel((z) => Math.max(z - 0.2, 0.4))} style={styles.toolBtn}>
              - ZOOM OUT
            </button>
            <button
              onClick={() => {
                setZoomLevel(1);
                setPanOffset({ x: 0, y: 0 });
              }}
              style={styles.toolBtn}
            >
              ↺ RESET VIEW
            </button>
          </div>

          {/* SVG Graph View */}
          <svg
            ref={svgRef}
            style={styles.svgCanvas}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
          >
            <g transform={`translate(${panOffset.x}, ${panOffset.y}) scale(${zoomLevel})`}>
              {/* Render Edges */}
              {graphData?.edges.map((edge) => {
                const sPos = nodePositions[edge.source_node_id];
                const tPos = nodePositions[edge.target_node_id];
                if (!sPos || !tPos) return null;

                const isSelected = selectedEdge?.edge_id === edge.edge_id;
                const strokeWidth = Math.min(Math.max(1.5, edge.weight * 0.8), 8);

                return (
                  <g key={edge.edge_id} onClick={() => { setSelectedEdge(edge); setSelectedNode(null); }}>
                    <line
                      x1={sPos.x}
                      y1={sPos.y}
                      x2={tPos.x}
                      y2={tPos.y}
                      stroke={isSelected ? '#38bdf8' : '#334155'}
                      strokeWidth={isSelected ? strokeWidth + 2 : strokeWidth}
                      strokeOpacity={0.7}
                      style={{ cursor: 'pointer' }}
                    />
                  </g>
                );
              })}

              {/* Render Nodes */}
              {graphData?.nodes.map((node) => {
                const pos = nodePositions[node.node_id];
                if (!pos) return null;

                const isSelected = selectedNode?.node_id === node.node_id;
                const radius = Math.min(Math.max(14, 12 + node.degree * 2), 30);
                const color = getNodeColor(node);

                return (
                  <g
                    key={node.node_id}
                    transform={`translate(${pos.x}, ${pos.y})`}
                    onClick={() => { setSelectedNode(node); setSelectedEdge(null); }}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      r={radius}
                      fill={color}
                      fillOpacity={0.85}
                      stroke={isSelected ? '#ffffff' : '#0f172a'}
                      strokeWidth={isSelected ? 3 : 1.5}
                    />
                    <text
                      dy={radius + 14}
                      textAnchor="middle"
                      fill="#f8fafc"
                      fontSize="11px"
                      fontFamily="monospace"
                      fontWeight={600}
                    >
                      {node.display_label.length > 18
                        ? node.display_label.substring(0, 16) + '…'
                        : node.display_label}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </div>

        {/* Right Inspector Drawer (Node or Edge Details) */}
        <aside style={styles.inspectorSidebar}>
          {selectedNode ? (
            <div style={styles.inspectorContent}>
              <div style={styles.inspHeader}>
                <span style={styles.inspTypeBadge}>{selectedNode.node_type}</span>
                <button onClick={() => setSelectedNode(null)} style={styles.inspCloseBtn}>✕</button>
              </div>
              <h2 style={styles.inspTitle}>{selectedNode.display_label}</h2>
              <div style={styles.inspId}>{selectedNode.node_id}</div>

              <div style={styles.metricsTable}>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Direct Degree:</span>
                  <span style={styles.mValHighlight}>{selectedNode.degree}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>In / Out Degree:</span>
                  <span style={styles.mVal}>{selectedNode.in_degree} in / {selectedNode.out_degree} out</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Weighted Interactions:</span>
                  <span style={styles.mValHighlight}>{selectedNode.weighted_degree}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Betweenness Centrality:</span>
                  <span style={styles.mVal}>{selectedNode.betweenness}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Closeness Centrality:</span>
                  <span style={styles.mVal}>{selectedNode.closeness}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>PageRank:</span>
                  <span style={styles.mVal}>{selectedNode.pagerank}</span>
                </div>
                {selectedNode.community_id !== undefined && (
                  <div style={styles.metricRow}>
                    <span style={styles.mLabel}>Community Cluster:</span>
                    <span style={styles.mVal}>Cluster #{selectedNode.community_id}</span>
                  </div>
                )}
              </div>

              {selectedNode.source_references && selectedNode.source_references.length > 0 && (
                <div style={styles.sourceRefBox}>
                  <div style={styles.refBoxTitle}>LINKED CANONICAL EVIDENCE ({selectedNode.source_references.length})</div>
                  <div style={styles.refList}>
                    {selectedNode.source_references.map((ref, idx) => (
                      <div key={idx} style={styles.refItem}>
                        <span>[{ref.artifact_type}]</span>
                        <span style={styles.refMono}>{ref.canonical_id.substring(0, 8)}...</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : selectedEdge ? (
            <div style={styles.inspectorContent}>
              <div style={styles.inspHeader}>
                <span style={styles.inspTypeBadge}>{selectedEdge.edge_type}</span>
                <button onClick={() => setSelectedEdge(null)} style={styles.inspCloseBtn}>✕</button>
              </div>
              <h2 style={styles.inspTitle}>Communication Channel</h2>

              <div style={styles.edgeEndpoints}>
                <div style={styles.endpointBox}>
                  <span style={styles.endpointLabel}>FROM:</span>
                  <span style={styles.endpointVal}>{selectedEdge.source_node_id}</span>
                </div>
                <div style={styles.endpointArrow}>↓</div>
                <div style={styles.endpointBox}>
                  <span style={styles.endpointLabel}>TO:</span>
                  <span style={styles.endpointVal}>{selectedEdge.target_node_id}</span>
                </div>
              </div>

              <div style={styles.metricsTable}>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Interaction Count:</span>
                  <span style={styles.mValHighlight}>{selectedEdge.weight} event(s)</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Applications:</span>
                  <span style={styles.mVal}>{selectedEdge.applications.join(', ') || 'N/A'}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>First Observed:</span>
                  <span style={styles.mVal}>{selectedEdge.first_timestamp || 'N/A'}</span>
                </div>
                <div style={styles.metricRow}>
                  <span style={styles.mLabel}>Last Observed:</span>
                  <span style={styles.mVal}>{selectedEdge.last_timestamp || 'N/A'}</span>
                </div>
              </div>

              {selectedEdge.source_canonical_ids && (
                <div style={styles.sourceRefBox}>
                  <div style={styles.refBoxTitle}>PROVENANCE RECORDS ({selectedEdge.source_canonical_ids.length})</div>
                  <div style={styles.refList}>
                    {selectedEdge.source_canonical_ids.map((id, idx) => (
                      <div key={idx} style={styles.refItem}>
                        <span>Canonical ID:</span>
                        <span style={styles.refMono}>{id}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={styles.emptyInspector}>
              <div style={styles.emptyInspIcon}>👆</div>
              <div style={styles.emptyInspTitle}>Select Node or Edge</div>
              <div style={styles.emptyInspText}>
                Click any entity node or interaction link to inspect centrality metrics, community affiliation, and original evidence provenance.
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* Snapshot Management Modal */}
      {isSnapshotModalOpen && (
        <div style={styles.modalOverlay} onClick={() => setIsSnapshotModalOpen(false)}>
          <div style={styles.modalCard} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <span style={styles.modalTitle}>📸 Forensic Graph Snapshots</span>
              <button onClick={() => setIsSnapshotModalOpen(false)} style={styles.inspCloseBtn}>✕</button>
            </div>

            <form onSubmit={handleSaveSnapshot} style={styles.snapshotForm}>
              <label style={styles.inputLabel}>SAVE CURRENT GRAPH STATE:</label>
              <div style={styles.saveRow}>
                <input
                  type="text"
                  value={snapshotTitle}
                  onChange={(e) => setSnapshotTitle(e.target.value)}
                  placeholder="Snapshot title (e.g. Sept 15 Call Network Analysis)..."
                  style={styles.textInput}
                />
                <button type="submit" style={styles.saveBtn} disabled={!snapshotTitle.trim()}>
                  SAVE
                </button>
              </div>
            </form>

            <div style={styles.snapshotListSection}>
              <div style={styles.snapshotListTitle}>PREVIOUS SNAPSHOTS FOR THIS CASE:</div>
              {snapshotsList.length === 0 ? (
                <div style={styles.noSnapshots}>No snapshots created yet.</div>
              ) : (
                <div style={styles.snapshotsList}>
                  {snapshotsList.map((snap) => (
                    <div key={snap.snapshot_id} style={styles.snapshotItem}>
                      <div>
                        <div style={styles.snapTitleText}>{snap.title}</div>
                        <div style={styles.snapMetaText}>
                          {snap.node_count} nodes • {snap.edge_count} edges • {new Date(snap.created_at).toLocaleString()}
                        </div>
                      </div>
                      <span style={styles.snapIdBadge}>{snap.snapshot_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: 'var(--bg-primary, #0a0f1d)',
    color: 'var(--text-primary, #f8fafc)',
    fontFamily: 'var(--font-sans, system-ui, sans-serif)',
  },
  header: {
    padding: '14px 20px',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    borderBottom: '1px solid var(--border-subtle, #1e293b)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '12px',
  },
  headerTitleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  headerIcon: {
    fontSize: '26px',
  },
  headerTitle: {
    fontSize: '17px',
    fontWeight: 700,
    margin: 0,
    color: '#f8fafc',
  },
  headerSubtitle: {
    fontSize: '12px',
    color: '#94a3b8',
    marginTop: '2px',
  },
  headerMetricsBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
  },
  metricsGroup: {
    display: 'flex',
    gap: '6px',
  },
  metricBadge: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    padding: '4px 8px',
    borderRadius: '4px',
    minWidth: '55px',
  },
  mVal: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#38bdf8',
    fontFamily: 'monospace',
  },
  mKey: {
    fontSize: '9px',
    color: '#94a3b8',
    letterSpacing: '0.5px',
  },
  snapshotBtn: {
    backgroundColor: '#083344',
    border: '1px solid #0891b2',
    color: '#38bdf8',
    fontSize: '11px',
    fontWeight: 700,
    padding: '6px 12px',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  workspace: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  controlsSidebar: {
    width: '280px',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    borderRight: '1px solid var(--border-subtle, #1e293b)',
    padding: '16px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '14px',
    flexShrink: 0,
  },
  controlsHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #1e293b',
    paddingBottom: '8px',
  },
  controlsTitle: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#94a3b8',
    letterSpacing: '0.5px',
  },
  applyBtn: {
    backgroundColor: '#0891b2',
    color: '#ffffff',
    border: 'none',
    borderRadius: '4px',
    padding: '4px 8px',
    fontSize: '11px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  filterSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  inputLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748b',
    letterSpacing: '0.5px',
  },
  labelWithVal: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  valChip: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#38bdf8',
    backgroundColor: '#1e293b',
    padding: '2px 6px',
    borderRadius: '3px',
    fontFamily: 'monospace',
  },
  textInput: {
    backgroundColor: '#090d16',
    border: '1px solid #334155',
    color: '#f8fafc',
    fontSize: '12px',
    padding: '8px 10px',
    borderRadius: '4px',
    outline: 'none',
  },
  dateInput: {
    backgroundColor: '#090d16',
    border: '1px solid #334155',
    color: '#f8fafc',
    fontSize: '11px',
    padding: '6px 8px',
    borderRadius: '4px',
    outline: 'none',
  },
  rangeInput: {
    width: '100%',
    accentColor: '#0891b2',
    cursor: 'pointer',
  },
  checkboxGroup: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '6px',
  },
  checkLabel: {
    fontSize: '11px',
    color: '#cbd5e1',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    cursor: 'pointer',
  },
  radioGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  radioLabel: {
    fontSize: '11px',
    color: '#cbd5e1',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    cursor: 'pointer',
  },
  safetyBox: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '10px',
    marginTop: 'auto',
  },
  safetyHeading: {
    fontSize: '9px',
    fontWeight: 700,
    color: '#38bdf8',
    letterSpacing: '0.5px',
    marginBottom: '4px',
  },
  safetyText: {
    fontSize: '10px',
    color: '#94a3b8',
    lineHeight: 1.4,
    margin: 0,
  },
  canvasContainer: {
    flex: 1,
    position: 'relative',
    backgroundColor: '#060913',
    overflow: 'hidden',
  },
  canvasToolbar: {
    position: 'absolute',
    top: '12px',
    left: '12px',
    display: 'flex',
    gap: '6px',
    zIndex: 10,
  },
  toolBtn: {
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    border: '1px solid #334155',
    color: '#e2e8f0',
    fontSize: '10px',
    fontWeight: 700,
    padding: '5px 10px',
    borderRadius: '4px',
    cursor: 'pointer',
    backdropFilter: 'blur(4px)',
  },
  svgCanvas: {
    width: '100%',
    height: '100%',
    cursor: 'grab',
  },
  errorBanner: {
    position: 'absolute',
    top: '12px',
    right: '12px',
    backgroundColor: '#450a0a',
    border: '1px solid #dc2626',
    color: '#fca5a5',
    fontSize: '12px',
    padding: '8px 12px',
    borderRadius: '4px',
    zIndex: 10,
  },
  inspectorSidebar: {
    width: '320px',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    borderLeft: '1px solid var(--border-subtle, #1e293b)',
    overflowY: 'auto',
    padding: '16px',
    flexShrink: 0,
  },
  inspectorContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  inspHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  inspTypeBadge: {
    fontSize: '10px',
    fontWeight: 700,
    backgroundColor: '#083344',
    border: '1px solid #0891b2',
    color: '#38bdf8',
    padding: '2px 6px',
    borderRadius: '3px',
  },
  inspCloseBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: '14px',
  },
  inspTitle: {
    fontSize: '15px',
    fontWeight: 700,
    margin: 0,
    color: '#f8fafc',
  },
  inspId: {
    fontSize: '11px',
    color: '#64748b',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
  },
  metricsTable: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '10px',
  },
  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '11px',
    borderBottom: '1px solid #131d33',
    paddingBottom: '4px',
  },
  mLabel: {
    color: '#94a3b8',
  },
  mValHighlight: {
    color: '#38bdf8',
    fontWeight: 700,
    fontFamily: 'monospace',
  },
  edgeEndpoints: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    backgroundColor: '#090d16',
    padding: '10px',
    borderRadius: '4px',
    border: '1px solid #1e293b',
  },
  endpointBox: {
    display: 'flex',
    flexDirection: 'column',
  },
  endpointLabel: {
    fontSize: '9px',
    fontWeight: 700,
    color: '#64748b',
  },
  endpointVal: {
    fontSize: '11px',
    color: '#f8fafc',
    fontFamily: 'monospace',
    wordBreak: 'break-all',
  },
  endpointArrow: {
    textAlign: 'center',
    color: '#38bdf8',
    fontSize: '12px',
  },
  sourceRefBox: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '10px',
  },
  refBoxTitle: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748b',
    letterSpacing: '0.5px',
    marginBottom: '6px',
  },
  refList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  refItem: {
    fontSize: '10px',
    display: 'flex',
    justifyContent: 'space-between',
    color: '#cbd5e1',
  },
  refMono: {
    fontFamily: 'monospace',
    color: '#38bdf8',
  },
  emptyInspector: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    height: '100%',
    color: '#64748b',
    padding: '20px',
  },
  emptyInspIcon: {
    fontSize: '32px',
    marginBottom: '10px',
  },
  emptyInspTitle: {
    fontSize: '14px',
    fontWeight: 700,
    color: '#94a3b8',
    marginBottom: '6px',
  },
  emptyInspText: {
    fontSize: '12px',
    lineHeight: 1.5,
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalCard: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    width: '90%',
    maxWidth: '550px',
    maxHeight: '80vh',
    display: 'flex',
    flexDirection: 'column',
    padding: '20px',
    gap: '16px',
  },
  modalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: '16px',
    fontWeight: 700,
    color: '#f8fafc',
  },
  snapshotForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    padding: '12px',
    borderRadius: '6px',
  },
  saveRow: {
    display: 'flex',
    gap: '8px',
  },
  saveBtn: {
    backgroundColor: '#0891b2',
    color: '#ffffff',
    border: 'none',
    borderRadius: '4px',
    padding: '0 14px',
    fontSize: '12px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  snapshotListSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    overflowY: 'auto',
  },
  snapshotListTitle: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#64748b',
    letterSpacing: '0.5px',
  },
  noSnapshots: {
    fontSize: '12px',
    color: '#64748b',
    padding: '10px 0',
  },
  snapshotsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  snapshotItem: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '10px 12px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  snapTitleText: {
    fontSize: '13px',
    fontWeight: 600,
    color: '#f8fafc',
  },
  snapMetaText: {
    fontSize: '10px',
    color: '#94a3b8',
    marginTop: '2px',
  },
  snapIdBadge: {
    fontSize: '10px',
    fontFamily: 'monospace',
    color: '#38bdf8',
    backgroundColor: '#083344',
    padding: '2px 6px',
    borderRadius: '3px',
  },
};
