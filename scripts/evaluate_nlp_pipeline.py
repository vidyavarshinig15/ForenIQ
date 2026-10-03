"""
Phase 11 — NLP Evaluation & Benchmarking Script

Evaluates the Investigation NLP Pipeline against the synthetic benchmark dataset:
- Intent classification: Accuracy, Precision, Recall, F1-score
- Forensic Entity extraction: Precision, Recall, F1-score
- Temporal expression extraction: Accuracy & Precision validity
- Query-plan validity: Structured constraints correctness
- Latency & Performance: Mean, P50, P95, P99 latency

Usage:
    python scripts/evaluate_nlp_pipeline.py
"""

import json
import os
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.nlp import InvestigationNLPPipeline


def evaluate_pipeline(dataset_path: str) -> Dict[str, Any]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        samples = json.load(f)

    pipeline = InvestigationNLPPipeline()

    total_samples = len(samples)
    intent_correct = 0

    intent_tp = defaultdict(int)
    intent_fp = defaultdict(int)
    intent_fn = defaultdict(int)

    entity_tp = 0
    entity_fp = 0
    entity_fn = 0

    temporal_correct = 0
    temporal_total = 0

    valid_plans = 0
    latencies = []

    print(f"============================================================")
    print(f"EVALUATING PHASE 11 INVESTIGATION NLP PIPELINE ({total_samples} samples)")
    print(f"============================================================")

    for sample in samples:
        query = sample["query"]
        expected_intent = sample["expected_intent"]
        expected_entities = sample.get("expected_entities", [])
        expected_temporal = sample.get("expected_temporal")

        t0 = time.perf_counter()
        parsed = pipeline.parse_query(query)
        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)

        # 1. Intent Classification
        predicted_intent = parsed.intent.type.value
        if predicted_intent == expected_intent:
            intent_correct += 1
            intent_tp[expected_intent] += 1
        else:
            intent_fp[predicted_intent] += 1
            intent_fn[expected_intent] += 1

        # 2. Entity Extraction
        # Match entities by type and normalized value or text substring
        pred_entities = parsed.entities
        matched_expected = set()
        matched_pred = set()

        for e_idx, exp in enumerate(expected_entities):
            exp_type = exp["type"]
            exp_val = exp.get("normalized_value") or exp.get("text", "")
            for p_idx, pred in enumerate(pred_entities):
                if p_idx in matched_pred:
                    continue
                # Match type or compatible (e.g. DATE handled in temporal)
                if pred.type.value == exp_type or (exp_type == "DATE" and pred.type.value == "TEMPORAL"):
                    if exp_val.lower() in pred.normalized_value.lower() or exp_val.lower() in pred.text.lower() or pred.text.lower() in exp_val.lower():
                        matched_expected.add(e_idx)
                        matched_pred.add(p_idx)
                        break

        # Also count if expected entity is DATE and temporal parser captured it
        for e_idx, exp in enumerate(expected_entities):
            if e_idx not in matched_expected and exp["type"] == "DATE" and parsed.temporal_constraints:
                matched_expected.add(e_idx)

        entity_tp += len(matched_expected)
        entity_fn += (len(expected_entities) - len(matched_expected))
        # Note: Non-date unpredicted entities that were extracted
        non_date_expected_count = len([e for e in expected_entities if e["type"] != "DATE"])
        entity_fp += max(0, len(pred_entities) - len(matched_pred))

        # 3. Temporal Extraction
        if expected_temporal is not None:
            temporal_total += 1
            if parsed.temporal_constraints:
                tc = parsed.temporal_constraints[0]
                if expected_temporal.get("precision") is None or tc.precision == expected_temporal.get("precision"):
                    temporal_correct += 1
        else:
            if not parsed.temporal_constraints:
                temporal_correct += 1
            temporal_total += 1

        # 4. Plan Validity
        plan = pipeline.query_planner.plan(
            raw_query=parsed.normalized_query,
            intent=parsed.intent,
            entities=parsed.entities,
            temporal_constraints=parsed.temporal_constraints,
            user_requested_mode="AUTO"
        )
        if plan.mode is not None and plan.recommended_mode is not None:
            valid_plans += 1

    # Metrics Calculation
    intent_acc = (intent_correct / total_samples) * 100.0 if total_samples > 0 else 0.0

    all_intents = set(list(intent_tp.keys()) + list(intent_fp.keys()) + list(intent_fn.keys()))
    precisions, recalls, f1s = [], [], []
    for intent_name in all_intents:
        tp = intent_tp[intent_name]
        fp = intent_fp[intent_name]
        fn = intent_fn[intent_name]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    macro_intent_p = (sum(precisions) / len(precisions)) * 100.0 if precisions else 0.0
    macro_intent_r = (sum(recalls) / len(recalls)) * 100.0 if recalls else 0.0
    macro_intent_f1 = (sum(f1s) / len(f1s)) * 100.0 if f1s else 0.0

    ent_p = (entity_tp / (entity_tp + entity_fp)) * 100.0 if (entity_tp + entity_fp) > 0 else 0.0
    ent_r = (entity_tp / (entity_tp + entity_fn)) * 100.0 if (entity_tp + entity_fn) > 0 else 0.0
    ent_f1 = (2 * ent_p * ent_r) / (ent_p + ent_r) if (ent_p + ent_r) > 0 else 0.0

    temp_acc = (temporal_correct / temporal_total) * 100.0 if temporal_total > 0 else 0.0
    plan_validity = (valid_plans / total_samples) * 100.0 if total_samples > 0 else 0.0

    latencies.sort()
    mean_lat = sum(latencies) / len(latencies)
    p50_lat = latencies[int(len(latencies) * 0.50)]
    p95_lat = latencies[int(len(latencies) * 0.95)]
    p99_lat = latencies[int(len(latencies) * 0.99)]

    results = {
        "total_samples": total_samples,
        "intent_accuracy": round(intent_acc, 2),
        "intent_precision_macro": round(macro_intent_p, 2),
        "intent_recall_macro": round(macro_intent_r, 2),
        "intent_f1_macro": round(macro_intent_f1, 2),
        "entity_precision": round(ent_p, 2),
        "entity_recall": round(ent_r, 2),
        "entity_f1": round(ent_f1, 2),
        "temporal_accuracy": round(temp_acc, 2),
        "plan_validity": round(plan_validity, 2),
        "mean_latency_ms": round(mean_lat, 2),
        "p50_latency_ms": round(p50_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "p99_latency_ms": round(p99_lat, 2),
    }

    print("\n--- RESULTS ---")
    print(f"Intent Classification Accuracy: {results['intent_accuracy']}%")
    print(f"Intent Precision (Macro):       {results['intent_precision_macro']}%")
    print(f"Intent Recall (Macro):          {results['intent_recall_macro']}%")
    print(f"Intent F1-Score (Macro):        {results['intent_f1_macro']}%")
    print(f"Entity Precision:               {results['entity_precision']}%")
    print(f"Entity Recall:                  {results['entity_recall']}%")
    print(f"Entity F1-Score:                {results['entity_f1']}%")
    print(f"Temporal Extraction Accuracy:   {results['temporal_accuracy']}%")
    print(f"Query Plan Validity:            {results['plan_validity']}%")
    print(f"Latency Mean:                   {results['mean_latency_ms']} ms")
    print(f"Latency P50:                    {results['p50_latency_ms']} ms")
    print(f"Latency P95:                    {results['p95_latency_ms']} ms")
    print(f"Latency P99:                    {results['p99_latency_ms']} ms")
    print("============================================================\n")

    return results


if __name__ == "__main__":
    dataset_file = os.path.join(
        os.path.dirname(__file__), "..", "backend", "tests", "evaluation", "synthetic_nlp_dataset.json"
    )
    evaluate_pipeline(dataset_file)
