from datetime import datetime
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

import networkx as nx

from backend.app.core.config import settings
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType, EdgeType, NodeType
from backend.app.schemas.graph import GraphEdge, GraphNode, GraphQueryRequest

logger = logging.getLogger(__name__)


class ForensicGraphBuilder:
    """
    Constructs normalized, case-isolated forensic communication graphs from canonical records.
    Builds both NetworkX graph structures for algorithmic analysis and Pydantic models for UI rendering.
    """

    def __init__(self):
        self.max_nodes_limit = settings.GRAPH_MAX_NODES
        self.max_edges_limit = settings.GRAPH_MAX_EDGES

    @staticmethod
    def _normalize_identifier(raw: str) -> Tuple[NodeType, str, str]:
        """
        Determines entity node type and normalizes its identifier.
        Returns: (NodeType, normalized_id, display_label)
        """
        val = raw.strip()
        
        # Check Email
        if "@" in val and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", val):
            clean_email = val.lower()
            return NodeType.EMAIL, f"email:{clean_email}", clean_email

        # Check Phone Number (contains digits and optional +, -, spaces)
        digit_count = sum(c.isdigit() for c in val)
        if digit_count >= 7 and re.match(r"^[\+0-9\s\-\(\)\.]+$", val):
            clean_phone = re.sub(r"[^\+0-9]", "", val)
            if not clean_phone.startswith("+") and len(clean_phone) == 10:
                clean_phone = f"+91{clean_phone}"  # Standard default country fallback if unformatted
            return NodeType.PHONE_NUMBER, f"phone:{clean_phone}", clean_phone

        # Check Person Name with phone inside parentheses e.g. "+919876543210 (Rahul)"
        m = re.search(r"(\+?\d[\d\s\-]{6,})\s*\((.*?)\)", val)
        if m:
            clean_phone = re.sub(r"[^\+0-9]", "", m.group(1))
            name = m.group(2).strip()
            return NodeType.PERSON, f"person:{name.lower()}:{clean_phone}", f"{name} ({clean_phone})"

        # Check Person Name
        if len(val) > 2 and not any(c.isdigit() for c in val):
            return NodeType.PERSON, f"person:{val.lower()}", val

        # Fallback Account / Identifier
        return NodeType.ACCOUNT, f"account:{val.lower()}", val

    @staticmethod
    def _map_artifact_to_edge_type(artifact_type: ArtifactType, app_name: Optional[str]) -> EdgeType:
        """Classifies interaction into standardized EdgeType."""
        if artifact_type == ArtifactType.CALL:
            return EdgeType.CALL
        
        app_lower = (app_name or "").lower()
        if "sms" in app_lower:
            return EdgeType.SMS
        if "mms" in app_lower:
            return EdgeType.MMS
        if "email" in app_lower or "mail" in app_lower:
            return EdgeType.EMAIL
        
        if artifact_type == ArtifactType.MESSAGE:
            return EdgeType.MESSAGE

        return EdgeType.OTHER_COMMUNICATION

    def build_graph(
        self,
        records: List[CanonicalEvidence],
        case_id: UUID,
        request: GraphQueryRequest,
    ) -> Tuple[nx.DiGraph, List[GraphNode], List[GraphEdge]]:
        """
        Processes canonical evidence records into a filtered NetworkX DiGraph and schema objects.
        """
        case_id_str = str(case_id).strip()
        G = nx.DiGraph()

        # Temporary node and edge aggregation dictionaries
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        # Edge key: (source_id, target_id, edge_type)
        edges_dict: Dict[Tuple[str, str, EdgeType], Dict[str, Any]] = {}

        for rec in records:
            # Case isolation verification
            if str(rec.case_id).strip() != case_id_str:
                logger.warning(
                    f"SECURITY ALERT: Filtered cross-case evidence in GraphBuilder. "
                    f"Target Case: {case_id_str}, Found Record Case: {rec.case_id}"
                )
                continue

            # Temporal filter check
            ts = rec.event_timestamp
            if ts:
                if request.time_range_start and ts < request.time_range_start:
                    continue
                if request.time_range_end and ts > request.time_range_end:
                    continue

            # Communication type / Artifact filter check
            app_name = rec.application or "Unknown"
            if request.applications:
                if not any(app.lower() in app_name.lower() for app in request.applications):
                    continue

            edge_type = self._map_artifact_to_edge_type(rec.artifact_type, app_name)
            if request.communication_types and edge_type not in request.communication_types:
                continue

            # Extract sender / receiver from record metadata_ or entities or payload
            meta = rec.metadata_ or {} if hasattr(rec, "metadata_") and rec.metadata_ else {}
            payload = getattr(rec, "parsed_payload", None) or {}
            
            sender_raw = (
                meta.get("sender")
                or meta.get("from")
                or meta.get("caller")
                or meta.get("from_party")
                or payload.get("sender")
                or payload.get("from")
                or payload.get("caller")
            )
            receiver_raw = (
                meta.get("receiver")
                or meta.get("to")
                or meta.get("callee")
                or meta.get("to_party")
                or meta.get("recipient")
                or payload.get("receiver")
                or payload.get("to")
                or payload.get("callee")
            )

            # Check entities if sender/receiver not directly in metadata
            if (not sender_raw or not receiver_raw) and hasattr(rec, "entities") and rec.entities:
                for ent in rec.entities:
                    role = ent.get("role", "").lower()
                    val = ent.get("value") or ent.get("text")
                    if role in ("sender", "from", "caller") and not sender_raw:
                        sender_raw = val
                    elif role in ("receiver", "to", "callee", "recipient") and not receiver_raw:
                        receiver_raw = val

            # Skip records without two identifiable communication endpoints
            if not sender_raw or not receiver_raw:
                continue

            # Normalize sender & receiver
            s_type, s_id, s_label = self._normalize_identifier(str(sender_raw))
            r_type, r_id, r_label = self._normalize_identifier(str(receiver_raw))

            # Skip self-loops if sender == receiver
            if s_id == r_id:
                continue

            iso_ts = ts.isoformat() if ts else None
            canon_id_str = str(rec.id)
            evid_id_str = str(rec.evidence_id)

            # --- Update Sender Node ---
            if s_id not in nodes_dict:
                nodes_dict[s_id] = {
                    "node_id": s_id,
                    "case_id": case_id_str,
                    "node_type": s_type,
                    "display_label": s_label,
                    "normalized_value": s_label,
                    "source_references": [],
                    "first_observed": iso_ts,
                    "last_observed": iso_ts,
                    "metadata": {"application": app_name},
                }
            s_node = nodes_dict[s_id]
            if iso_ts:
                if not s_node["first_observed"] or iso_ts < s_node["first_observed"]:
                    s_node["first_observed"] = iso_ts
                if not s_node["last_observed"] or iso_ts > s_node["last_observed"]:
                    s_node["last_observed"] = iso_ts
            if canon_id_str not in [ref.get("canonical_id") for ref in s_node["source_references"]]:
                s_node["source_references"].append({
                    "canonical_id": canon_id_str,
                    "evidence_id": evid_id_str,
                    "artifact_type": rec.artifact_type.value,
                })

            # --- Update Receiver Node ---
            if r_id not in nodes_dict:
                nodes_dict[r_id] = {
                    "node_id": r_id,
                    "case_id": case_id_str,
                    "node_type": r_type,
                    "display_label": r_label,
                    "normalized_value": r_label,
                    "source_references": [],
                    "first_observed": iso_ts,
                    "last_observed": iso_ts,
                    "metadata": {"application": app_name},
                }
            r_node = nodes_dict[r_id]
            if iso_ts:
                if not r_node["first_observed"] or iso_ts < r_node["first_observed"]:
                    r_node["first_observed"] = iso_ts
                if not r_node["last_observed"] or iso_ts > r_node["last_observed"]:
                    r_node["last_observed"] = iso_ts
            if canon_id_str not in [ref.get("canonical_id") for ref in r_node["source_references"]]:
                r_node["source_references"].append({
                    "canonical_id": canon_id_str,
                    "evidence_id": evid_id_str,
                    "artifact_type": rec.artifact_type.value,
                })

            # --- Update Edge ---
            edge_key = (s_id, r_id, edge_type)
            if edge_key not in edges_dict:
                edge_id = f"edge:{hashlib.sha256(f'{s_id}->{r_id}:{edge_type.value}'.encode()).hexdigest()[:16]}"
                edges_dict[edge_key] = {
                    "edge_id": edge_id,
                    "case_id": case_id_str,
                    "source_node_id": s_id,
                    "target_node_id": r_id,
                    "edge_type": edge_type,
                    "weight": 0,
                    "first_timestamp": iso_ts,
                    "last_timestamp": iso_ts,
                    "timestamps": [],
                    "source_canonical_ids": [],
                    "source_evidence_ids": [],
                    "applications": [],
                    "metadata": {},
                }

            e_entry = edges_dict[edge_key]
            e_entry["weight"] += 1
            if iso_ts:
                e_entry["timestamps"].append(iso_ts)
                if not e_entry["first_timestamp"] or iso_ts < e_entry["first_timestamp"]:
                    e_entry["first_timestamp"] = iso_ts
                if not e_entry["last_timestamp"] or iso_ts > e_entry["last_timestamp"]:
                    e_entry["last_timestamp"] = iso_ts
            if canon_id_str not in e_entry["source_canonical_ids"]:
                e_entry["source_canonical_ids"].append(canon_id_str)
            if evid_id_str not in e_entry["source_evidence_ids"]:
                e_entry["source_evidence_ids"].append(evid_id_str)
            if app_name and app_name not in e_entry["applications"]:
                e_entry["applications"].append(app_name)

        # Build NetworkX MultiDiGraph
        for n_id, n_data in nodes_dict.items():
            G.add_node(n_id, **n_data)

        for (u, v, etype), e_data in edges_dict.items():
            # Filter by min_weight if configured
            if e_data["weight"] >= (request.min_weight or 1):
                G.add_edge(u, v, key=etype.value, **e_data)

        # Ego-Network Extraction (if center_node specified)
        if request.center_node:
            center_clean = request.center_node.strip()
            # Find matching node id
            matched_node_id = None
            for n_id, n_data in nodes_dict.items():
                if (
                    center_clean.lower() in n_id.lower()
                    or center_clean.lower() in n_data["display_label"].lower()
                    or center_clean.lower() in n_data["normalized_value"].lower()
                ):
                    matched_node_id = n_id
                    break

            if matched_node_id and matched_node_id in G:
                radius = min(request.depth or 2, settings.GRAPH_MAX_DEPTH_LIMIT)
                undirected_G = G.to_undirected(as_view=True)
                reachable_nodes = set(nx.single_source_shortest_path_length(undirected_G, matched_node_id, cutoff=radius).keys())
                G = G.subgraph(reachable_nodes).copy()
            else:
                # Center node not found -> return empty graph
                G = nx.DiGraph()

        # Enforce max_nodes safety limit
        max_allowed_nodes = min(request.max_nodes or self.max_nodes_limit, self.max_nodes_limit)
        if G.number_of_nodes() > max_allowed_nodes:
            # Keep top nodes by degree
            sorted_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:max_allowed_nodes]
            top_node_ids = {n for n, deg in sorted_nodes}
            G = G.subgraph(top_node_ids).copy()

        # Convert back to schema objects
        schema_nodes: List[GraphNode] = []
        for n_id in G.nodes():
            n_attr = G.nodes[n_id]
            schema_nodes.append(
                GraphNode(
                    node_id=n_id,
                    case_id=case_id_str,
                    node_type=n_attr.get("node_type", NodeType.ACCOUNT),
                    display_label=n_attr.get("display_label", n_id),
                    normalized_value=n_attr.get("normalized_value", n_id),
                    source_references=n_attr.get("source_references", []),
                    first_observed=n_attr.get("first_observed"),
                    last_observed=n_attr.get("last_observed"),
                    metadata=n_attr.get("metadata", {}),
                )
            )

        schema_edges: List[GraphEdge] = []
        for u, v, e_attr in G.edges(data=True):
            schema_edges.append(
                GraphEdge(
                    edge_id=e_attr.get("edge_id", f"edge:{u}->{v}"),
                    case_id=case_id_str,
                    source_node_id=u,
                    target_node_id=v,
                    edge_type=e_attr.get("edge_type", EdgeType.CALL),
                    weight=e_attr.get("weight", 1),
                    first_timestamp=e_attr.get("first_timestamp"),
                    last_timestamp=e_attr.get("last_timestamp"),
                    timestamps=e_attr.get("timestamps", []),
                    source_canonical_ids=e_attr.get("source_canonical_ids", []),
                    source_evidence_ids=e_attr.get("source_evidence_ids", []),
                    applications=e_attr.get("applications", []),
                    metadata=e_attr.get("metadata", {}),
                )
            )

        return G, schema_nodes, schema_edges
