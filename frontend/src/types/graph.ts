export type NodeType = 'PERSON' | 'PHONE_NUMBER' | 'EMAIL' | 'ACCOUNT' | 'DEVICE' | 'APPLICATION';

export type EdgeType = 'CALL' | 'SMS' | 'MMS' | 'MESSAGE' | 'EMAIL' | 'OTHER_COMMUNICATION';

export type CommunityAlgorithm = 'LOUVAIN' | 'GREEDY_MODULARITY';

export interface GraphNode {
  node_id: string;
  case_id: string;
  node_type: NodeType;
  display_label: string;
  normalized_value: string;
  source_references: Array<Record<string, any>>;
  first_observed?: string | null;
  last_observed?: string | null;
  degree: number;
  in_degree: number;
  out_degree: number;
  weighted_degree: number;
  betweenness: number;
  closeness: number;
  pagerank: number;
  community_id?: number | null;
  metadata: Record<string, any>;
}

export interface GraphEdge {
  edge_id: string;
  case_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType;
  weight: number;
  first_timestamp?: string | null;
  last_timestamp?: string | null;
  timestamps: string[];
  source_canonical_ids: string[];
  source_evidence_ids: string[];
  applications: string[];
  metadata: Record<string, any>;
}

export interface GraphMetricsSummary {
  total_nodes: number;
  total_edges: number;
  density: number;
  average_degree: number;
  is_connected: boolean;
  connected_components_count: number;
  metric_explanations: Record<string, string>;
}

export interface CommunitySummary {
  algorithm: CommunityAlgorithm;
  total_communities: number;
  modularity_score?: number | null;
  community_sizes: Record<number, number>;
  description: string;
}

export interface GraphQueryRequest {
  time_range_start?: string | null;
  time_range_end?: string | null;
  communication_types?: EdgeType[] | null;
  applications?: string[] | null;
  center_node?: string | null;
  depth?: number;
  min_weight?: number;
  max_nodes?: number | null;
  include_metrics?: boolean;
  include_communities?: boolean;
}

export interface GraphQueryResponse {
  snapshot_id: string;
  case_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  metrics_summary?: GraphMetricsSummary | null;
  communities_summary?: CommunitySummary | null;
  reproducibility: Record<string, any>;
  latency_ms: number;
}

export interface GraphSnapshotRecord {
  snapshot_id: string;
  case_id: string;
  title: string;
  created_at: string;
  created_by_user_id?: string | null;
  node_count: number;
  edge_count: number;
  query_params: Record<string, any>;
  reproducibility: Record<string, any>;
}
