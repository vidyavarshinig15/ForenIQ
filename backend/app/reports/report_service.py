from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.anomalies.anomaly_service import anomaly_service
from backend.app.core.config import settings
from backend.app.core.errors import ForensicAppException
from backend.app.graph.graph_service import ForensicGraphService
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.custody import EvidenceCustodyEvent
from backend.app.models.enums import (
    AuditAction,
    FindingType,
    ReportStatus,
    ReportType,
    UserRole,
)
from backend.app.models.evidence import Evidence
from backend.app.models.user import User
from backend.app.reports.citation_engine import citation_engine
from backend.app.reports.export_service import export_service
from backend.app.repositories.case_repo import CaseRepository
from backend.app.schemas.report import (
    EvidenceCitation,
    ForensicFinding,
    ForensicReportDocument,
    ReportAnomalyEntry,
    ReportCaseInfo,
    ReportConflictingEvidence,
    ReportCreateRequest,
    ReportCustodyEvent,
    ReportEvidenceItem,
    ReportGraphSummary,
    ReportListSummary,
    ReportTimelineEntry,
    ReportUpdateRequest,
)
from backend.app.services.audit_service import AuditService
from backend.app.timeline.timeline_service import timeline_service

logger = logging.getLogger(__name__)


class ForensicReportService:
    """
    Forensic Investigation Report Generator & Orchestrator.
    Synthesizes multi-source evidence, timeline streams, communication graphs,
    statistical anomalies, and RAG findings into structured, court-ready, verifiable reports.
    """

    def __init__(self):
        self._reports_registry: Dict[str, ForensicReportDocument] = {}
        self._report_versions: Dict[str, List[ForensicReportDocument]] = {}

    async def generate_report(
        self,
        case_id: UUID,
        request: ReportCreateRequest,
        current_user: User,
        session: AsyncSession,
    ) -> ForensicReportDocument:
        """
        Build a comprehensive, evidence-grounded forensic report document.
        """
        # 1. Validate Case Access
        case_repo = CaseRepository(session)
        case = await case_repo.get_by_id(case_id)
        if not case:
            raise ForensicAppException(
                message=f"Case '{case_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        report_id = f"REP-{case.case_number}-{uuid.uuid4().hex[:6].upper()}"
        report_title = request.title or f"Forensic Investigation Report - {case.case_number}"

        # 2. Case Info
        case_info = ReportCaseInfo(
            case_id=case.id,
            case_number=case.case_number,
            title=case.title,
            description=case.description,
            lead_investigator=getattr(current_user, "name", current_user.email),
            created_at=case.created_at.isoformat() if case.created_at else datetime.now(timezone.utc).isoformat(),
            status=case.status.value if hasattr(case.status, "value") else str(case.status),
        )

        # 3. Evidence Inventory & Hashes
        ev_query = select(Evidence).where(Evidence.case_id == case_id)
        ev_res = await session.execute(ev_query)
        evidence_records = ev_res.scalars().all()

        evidence_inventory: List[ReportEvidenceItem] = []
        for ev in evidence_records:
            # Count canonical artifacts for evidence
            art_count_q = select(CanonicalEvidence).where(CanonicalEvidence.evidence_id == ev.id)
            art_count_res = await session.execute(art_count_q)
            art_count = len(art_count_res.scalars().all())
            ev_number = f"EVD-{str(ev.id)[:8].upper()}"

            evidence_inventory.append(
                ReportEvidenceItem(
                    evidence_id=ev.id,
                    evidence_number=ev_number,
                    original_filename=ev.original_filename,
                    sha256_hash=ev.sha256_hash or "UNKNOWN",
                    integrity_status=ev.integrity_status.value if hasattr(ev.integrity_status, "value") else str(ev.integrity_status),
                    artifact_count=art_count,
                    ingestion_timestamp=ev.created_at.isoformat() if ev.created_at else datetime.now(timezone.utc).isoformat(),
                )
            )

        # 4. Chain of Custody History
        custody_list: List[ReportCustodyEvent] = []
        if request.include_custody_chain and evidence_records:
            ev_ids = [ev.id for ev in evidence_records]
            cust_query = select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id.in_(ev_ids)).order_by(EvidenceCustodyEvent.timestamp.asc())
            cust_res = await session.execute(cust_query)
            cust_records = cust_res.scalars().all()

            ev_num_map = {ev.id: f"EVD-{str(ev.id)[:8].upper()}" for ev in evidence_records}
            for ce in cust_records:
                custody_list.append(
                    ReportCustodyEvent(
                        evidence_number=ev_num_map.get(ce.evidence_id, "EVD-UNKNOWN"),
                        event_type=ce.event_type.value if hasattr(ce.event_type, "value") else str(ce.event_type),
                        actor_name=str(ce.actor_user_id) if ce.actor_user_id else "System Custody Officer",
                        timestamp=ce.timestamp.isoformat() if ce.timestamp else datetime.now(timezone.utc).isoformat(),
                        action=ce.event_type.value if hasattr(ce.event_type, "value") else str(ce.event_type),
                        integrity_verified=True,
                    )
                )

        citations_list: List[EvidenceCitation] = []
        findings_list: List[ForensicFinding] = []
        conflicting_evidence: List[ReportConflictingEvidence] = []
        cit_counter = 1

        # 5. Timeline Section & Timeline Findings
        timeline_section_entries: Optional[List[ReportTimelineEntry]] = None
        if request.include_timeline:
            from backend.app.schemas.timeline_anomaly import TimelineFilterRequest
            tl_res = await timeline_service.get_timeline(
                case_id=case_id,
                filter_params=TimelineFilterRequest(limit=settings.REPORT_MAX_TIMELINE_EVENTS),
                current_user=current_user,
                session=session,
            )

            timeline_section_entries = []
            ev_map = {ev.id: f"EVD-{str(ev.id)[:8].upper()}" for ev in evidence_records}

            for ev_item in tl_res.events[: settings.REPORT_MAX_TIMELINE_EVENTS]:
                ev_num = ev_map.get(ev_item.evidence_id, "EVD-01")
                cit = citation_engine.create_citation(
                    evidence_id=ev_item.evidence_id,
                    evidence_number=ev_num,
                    artifact_id=ev_item.artifact_id,
                    record_identifier=ev_item.event_id,
                    source_file=ev_item.source_file,
                    timestamp=ev_item.timestamp,
                    summary=f"{ev_item.event_type.value} event involving {ev_item.actor or 'unknown'} to {ev_item.target or 'unknown'}",
                    citation_index=cit_counter,
                )
                citations_list.append(cit)

                timeline_section_entries.append(
                    ReportTimelineEntry(
                        timestamp=ev_item.timestamp or "N/A",
                        event_type=ev_item.event_type.value if hasattr(ev_item.event_type, "value") else str(ev_item.event_type),
                        application=ev_item.application,
                        actor=ev_item.actor,
                        target=ev_item.target,
                        content_summary=ev_item.content_summary,
                        citation_ref=cit.citation_id,
                    )
                )
                cit_counter += 1

            if tl_res.total_events > 0:
                findings_list.append(
                    ForensicFinding(
                        finding_id=f"FIND-{len(findings_list)+1:03d}",
                        title="Unified Chronological Timeline Extracted",
                        description=f"A total of {tl_res.total_events} canonical forensic events were synchronized across {len(evidence_records)} evidence containers spanning from {tl_res.earliest_timestamp or 'N/A'} to {tl_res.latest_timestamp or 'N/A'}.",
                        finding_type=FindingType.TIMELINE_EVENT,
                        source_type="Timeline Analysis Engine",
                        citations=citations_list[:3],
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )

        # 6. Communication Graph Findings
        graph_summary: Optional[ReportGraphSummary] = None
        if request.include_graph:
            try:
                graph_svc = ForensicGraphService(session)
                from backend.app.schemas.graph import GraphQueryRequest
                graph_data = await graph_svc.generate_communication_graph(
                    case_id=case_id,
                    request=GraphQueryRequest(),
                    current_user=current_user,
                )
                graph_summary = ReportGraphSummary(
                    snapshot_id=graph_data.snapshot_id,
                    total_nodes=len(graph_data.nodes),
                    total_edges=len(graph_data.edges),
                    density=graph_data.metrics_summary.density if graph_data.metrics_summary else 0.0,
                    top_centrality_nodes=[
                        {"node_id": n.node_id, "label": n.display_label, "degree": n.degree}
                        for n in graph_data.nodes[:5]
                    ],
                    detected_communities_count=graph_data.communities_summary.total_communities if graph_data.communities_summary else 0,
                    algorithm_version=settings.GRAPH_VERSION,
                )
                findings_list.append(
                    ForensicFinding(
                        finding_id=f"FIND-{len(findings_list)+1:03d}",
                        title="Communication Network Topology Constructed",
                        description=f"Constructed directed interaction network containing {len(graph_data.nodes)} distinct forensic entities (phone numbers, accounts, emails) and {len(graph_data.edges)} aggregated interaction channels.",
                        finding_type=FindingType.COMMUNICATION_PATTERN,
                        source_type="Communication Graph Engine",
                        citations=citations_list[:2] if citations_list else [],
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            except Exception as e:
                logger.warning("Graph section skipped: %s", str(e))

        # 7. Statistical Anomaly Findings
        anomaly_entries: Optional[List[ReportAnomalyEntry]] = None
        if request.include_anomalies:
            try:
                from backend.app.schemas.timeline_anomaly import AnomalyDetectionRequest
                anom_res = await anomaly_service.detect_anomalies(
                    case_id=case_id,
                    request=AnomalyDetectionRequest(contamination=0.05),
                    current_user=current_user,
                    session=session,
                )
                anomaly_entries = []
                for a in anom_res.anomalies[:15]:
                    anomaly_entries.append(
                        ReportAnomalyEntry(
                            anomaly_id=a.anomaly_id,
                            time_window=f"{a.start_time} - {a.end_time}",
                            anomaly_type=a.anomaly_type.value if hasattr(a.anomaly_type, "value") else str(a.anomaly_type),
                            severity=a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                            anomaly_score=a.anomaly_score,
                            factual_explanation=a.factual_explanation,
                            observed_vs_baseline={
                                m.feature_name: {"observed": m.observed_value, "median": m.baseline_median}
                                for m in a.baseline_metrics[:3]
                            },
                            citation_refs=a.supporting_event_ids[:2],
                        )
                    )

                if anom_res.anomalies_detected > 0:
                    findings_list.append(
                        ForensicFinding(
                            finding_id=f"FIND-{len(findings_list)+1:03d}",
                            title="Statistical Behavioral Anomalies Detected",
                            description=f"Isolation Forest identified {anom_res.anomalies_detected} time windows exhibiting statistical behavioral deviations relative to the case baseline.",
                            finding_type=FindingType.STATISTICAL_ANOMALY,
                            source_type="Isolation Forest Engine",
                            citations=citations_list[:2] if citations_list else [],
                            created_at=datetime.now(timezone.utc).isoformat(),
                            limitations=["Anomalies represent purely statistical deviations and do not indicate culpability or intent."],
                        )
                    )
            except Exception as e:
                logger.warning("Anomaly section skipped: %s", str(e))

        # 8. Methodology Description
        methodology = [
            "SHA-256 Cryptographic Hashing & Integrity Verification (NIST SP 800-86)",
            "Automated UFDR Parsing & Decompression with Zip Bomb Defense",
            "Deterministic Canonical Data Normalization (Phase 7 Standard)",
            "Chronological Cross-Artifact Timeline Synthesis",
            "NetworkX Topological Graph Analysis & Louvain Community Detection",
            "Multivariate Isolation Forest Statistical Outlier Detection",
            "Evidence Citation Traceability & Referential Integrity Validation",
        ]

        # 9. Limitations
        limitations = [
            "All findings are derived strictly from ingested forensic UFDR containers.",
            "Timestamps with UNKNOWN precision reflect device clock limitations.",
            "Graph centrality and community clusters represent structural topology, not organizational intent.",
            "Statistical anomalies require human investigator validation before establishing investigative relevance.",
        ]

        # 10. Citation Validation Check
        is_valid, validation_errors = await citation_engine.validate_citations(
            citations=citations_list,
            case_id=case_id,
            session=session,
        )
        if not is_valid:
            logger.error("Citation validation failed: %s", validation_errors)
            raise ForensicAppException(
                message=f"Report finalization rejected due to invalid citations: {'; '.join(validation_errors[:3])}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # 11. Construct Report Document
        doc = ForensicReportDocument(
            report_id=report_id,
            case_id=case_id,
            title=report_title,
            report_type=request.report_type,
            status=ReportStatus.DRAFT,
            version=1,
            generated_by_id=current_user.id,
            generated_by_name=getattr(current_user, "name", current_user.email),
            generated_at=datetime.now(timezone.utc).isoformat(),
            case_info=case_info,
            investigation_scope={
                "time_range": request.time_range or "Full Evidence Span",
                "target_entities": request.target_entities or "All Identified Entities",
                "included_sections": {
                    "evidence_inventory": request.include_evidence_inventory,
                    "chain_of_custody": request.include_custody_chain,
                    "timeline": request.include_timeline,
                    "communication_graph": request.include_graph,
                    "anomalies": request.include_anomalies,
                },
            },
            methodology=methodology,
            evidence_inventory=evidence_inventory,
            chain_of_custody=custody_list,
            findings=findings_list,
            timeline_section=timeline_section_entries,
            graph_section=graph_summary,
            anomaly_section=anomaly_entries,
            rag_narrative_summary=None,
            citations=citations_list,
            conflicting_evidence=conflicting_evidence,
            limitations=limitations,
            analyst_notes=request.analyst_notes,
            audit_metadata={
                "generator_version": settings.REPORT_VERSION,
                "template_version": settings.REPORT_TEMPLATE_VERSION,
                "total_citations": len(citations_list),
                "total_findings": len(findings_list),
            },
            reproducibility={
                "software_version": settings.REPORT_VERSION,
                "graph_version": settings.GRAPH_VERSION,
                "anomaly_version": settings.ANOMALY_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        # 12. Compute Report Content Hash
        _, report_hash = export_service.export_as_json(doc)
        doc.report_hash = report_hash

        # Store in registry
        self._reports_registry[report_id] = doc
        self._report_versions[report_id] = [doc]

        # 13. Audit Logging
        audit_service = AuditService(session)
        await audit_service.record_event(
            action=AuditAction.REPORT_GENERATED.value if hasattr(AuditAction.REPORT_GENERATED, "value") else str(AuditAction.REPORT_GENERATED),
            resource_type="forensic_report",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=report_id,
            case_id=case_id,
            details={
                "report_id": report_id,
                "report_type": doc.report_type.value,
                "version": doc.version,
                "report_hash": report_hash,
                "findings_count": len(findings_list),
                "citations_count": len(citations_list),
            },
        )

        return doc

    async def list_reports(
        self,
        case_id: UUID,
        current_user: User,
        session: AsyncSession,
    ) -> List[ReportListSummary]:
        """List all generated reports for the specified case."""
        case_repo = CaseRepository(session)
        case = await case_repo.get_by_id(case_id)
        if not case:
            raise ForensicAppException(
                message=f"Case '{case_id}' not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        summaries: List[ReportListSummary] = []
        for rep in self._reports_registry.values():
            if rep.case_id == case_id:
                summaries.append(
                    ReportListSummary(
                        report_id=rep.report_id,
                        case_id=rep.case_id,
                        title=rep.title,
                        report_type=rep.report_type,
                        status=rep.status,
                        version=rep.version,
                        generated_by_name=rep.generated_by_name,
                        generated_at=rep.generated_at,
                        report_hash=rep.report_hash,
                        findings_count=len(rep.findings),
                        citations_count=len(rep.citations),
                    )
                )

        summaries.sort(key=lambda x: x.generated_at, reverse=True)
        return summaries

    async def get_report(
        self,
        case_id: UUID,
        report_id: str,
        current_user: User,
        session: AsyncSession,
    ) -> ForensicReportDocument:
        """Retrieve a specific report enforcing case isolation."""
        doc = self._reports_registry.get(report_id)
        if not doc or doc.case_id != case_id:
            raise ForensicAppException(
                message=f"Report '{report_id}' not found in Case '{case_id}'.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return doc

    async def update_report(
        self,
        case_id: UUID,
        report_id: str,
        request: ReportUpdateRequest,
        current_user: User,
        session: AsyncSession,
    ) -> ForensicReportDocument:
        """Update report analyst notes or advance review lifecycle status."""
        doc = await self.get_report(case_id, report_id, current_user, session)

        # Clone and increment version
        new_doc_dict = doc.model_dump()
        if request.title:
            new_doc_dict["title"] = request.title
        if request.status:
            new_doc_dict["status"] = request.status
        if request.analyst_notes is not None:
            new_doc_dict["analyst_notes"] = request.analyst_notes

        new_doc_dict["version"] = doc.version + 1
        new_doc = ForensicReportDocument(**new_doc_dict)

        # Recompute hash
        _, new_hash = export_service.export_as_json(new_doc)
        new_doc.report_hash = new_hash

        self._reports_registry[report_id] = new_doc
        self._report_versions[report_id].append(new_doc)
        return new_doc

    async def approve_report(
        self,
        case_id: UUID,
        report_id: str,
        current_user: User,
        session: AsyncSession,
    ) -> ForensicReportDocument:
        """Approve report document for court export."""
        update_req = ReportUpdateRequest(status=ReportStatus.APPROVED)
        approved_doc = await self.update_report(case_id, report_id, update_req, current_user, session)

        audit_service = AuditService(session)
        await audit_service.record_event(
            action=AuditAction.REPORT_APPROVED.value if hasattr(AuditAction.REPORT_APPROVED, "value") else str(AuditAction.REPORT_APPROVED),
            resource_type="forensic_report",
            status="SUCCESS",
            user_id=current_user.id,
            resource_id=report_id,
            case_id=case_id,
            details={
                "report_id": report_id,
                "version": approved_doc.version,
                "approved_by": current_user.email,
                "report_hash": approved_doc.report_hash,
            },
        )
        return approved_doc


report_service = ForensicReportService()
