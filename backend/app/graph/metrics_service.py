import logging
from typing import Dict, List, Tuple

import networkx as nx

from backend.app.schemas.graph import GraphMetricsSummary, GraphNode

logger = logging.getLogger(__name__)


class GraphMetricsService:
    """
    Computes mathematical graph structure and centrality metrics using NetworkX.
    All scores represent structural graph properties, NOT criminality or legal culpability.
    """

    def compute_metrics(
        self,
        G: nx.DiGraph,
        schema_nodes: List[GraphNode],
    ) -> Tuple[List[GraphNode], GraphMetricsSummary]:
        """
        Computes node-level centrality and graph-level topology summary.
        """
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        if num_nodes == 0:
            summary = GraphMetricsSummary(
                total_nodes=0,
                total_edges=0,
                density=0.0,
                average_degree=0.0,
                is_connected=False,
                connected_components_count=0,
            )
            return schema_nodes, summary

        # 1. Degree Metrics
        in_degrees = dict(G.in_degree())
        out_degrees = dict(G.out_degree())
        degrees = dict(G.degree())

        # Weighted degrees (sum of weights on connected edges)
        weighted_degrees: Dict[str, float] = {}
        for n in G.nodes():
            w_sum = sum(
                e_data.get("weight", 1)
                for _, _, e_data in G.in_edges(n, data=True)
            ) + sum(
                e_data.get("weight", 1)
                for _, _, e_data in G.out_edges(n, data=True)
            )
            weighted_degrees[n] = float(w_sum)

        # 2. Centrality Measures
        try:
            betweenness = nx.betweenness_centrality(G, normalized=True)
        except Exception as e:
            logger.warning(f"Betweenness centrality calculation error: {e}")
            betweenness = {n: 0.0 for n in G.nodes()}

        try:
            closeness = nx.closeness_centrality(G)
        except Exception as e:
            logger.warning(f"Closeness centrality calculation error: {e}")
            closeness = {n: 0.0 for n in G.nodes()}

        try:
            pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
        except Exception as e:
            logger.warning(f"PageRank calculation fallback: {e}")
            pagerank = {n: 1.0 / max(num_nodes, 1) for n in G.nodes()}

        # 3. Graph Topology Summary
        density = float(nx.density(G))
        avg_degree = sum(degrees.values()) / max(num_nodes, 1)
        undirected_G = G.to_undirected(as_view=True)
        is_conn = nx.is_connected(undirected_G) if num_nodes > 0 else False
        num_components = nx.number_connected_components(undirected_G) if num_nodes > 0 else 0

        # Update schema node models
        node_lookup = {node.node_id: node for node in schema_nodes}
        for n_id in G.nodes():
            if n_id in node_lookup:
                target_node = node_lookup[n_id]
                target_node.degree = int(degrees.get(n_id, 0))
                target_node.in_degree = int(in_degrees.get(n_id, 0))
                target_node.out_degree = int(out_degrees.get(n_id, 0))
                target_node.weighted_degree = round(float(weighted_degrees.get(n_id, 0.0)), 2)
                target_node.betweenness = round(float(betweenness.get(n_id, 0.0)), 4)
                target_node.closeness = round(float(closeness.get(n_id, 0.0)), 4)
                target_node.pagerank = round(float(pagerank.get(n_id, 0.0)), 4)

        summary = GraphMetricsSummary(
            total_nodes=num_nodes,
            total_edges=num_edges,
            density=round(density, 4),
            average_degree=round(avg_degree, 2),
            is_connected=is_conn,
            connected_components_count=num_components,
        )

        return list(node_lookup.values()), summary
