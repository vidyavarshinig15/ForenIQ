#!/usr/bin/env python3
"""
scripts/benchmark_ingestion.py
Forensic Ingestion & Persistence Throughput Benchmark

Generates synthetic heterogeneous forensic records across all 7 artifact domains
and measures batch persistence throughput, memory delta (RSS), and database latency.

Usage:
    python scripts/benchmark_ingestion.py --records 10000 --batch-size 500
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import os
import sys
import time
import uuid

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import async_session_factory, init_db
from backend.app.models.enums import ArtifactType
from backend.app.models.raw_artifact import RawArtifact
from backend.app.repositories.raw_artifact_repo import RawArtifactRepository

try:
    import resource

    def get_memory_mb() -> float:
        # ru_maxrss is in bytes on macOS, in kilobytes on Linux
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return rss / (1024 * 1024)
        return rss / 1024
except ImportError:
    def get_memory_mb() -> float:
        return 0.0


def generate_synthetic_record(
    index: int,
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    job_id: uuid.UUID,
) -> RawArtifact:
    """Generate a realistic synthetic forensic artifact across domains."""
    domains = [
        ArtifactType.CALL,
        ArtifactType.MESSAGE,
        ArtifactType.CONTACT,
        ArtifactType.LOCATION,
        ArtifactType.BROWSER,
        ArtifactType.APPLICATION,
        ArtifactType.FILESYSTEM,
    ]
    domain = domains[index % len(domains)]
    record_id = f"BENCH_{domain.value}_{index:08d}"
    source_file = f"{domain.value.lower()}_benchmark.xml"
    source_path = f"benchmark/{source_file}"

    # Rich payload
    if domain == ArtifactType.MESSAGE:
        raw_data = {
            "id": record_id,
            "sender": f"+1555{index % 10000:04d}",
            "receiver": f"+1555{(index * 3) % 10000:04d}",
            "content": f"Forensic transaction payload #{index} reference hash {hashlib.md5(str(index).encode()).hexdigest()[:8]}",
            "direction": "INCOMING" if index % 2 == 0 else "OUTGOING",
            "timestamp": "2026-09-30T10:00:00Z",
            "application": "WhatsApp",
        }
    elif domain == ArtifactType.CALL:
        raw_data = {
            "id": record_id,
            "caller": f"+1555{index % 10000:04d}",
            "receiver": f"+1555{(index * 7) % 10000:04d}",
            "duration": 45 + (index % 600),
            "direction": "MISSED" if index % 5 == 0 else "OUTGOING",
            "timestamp": "2026-09-30T10:15:00Z",
        }
    elif domain == ArtifactType.LOCATION:
        raw_data = {
            "id": record_id,
            "latitude": 37.7749 + (index % 1000) * 0.0001,
            "longitude": -122.4194 + (index % 1000) * 0.0001,
            "source": "GPS_FUSED",
            "accuracy": 4.5,
            "timestamp": "2026-09-30T10:30:00Z",
        }
    else:
        raw_data = {
            "id": record_id,
            "domain": domain.value,
            "index": index,
            "digest": hashlib.sha256(str(index).encode()).hexdigest()[:16],
            "timestamp": "2026-09-30T11:00:00Z",
        }

    identity_key = f"{evidence_id}:{source_file}:{source_path}:{record_id}:{domain.value}"
    fingerprint = hashlib.sha256(identity_key.encode("utf-8")).hexdigest()
    art_id = uuid.uuid5(evidence_id, identity_key)

    return RawArtifact(
        id=art_id,
        case_id=case_id,
        evidence_id=evidence_id,
        processing_job_id=job_id,
        artifact_type=domain,
        artifact_fingerprint=fingerprint,
        source_file=source_file,
        source_path=source_path,
        record_identifier=record_id,
        raw_data=raw_data,
        parsed_at=datetime.now(timezone.utc),
    )


async def run_benchmark(records_count: int, batch_size: int) -> None:
    print(f"\n==================================================================")
    print(f" UFDR Ingestion & Persistence Benchmark (Phase 6)")
    print(f" Total Records: {records_count:,} | Batch Size: {batch_size:,}")
    print(f"==================================================================\n")

    await init_db()

    case_id = uuid.uuid4()
    evidence_id = uuid.uuid4()
    job_id = uuid.uuid4()

    start_mem = get_memory_mb()
    print(f"[*] Initial Process RSS: {start_mem:.2f} MB")
    print(f"[*] Generating and persisting {records_count:,} records in batches of {batch_size:,}...")

    total_inserted = 0
    batches_count = 0
    start_time = time.time()

    async with async_session_factory() as session:
        repo = RawArtifactRepository(session)

        current_batch = []
        for i in range(records_count):
            item = generate_synthetic_record(i, case_id, evidence_id, job_id)
            current_batch.append(item)

            if len(current_batch) >= batch_size:
                inserted = await repo.bulk_create_or_ignore(current_batch)
                total_inserted += inserted
                batches_count += 1
                current_batch.clear()

                if batches_count % 5 == 0 or total_inserted >= records_count:
                    elapsed = max(0.001, time.time() - start_time)
                    rate = total_inserted / elapsed
                    print(
                        f"  -> Persisted {total_inserted:,}/{records_count:,} records "
                        f"({(total_inserted/records_count)*100:.1f}%) | "
                        f"Speed: {rate:,.1f} records/sec | Batches: {batches_count}"
                    )

        if current_batch:
            inserted = await repo.bulk_create_or_ignore(current_batch)
            total_inserted += inserted
            batches_count += 1
            current_batch.clear()

    total_duration = max(0.001, time.time() - start_time)
    end_mem = get_memory_mb()
    mem_delta = max(0.0, end_mem - start_mem)
    final_throughput = total_inserted / total_duration

    print(f"\n------------------------------------------------------------------")
    print(f" Benchmark Summary:")
    print(f"   Total Records Persisted : {total_inserted:,}")
    print(f"   Total Batches Committed : {batches_count:,}")
    print(f"   Execution Duration      : {total_duration:.3f} seconds")
    print(f"   Average Throughput      : {final_throughput:,.1f} records/second")
    print(f"   Initial Memory (RSS)    : {start_mem:.2f} MB")
    print(f"   Peak Memory (RSS)       : {end_mem:.2f} MB (Delta: +{mem_delta:.2f} MB)")
    print(f"------------------------------------------------------------------")

    # Verify idempotency by re-inserting same batch!
    print(f"\n[*] Testing Idempotency & Duplicate Prevention (Re-running same 100 records)...")
    async with async_session_factory() as session:
        repo = RawArtifactRepository(session)
        dup_batch = [generate_synthetic_record(i, case_id, evidence_id, job_id) for i in range(100)]
        await repo.bulk_create_or_ignore(dup_batch)

        # Check count in DB
        items, count = await repo.list_by_evidence(evidence_id, page=1, page_size=1)
        print(f"   Database Record Count after duplicate insert: {count:,} (Expected: {records_count:,})")
        assert count == records_count, f"Duplicate records were created! Expected {records_count}, got {count}"
        print(f"   [SUCCESS] Idempotency confirmed. 0 duplicate records created.")

        # Cleanup benchmark data
        await repo.delete_by_evidence_id(evidence_id)
        print(f"[*] Benchmark test records purged.\n")


def main():
    parser = argparse.ArgumentParser(description="UFDR Ingestion Benchmark")
    parser.add_argument("--records", type=int, default=5000, help="Number of records to generate")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for DB persistence")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.records, args.batch_size))


if __name__ == "__main__":
    main()
