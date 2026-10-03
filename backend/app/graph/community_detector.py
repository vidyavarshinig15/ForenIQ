import logging
from typing import Dict, List, Optional, Tuple

import networkx as nx
from networkx.algorithms import community as nx_comm

from backend.app.core.config import settings
from backend.app.models.enums import CommunityAlgorithm
from backend.app.schemas.graph import CommunitySummary, GraphNode

logger = logging.getLogger(__name__)


class CommunityDetectionService:
    """
    Executes deterministic mathematical community detection over forensic communication graphs.
    Communities represent topological network clusters, NOT criminal conspiracies or syndicates.
    """

    def __init__(self):
        self.default_algorithm = CommunityAlgorithm(getattr(settings, "GRAPH_COMMUNITY_ALGORITHM", "LOUVAIN"))
        self.random_seed = getattr(settings, "GRAPH_COMMUNITY_RANDOM_SEED", 42)

    def detect_communities(
        self,
        G: nx.DiGraph,
        schema_nodes: List[GraphNode],
        algorithm: Optional[CommunityAlgorithm] = None,
    ) -> Tuple[List[GraphNode], CommunitySummary]:
        """
        Partitions the graph into mathematical clusters and assigns community IDs to nodes.
        """
        algo = algorithm or self.default_algorithm
        num_nodes = G.number_of_nodes()

        if num_nodes == 0:
            summary = CommunitySummary(
                algorithm=algo,
                total_communities=0,
                modularity_score=0.0,
                community_sizes={},
            )
            return schema_nodes, summary

        undirected_G = G.to_undirected(as_view=False)
        node_lookup = {node.node_id: node for node in schema_nodes}

        communities: List[set] = []
        try:
            if algo == CommunityAlgorithm.LOUVAIN:
                communities = list(
                    nx_comm.louvain_communities(
                        undirected_G,
                        weight="weight",
                        seed=self.random_seed,
                    )
                )
            elif algo == CommunityAlgorithm.GREEDY_MODULARITY:
                communities = list(
                    nx_comm.greedy_modularity_communities(
                        undirected_G,
                        weight="weight",
                    )
                )
            else:
                communities = list(
                    nx_comm.louvain_communities(
                        undirected_G,
                        weight="weight",
                        seed=self.random_seed,
                    )
                )
        except Exception as e:
            logger.warning(f"Community detection fallback due to algorithm error: {e}")
            # Fallback to connected components as natural communities
            communities = list(nx.connected_components(undirected_G))

        # Calculate modularity score
        modularity_val = None
        if len(communities) > 0 and undirected_G.number_of_edges() > 0:
            try:
                modularity_val = round(float(nx_comm.modularity(undirected_G, communities, weight="weight")), 4)
            except Exception as e:
                logger.debug(f"Modularity calculation exception: {e}")
                modularity_val = 0.0

        # Assign community IDs
        community_sizes: Dict[int, int] = {}
        for comm_idx, comm_set in enumerate(communities):
            community_sizes[comm_idx] = len(comm_set)
            for node_id in comm_set:
                if node_id in node_lookup:
                    node_lookup[node_id].community_id = comm_idx

        summary = CommunitySummary(
            algorithm=algo,
            total_communities=len(communities),
            modularity_score=modularity_val,
            community_sizes=community_sizes,
        )

        return list(node_lookup.values()), summary
