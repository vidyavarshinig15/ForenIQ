#!/usr/bin/env python3
"""
Phase 10 — Forensic Retrieval Evaluation & Benchmarking Script

Evaluates EXACT, LEXICAL, SEMANTIC, and HYBRID retrieval modes against
the synthetic ground-truth dataset.
Calculates:
  - Precision@5, Precision@10
  - Recall@5, Recall@10
  - Mean Reciprocal Rank (MRR)
  - Query Latency (ms)
  - Embedding Generation Throughput (records/sec)
  - Vector Index Build Time & Memory
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from uuid import UUID

try:
    import torch
    torch.set_num_threads(1)
except ImportError:
    pass

import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import get_settings
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.enums import ArtifactType
from backend.app.services.embedding_formatter import EmbeddingFormatter
from backend.app.services.embedding_service import get_embedding_service
from backend.app.services.retrieval_ranker import RetrievalRanker
from backend.app.vector_store import get_vector_store

logging.basicConfig(level=logging.WARNING)


def calculate_precision_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_in_top_k = sum(1 for rid in top_k if rid in relevant_ids)
    return relevant_in_top_k / float(k)


def calculate_recall_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_in_top_k = sum(1 for rid in top_k if rid in relevant_ids)
    return relevant_in_top_k / float(len(relevant_ids))


def calculate_reciprocal_rank(retrieved_ids: List[str], relevant_ids: Set[str]) -> float:
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / float(rank)
    return 0.0


def run_evaluation():
    settings = get_settings()
    dataset_path = PROJECT_ROOT / "backend/tests/evaluation/synthetic_retrieval_dataset.json"

    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("records", [])
    queries = data.get("evaluation_queries", [])

    print("\n" + "=" * 75)
    print("PHASE 10: FORENSIC RETRIEVAL EVALUATION & BENCHMARK")
    print("=" * 75)
    print(f"Configured Embedding Model: {settings.EMBEDDING_MODEL_NAME} (v{settings.EMBEDDING_MODEL_VERSION})")
    print(f"Embedding Dimension:        {settings.EMBEDDING_DIMENSION}")
    print(f"Evaluation Dataset Records: {len(records)}")
    print(f"Ground-Truth Query Count:   {len(queries)}")
    print("=" * 75)

    eval_case_id = UUID("00000000-0000-0000-0000-00000000cafe")
    vector_store = get_vector_store()
    embedding_service = get_embedding_service()
    ranker = RetrievalRanker()

    # 1. Format and Embed Synthetic Records
    t0 = time.monotonic()
    texts: List[str] = []
    ids: List[UUID] = []
    record_map: Dict[str, Dict[str, Any]] = {}

    try:
        for r in records:
            rid = UUID(r["id"])
            record_map[r["id"]] = r
            # Build simple canonical evidence mock object
            can_rec = CanonicalEvidence(
                id=rid,
                case_id=eval_case_id,
                evidence_id=UUID("00000000-0000-0000-0000-00000000e001"),
                raw_artifact_id=UUID("00000000-0000-0000-0000-00000000a001"),
                artifact_type=ArtifactType(r["artifact_type"]),
                canonical_fingerprint="fp_" + r["id"][:8],
                source_file=r["source_file"],
                source_path="/evidence/" + r["source_file"],
                record_identifier=r["record_identifier"],
                content=r["content"],
                application=r["application"],
                device_id="dev_pixel_9",
                entities=r.get("entities", []),
                metadata_={"sender": r.get("sender"), "receiver": r.get("receiver")},
            )
            formatted_text, content_hash = EmbeddingFormatter.format_canonical_record(can_rec)
            if formatted_text:
                texts.append(formatted_text)
                ids.append(rid)

        t_format = time.monotonic() - t0
        print(f"[1/4] Formatted {len(texts)} records in {t_format:.3f}s", flush=True)

        # 2. Benchmark Embedding Generation
        t1 = time.monotonic()
        vectors = embedding_service.embed_texts(texts)
        t_embed = time.monotonic() - t1
        embed_rate = len(texts) / max(0.001, t_embed)

        print(f"[2/4] Generated {len(vectors)} embeddings in {t_embed:.3f}s ({embed_rate:.1f} rec/s)", flush=True)

        # 3. Benchmark Index Build & Persistence
        t2 = time.monotonic()
        vector_store.rebuild(case_id=eval_case_id, ids=ids, vectors=vectors)
        t_index = time.monotonic() - t2
        print(f"[3/4] Vector index rebuilt in {t_index:.3f}s", flush=True)

    except Exception as e:
        import traceback
        print("ERROR IN EVALUATION SETUP:")
        traceback.print_exc()
        return

    # 4. Evaluate Modes across Queries
    modes = ["LEXICAL", "SEMANTIC", "HYBRID"]
    results_by_mode: Dict[str, Dict[str, float]] = {}

    for mode in modes:
        p5_list = []
        p10_list = []
        r5_list = []
        r10_list = []
        mrr_list = []
        latencies = []

        for q_entry in queries:
            q_text = q_entry["query"]
            rel_ids = set(q_entry["relevant_record_ids"])

            t_q0 = time.monotonic()

            if mode == "SEMANTIC":
                q_vec = embedding_service.embed_query(q_text)
                matches = vector_store.search(case_id=eval_case_id, query_vector=q_vec, top_k=10)
                retrieved_ids = [str(uid) for uid, score in matches]

            elif mode == "LEXICAL":
                # Simulated lexical keyword substring match
                terms = q_text.lower().split()
                matched = []
                for r in records:
                    score = sum(1 for term in terms if term in (r["content"] or "").lower() or term in (r.get("application") or "").lower())
                    if score > 0:
                        matched.append((r["id"], score))
                matched.sort(key=lambda x: x[1], reverse=True)
                retrieved_ids = [rid for rid, _ in matched[:10]]

            elif mode == "HYBRID":
                # Dense semantic search
                q_vec = embedding_service.embed_query(q_text)
                sem_matches = vector_store.search(case_id=eval_case_id, query_vector=q_vec, top_k=10)
                sem_scores = {str(uid): score for uid, score in sem_matches}

                # Lexical search
                terms = q_text.lower().split()
                lex_scores = {}
                for r in records:
                    sc = sum(1 for term in terms if term in (r["content"] or "").lower())
                    if sc > 0:
                        lex_scores[r["id"]] = float(sc)

                # Combine
                all_candidate_ids = set(sem_scores.keys()) | set(lex_scores.keys())
                max_lex = max(lex_scores.values()) if lex_scores else 1.0
                scored = []
                for cid in all_candidate_ids:
                    norm_lex = (lex_scores.get(cid, 0.0) / max_lex) if max_lex > 0 else 0.0
                    norm_sem = sem_scores.get(cid, 0.0)
                    comb = 0.5 * norm_lex + 0.5 * norm_sem
                    scored.append((cid, comb))
                scored.sort(key=lambda x: x[1], reverse=True)
                retrieved_ids = [cid for cid, _ in scored[:10]]

            latency_ms = (time.monotonic() - t_q0) * 1000
            latencies.append(latency_ms)

            p5_list.append(calculate_precision_at_k(retrieved_ids, rel_ids, 5))
            p10_list.append(calculate_precision_at_k(retrieved_ids, rel_ids, 10))
            r5_list.append(calculate_recall_at_k(retrieved_ids, rel_ids, 5))
            r10_list.append(calculate_recall_at_k(retrieved_ids, rel_ids, 10))
            mrr_list.append(calculate_reciprocal_rank(retrieved_ids, rel_ids))

        results_by_mode[mode] = {
            "Precision@5": float(np.mean(p5_list)),
            "Recall@5": float(np.mean(r5_list)),
            "Precision@10": float(np.mean(p10_list)),
            "Recall@10": float(np.mean(r10_list)),
            "MRR": float(np.mean(mrr_list)),
            "Avg_Latency_ms": float(np.mean(latencies)),
        }

    # 5. Print Evaluation Summary Table
    print("\n" + "=" * 75, flush=True)
    print(f"{'Retrieval Mode':<15} | {'P@5':<8} | {'R@5':<8} | {'P@10':<8} | {'R@10':<8} | {'MRR':<8} | {'Latency':<10}", flush=True)
    print("-" * 75, flush=True)
    for mode, m in results_by_mode.items():
        print(
            f"{mode:<15} | {m['Precision@5']:<8.3f} | {m['Recall@5']:<8.3f} | "
            f"{m['Precision@10']:<8.3f} | {m['Recall@10']:<8.3f} | {m['MRR']:<8.3f} | {m['Avg_Latency_ms']:<7.2f} ms",
            flush=True,
        )
    print("=" * 75, flush=True)

    stats = vector_store.get_index_stats(eval_case_id)
    print(f"Vector Store Engine: {stats.get('engine', 'FAISS')}", flush=True)
    print(f"Vector Index Size:   {stats.get('total_vectors', len(ids))} vectors", flush=True)
    print("Evaluation completed successfully.\n", flush=True)


if __name__ == "__main__":
    run_evaluation()
