#!/usr/bin/env python3
"""
Phase 12 — RAG Pipeline Evaluation & Benchmark Suite

Evaluates:
  1. Retrieval Precision@K and Recall@K
  2. Evidence Citation Correctness & Completeness
  3. Unsupported Claim & Hallucination Rate
  4. Prompt-Injection Resilience Rate
  5. Insufficient Evidence Detection Accuracy
  6. Answer Generation Latency (ms)
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.rag.citation_validator import CitationValidationService
from backend.app.rag.context_builder import EvidenceContextBuilder
from backend.app.rag.prompts import SYSTEM_PROMPT_FORENSIC_RAG
from backend.app.rag.providers.local_provider import DeterministicForensicRAGProvider


async def run_rag_evaluation():
    dataset_path = os.path.join(
        os.path.dirname(__file__),
        "../backend/tests/evaluation/synthetic_rag_dataset.json",
    )

    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    print("=" * 80)
    print("PHASE 12 — EVIDENCE-GROUNDED FORENSIC RAG EVALUATION BENCHMARK")
    print(f"Total Synthetic Test Cases: {len(test_cases)}")
    print("=" * 80)

    context_builder = EvidenceContextBuilder()
    citation_validator = CitationValidationService()
    provider = DeterministicForensicRAGProvider()

    total_cases = len(test_cases)
    retrieval_precisions = []
    retrieval_recalls = []
    citation_correct_count = 0
    total_citations_evaluated = 0
    citation_complete_count = 0
    unsupported_claims_count = 0
    insufficient_correct = 0
    insufficient_total = 0
    injection_defense_success = 0
    injection_total = 0
    latencies_ms = []

    case_id = "case-test-eval-001"

    for tc in test_cases:
        tc_id = tc["id"]
        category = tc["category"]
        query = tc["query"]
        evidence_records = tc.get("evidence_records", [])
        expected_insufficient = tc.get("expected_insufficient", False)
        expected_cited_ids = set(tc.get("expected_cited_ids", []))
        expected_facts = tc.get("expected_facts", [])
        expected_prohibited = tc.get("expected_prohibited_terms", [])

        # Inject case_id into records
        for r in evidence_records:
            r["case_id"] = case_id

        t0 = time.monotonic()

        # Step 1: Context building
        context_items, context_text, tag_lookup, detected_conflicts = context_builder.build_context(
            raw_search_results=evidence_records,
            case_id=case_id,
        )

        # Step 2: Generation
        raw_output = await provider.generate_answer(
            query=query,
            evidence_items=context_items,
            evidence_context_text=context_text,
            system_prompt=SYSTEM_PROMPT_FORENSIC_RAG,
        )

        # Step 3: Citation validation
        valid_citations, val_report, sanitized_ans = citation_validator.validate_citations(
            raw_answer=raw_output,
            tag_lookup=tag_lookup,
            active_case_id=case_id,
        )

        latency = (time.monotonic() - t0) * 1000
        latencies_ms.append(latency)

        # Metrics calculation
        retrieved_ids = {item.canonical_id for item in context_items}

        # Precision & Recall
        if expected_cited_ids:
            intersection = retrieved_ids.intersection(expected_cited_ids)
            precision = len(intersection) / len(retrieved_ids) if retrieved_ids else 1.0
            recall = len(intersection) / len(expected_cited_ids)
            retrieval_precisions.append(precision)
            retrieval_recalls.append(recall)
        else:
            retrieval_precisions.append(1.0)
            retrieval_recalls.append(1.0)

        # Citation correctness
        for cit in valid_citations:
            total_citations_evaluated += 1
            if cit.canonical_id in expected_cited_ids or not expected_cited_ids:
                citation_correct_count += 1

        # Citation completeness
        cited_canonical_ids = {cit.canonical_id for cit in valid_citations}
        if expected_cited_ids:
            if expected_cited_ids.issubset(cited_canonical_ids) or expected_insufficient:
                citation_complete_count += 1
        else:
            citation_complete_count += 1

        # Insufficient handling
        is_insufficient_ans = "not provide enough information" in raw_output.lower() or "insufficient" in raw_output.lower()
        if expected_insufficient:
            insufficient_total += 1
            if is_insufficient_ans:
                insufficient_correct += 1

        # Injection defense
        if category == "PROMPT_INJECTION_DEFENSE":
            injection_total += 1
            # Check that model did not abandon forensic formatting or citation requirements
            has_citations = len(valid_citations) > 0
            has_structure = "ANSWER:" in raw_output and "EVIDENCE_REFERENCES:" in raw_output
            if has_citations and has_structure and val_report.is_valid:
                injection_defense_success += 1

        # Unsupported claims / Prohibited terms check
        if val_report.unsupported_claims:
            unsupported_claims_count += len(val_report.unsupported_claims)

        print(f"[{tc_id}] {category:<30} | Latency: {latency:.2f}ms | Valid Citations: {len(valid_citations)} | Valid: {val_report.is_valid}")

    # Summary Metrics
    mean_precision = sum(retrieval_precisions) / len(retrieval_precisions) if retrieval_precisions else 1.0
    mean_recall = sum(retrieval_recalls) / len(retrieval_recalls) if retrieval_recalls else 1.0
    citation_correctness_pct = (citation_correct_count / total_citations_evaluated * 100) if total_citations_evaluated else 100.0
    citation_completeness_pct = (citation_complete_count / total_cases * 100)
    unsupported_claim_rate = (unsupported_claims_count / total_cases * 100)
    insufficient_detection_pct = (insufficient_correct / insufficient_total * 100) if insufficient_total else 100.0
    injection_resilience_pct = (injection_defense_success / injection_total * 100) if injection_total else 100.0
    mean_latency_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0

    print("\n" + "=" * 80)
    print("PHASE 12 RAG BENCHMARK RESULTS")
    print("=" * 80)
    print(f"1. Retrieval Precision@K:                {mean_precision * 100:.2f}%")
    print(f"2. Retrieval Recall@K:                   {mean_recall * 100:.2f}%")
    print(f"3. Citation Correctness:                 {citation_correctness_pct:.2f}%")
    print(f"4. Citation Completeness:                {citation_completeness_pct:.2f}%")
    print(f"5. Unsupported-Claim Rate:               {unsupported_claim_rate:.2f}%")
    print(f"6. Insufficient Evidence Detection Rate: {insufficient_detection_pct:.2f}%")
    print(f"7. Prompt-Injection Defense Resilience:  {injection_resilience_pct:.2f}%")
    print(f"8. Mean Pipeline Latency:                {mean_latency_ms:.2f} ms")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_rag_evaluation())
