#!/usr/bin/env python3
"""
Phase 15 — Intelligent Forensic Report Generation, Citation & Export Benchmark.
Measures report document compilation, citation verification, PDF generation, JSON serialization,
and SHA-256 integrity hashing across small, medium, and large report payloads.
"""

from datetime import datetime, timezone
import json
import os
import sys
import time
from uuid import uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.models.enums import FindingType, ReportStatus, ReportType
from backend.app.reports.export_service import export_service
from backend.app.reports.pdf_generator import pdf_generator
from backend.app.schemas.report import (
    EvidenceCitation,
    ForensicFinding,
    ForensicReportDocument,
    ReportCaseInfo,
    ReportEvidenceItem,
    ReportGraphSummary,
    ReportTimelineEntry,
)


def create_synthetic_report_doc(case_id, findings_count=10, timeline_count=20):
    ev_id = uuid4()
    citations = [
        EvidenceCitation(
            citation_id=f"CIT-{i+1:03d}",
            evidence_id=ev_id,
            evidence_number="EVD-SYN-01",
            artifact_id=uuid4(),
            record_identifier=f"REC-{i+1:03d}",
            source_file="extraction.xml",
            timestamp=datetime.now(timezone.utc).isoformat(),
            summary=f"Forensic interaction artifact #{i+1}",
        )
        for i in range(min(findings_count * 2, 50))
    ]

    findings = [
        ForensicFinding(
            finding_id=f"FIND-{i+1:03d}",
            title=f"Forensic Investigative Finding #{i+1}",
            description=f"Evidence artifact indicates structured interaction pattern with external actor {i+1} referencing verifiable forensic citations.",
            finding_type=FindingType.TIMELINE_EVENT if i % 2 == 0 else FindingType.COMMUNICATION_PATTERN,
            source_type="Forensic Multi-Layer Subsystems",
            citations=citations[i % len(citations) : (i % len(citations)) + 2],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        for i in range(findings_count)
    ]

    timeline_entries = [
        ReportTimelineEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="CALL" if i % 2 == 0 else "MESSAGE",
            application="Phone" if i % 2 == 0 else "WhatsApp",
            actor=f"+919876543{i%10:03d}",
            target=f"+919876543{(i+1)%10:03d}",
            content_summary=f"Event summary narrative #{i+1}",
            citation_ref=f"CIT-{(i % len(citations)) + 1:03d}",
        )
        for i in range(timeline_count)
    ]

    return ForensicReportDocument(
        report_id=f"REP-SYN-{uuid4().hex[:6].upper()}",
        case_id=case_id,
        title="Automated Comprehensive Forensic Investigation Report",
        report_type=ReportType.COMPREHENSIVE_FORENSIC_ANALYSIS_REPORT,
        status=ReportStatus.APPROVED,
        version=1,
        generated_by_id=uuid4(),
        generated_by_name="Senior Forensic Examiner",
        generated_at=datetime.now(timezone.utc).isoformat(),
        case_info=ReportCaseInfo(
            case_id=case_id,
            case_number="CASE-SYN-9901",
            title="Synthetic Large-Scale Forensic Extraction Analysis",
            description="Complete analysis of multi-device digital evidence extractions.",
            lead_investigator="Lead Examiner",
            created_at=datetime.now(timezone.utc).isoformat(),
            status="ACTIVE",
        ),
        investigation_scope={"time_range": "2026-09-01 to 2026-09-30", "devices": ["Device_01", "Device_02"]},
        methodology=["NIST SP 800-86 Forensic Acquisition", "NetworkX SNA", "Isolation Forest Anomaly Modeling"],
        evidence_inventory=[
            ReportEvidenceItem(
                evidence_id=ev_id,
                evidence_number="EVD-SYN-01",
                original_filename="mobile_extraction.ufdr",
                sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                integrity_status="VALID",
                artifact_count=findings_count * 10,
                ingestion_timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
        findings=findings,
        timeline_section=timeline_entries,
        graph_section=ReportGraphSummary(
            total_nodes=25,
            total_edges=48,
            density=0.16,
            detected_communities_count=3,
        ),
        citations=citations,
        limitations=["Analysis based strictly on verified forensic extraction records."],
        analyst_notes="Court-ready certified forensic analysis report.",
        audit_metadata={"template_version": "1.0.0", "generator": "UFDR-ReportEngine"},
        reproducibility={"software_version": "1.0.0", "sha256_verified": True},
    )


def evaluate_report_pipeline():
    print("=" * 80)
    print("PHASE 15 — FORENSIC REPORT GENERATION, CITATION & EXPORT BENCHMARK")
    print("=" * 80)

    case_id = uuid4()

    # 1. Standard Report Generation Benchmark
    t0 = time.perf_counter()
    doc = create_synthetic_report_doc(case_id, findings_count=10, timeline_count=25)
    doc_prep_time_ms = (time.perf_counter() - t0) * 1000.0

    # 2. JSON Export & SHA-256 Hashing
    t1 = time.perf_counter()
    json_str, json_hash = export_service.export_as_json(doc)
    json_export_time_ms = (time.perf_counter() - t1) * 1000.0

    # 3. PDF Generation & SHA-256 Hashing
    t2 = time.perf_counter()
    pdf_bytes, pdf_hash = export_service.export_as_pdf(doc)
    pdf_export_time_ms = (time.perf_counter() - t2) * 1000.0

    # 4. CSV Export
    t3 = time.perf_counter()
    csv_str = export_service.export_timeline_as_csv(doc)
    csv_export_time_ms = (time.perf_counter() - t3) * 1000.0

    print("\nBENCHMARK METRICS (STANDARD COMPREHENSIVE REPORT):")
    print("-" * 80)
    print(f"  • Report Document ID:        {doc.report_id}")
    print(f"  • Findings Count:            {len(doc.findings)}")
    print(f"  • Citations Count:           {len(doc.citations)}")
    print(f"  • Timeline Entries Count:    {len(doc.timeline_section)}")
    print(f"  • Document Assembly Latency: {doc_prep_time_ms:.2f} ms")
    print(f"  • JSON Export Latency:       {json_export_time_ms:.2f} ms (Size: {len(json_str)/1024:.2f} KB)")
    print(f"  • PDF Generation Latency:    {pdf_export_time_ms:.2f} ms (Size: {len(pdf_bytes)/1024:.2f} KB)")
    print(f"  • CSV Export Latency:        {csv_export_time_ms:.2f} ms")
    print(f"  • JSON SHA-256 Integrity:    {json_hash[:24]}...")
    print(f"  • PDF SHA-256 Integrity:     {pdf_hash[:24]}...")
    print("-" * 80)

    # 5. Scalability Testing across Report Sizes
    print("\n" + "=" * 80)
    print("SCALABILITY & THROUGHPUT BENCHMARK (REPORT SIZE PROFILING)")
    print("=" * 80)

    sizes = [
        ("Small Report (5 Findings, 10 Events)", 5, 10),
        ("Medium Report (25 Findings, 50 Events)", 25, 50),
        ("Large Report (100 Findings, 200 Events)", 100, 200),
        ("Very Large Report (200 Findings, 500 Events)", 200, 500),
    ]

    for label, num_f, num_tl in sizes:
        t_start = time.perf_counter()
        test_doc = create_synthetic_report_doc(case_id, findings_count=num_f, timeline_count=num_tl)
        j_str, j_hash = export_service.export_as_json(test_doc)
        p_bytes, p_hash = export_service.export_as_pdf(test_doc)
        total_time_ms = (time.perf_counter() - t_start) * 1000.0

        print(f"{label:<45} | PDF Size: {len(p_bytes)/1024:6.1f} KB | Total Latency: {total_time_ms:7.2f} ms")

    print("=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    evaluate_report_pipeline()
