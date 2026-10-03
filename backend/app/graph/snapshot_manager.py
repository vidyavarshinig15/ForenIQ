from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from backend.app.schemas.graph import (
    GraphEdge,
    GraphNode,
    GraphQueryRequest,
    GraphSnapshotRecord,
)

logger = logging.getLogger(__name__)


class GraphSnapshotManager:
    """
    Manages reproducible, case-scoped graph snapshot records.
    """

    def __init__(self):
        # Key: (case_id, snapshot_id) -> snapshot dict
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def _get_key(self, case_id: str, snapshot_id: str) -> str:
        return f"{str(case_id).strip()}::{str(snapshot_id).strip()}"

    def create_snapshot(
        self,
        case_id: UUID,
        title: str,
        query_params: GraphQueryRequest,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        metrics_summary: Optional[Dict[str, Any]] = None,
        reproducibility: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> GraphSnapshotRecord:
        case_id_str = str(case_id).strip()
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        record = GraphSnapshotRecord(
            snapshot_id=snapshot_id,
            case_id=case_id_str,
            title=title,
            created_at=now_iso,
            created_by_user_id=user_id,
            node_count=len(nodes),
            edge_count=len(edges),
            query_params=query_params.model_dump() if hasattr(query_params, "model_dump") else query_params,
            reproducibility=reproducibility or {},
        )

        key = self._get_key(case_id_str, snapshot_id)
        self._snapshots[key] = {
            "record": record,
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "metrics": metrics_summary or {},
        }

        return record

    def get_snapshot(self, case_id: UUID, snapshot_id: str) -> Optional[Dict[str, Any]]:
        case_id_str = str(case_id).strip()
        key = self._get_key(case_id_str, snapshot_id)
        return self._snapshots.get(key)

    def list_snapshots_for_case(self, case_id: UUID) -> List[GraphSnapshotRecord]:
        case_id_str = str(case_id).strip()
        prefix = f"{case_id_str}::"
        results: List[GraphSnapshotRecord] = []
        for k, v in self._snapshots.items():
            if k.startswith(prefix):
                results.append(v["record"])
        return sorted(results, key=lambda x: x.created_at, reverse=True)


# Global singleton
graph_snapshot_manager = GraphSnapshotManager()
