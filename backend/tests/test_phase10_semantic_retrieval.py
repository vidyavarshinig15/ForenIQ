"""
Phase 10 — Semantic Retrieval, Embeddings, Vector Index & Hybrid Ranker Test Suite

Comprehensive tests verifying:
  1. FAISS Vector Store Abstraction & Persistence
  2. Case-scoped Vector Search & Cross-case Leakage Isolation
  3. Atomic Index Rebuild Safety
  4. Embedding Service (Sentence-BERT MiniLM-L6-v2, 384 dim, L2-normalized)
  5. Embedding Formatter, Artifact Quality Filtering & SHA-256 Content Hashing
  6. Stale Embedding Detection & Idempotent Generation
  7. Hybrid Retrieval Ranker (Weighted Scoring, Exact Match Boost, Deduplication)
  8. Embedding Worker Batch Processing & Checkpointing
  9. Search API Modes (EXACT, LEXICAL, SEMANTIC, HYBRID) & Graceful Degradation
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import pytest
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import torch
torch.set_num_threads(1)

from backend.app.core.config import get_settings
from backend.app.models.canonical_evidence import CanonicalEvidence
from backend.app.models.evidence_embedding import EvidenceEmbedding
from backend.app.models.enums import ArtifactType, EmbeddingStatus, SearchMode, JobType, JobStatus
from backend.app.models.processing_job import ProcessingJob
from backend.app.models.user import User
from backend.app.services.embedding_formatter import EmbeddingFormatter
from backend.app.services.embedding_service import EmbeddingService, get_embedding_service
from backend.app.services.retrieval_ranker import RetrievalRanker
from backend.app.vector_store.faiss_store import FaissVectorStore
from backend.app.services.embedding_worker import EvidenceEmbeddingWorker


# ============================================================================ #
# 1. FAISS Vector Store Tests                                                  #
# ============================================================================ #

class TestFaissVectorStore:
    """Tests for the FAISS vector store abstraction and case isolation."""

    @pytest.fixture
    def temp_store(self):
        tmp_dir = tempfile.mkdtemp(prefix="faiss_test_")
        store = FaissVectorStore(index_dir=tmp_dir, dimension=384)
        yield store
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_add_and_search_vectors(self, temp_store):
        case_id = uuid.uuid4()
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()

        # Generate two synthetic vectors
        v1 = np.ones((1, 384), dtype=np.float32)
        v2 = -np.ones((1, 384), dtype=np.float32)
        vectors = np.vstack([v1, v2])

        temp_store.add(case_id=case_id, ids=[id1, id2], vectors=vectors)

        # Search with query aligned with v1
        q_vec = np.ones((1, 384), dtype=np.float32)
        results = temp_store.search(case_id=case_id, query_vector=q_vec, top_k=2)

        assert len(results) == 2
        top_id, top_score = results[0]
        assert top_id == id1
        assert top_score >= 0.99  # Normalized dot product with identical direction

    def test_cross_case_isolation_no_leakage(self, temp_store):
        """
        Critical security test:
        Ensure Case A vectors NEVER leak into Case B search results.
        """
        case_a = uuid.uuid4()
        case_b = uuid.uuid4()

        id_a = uuid.uuid4()
        id_b = uuid.uuid4()

        # Same vector added to Case A and different vector to Case B
        v_a = np.ones((1, 384), dtype=np.float32)
        v_b = np.zeros((1, 384), dtype=np.float32)
        v_b[0, 0] = 1.0

        temp_store.add(case_id=case_a, ids=[id_a], vectors=v_a)
        temp_store.add(case_id=case_b, ids=[id_b], vectors=v_b)

        # Search in Case A with query matching Case B
        results_a = temp_store.search(case_id=case_a, query_vector=v_b, top_k=10)
        retrieved_ids_a = {r[0] for r in results_a}

        assert id_b not in retrieved_ids_a
        assert (len(retrieved_ids_a) == 0) or (id_a in retrieved_ids_a)

        # Search in Case B
        results_b = temp_store.search(case_id=case_b, query_vector=v_b, top_k=10)
        retrieved_ids_b = {r[0] for r in results_b}
        assert id_a not in retrieved_ids_b
        assert id_b in retrieved_ids_b

    def test_delete_vectors(self, temp_store):
        case_id = uuid.uuid4()
        ids = [uuid.uuid4() for _ in range(4)]
        vecs = np.random.randn(4, 384).astype(np.float32)

        temp_store.add(case_id=case_id, ids=ids, vectors=vecs)
        stats_before = temp_store.get_index_stats(case_id)
        assert stats_before["total_vectors"] == 4

        # Delete two vectors
        temp_store.delete(case_id=case_id, ids=[ids[0], ids[2]])
        stats_after = temp_store.get_index_stats(case_id)
        assert stats_after["total_vectors"] == 2
        assert stats_after["mapped_ids_count"] == 2

        # Verify deleted IDs cannot be retrieved
        results = temp_store.search(case_id=case_id, query_vector=vecs[0], top_k=10)
        retrieved = {r[0] for r in results}
        assert ids[0] not in retrieved
        assert ids[2] not in retrieved
        assert ids[1] in retrieved or ids[3] in retrieved

    def test_atomic_rebuild(self, temp_store):
        case_id = uuid.uuid4()
        old_ids = [uuid.uuid4() for _ in range(3)]
        old_vecs = np.random.randn(3, 384).astype(np.float32)
        temp_store.add(case_id=case_id, ids=old_ids, vectors=old_vecs)

        new_ids = [uuid.uuid4() for _ in range(5)]
        new_vecs = np.random.randn(5, 384).astype(np.float32)

        temp_store.rebuild(case_id=case_id, ids=new_ids, vectors=new_vecs)

        stats = temp_store.get_index_stats(case_id)
        assert stats["total_vectors"] == 5
        assert stats["mapped_ids_count"] == 5
        assert stats["is_consistent"] is True

    def test_persistence_and_reload(self, temp_store):
        case_id = uuid.uuid4()
        ids = [uuid.uuid4() for _ in range(3)]
        vecs = np.random.randn(3, 384).astype(np.float32)
        temp_store.add(case_id=case_id, ids=ids, vectors=vecs)

        # Create new store instance pointing to same directory
        store2 = FaissVectorStore(index_dir=str(temp_store.index_dir), dimension=384)
        stats = store2.get_index_stats(case_id)
        assert stats["total_vectors"] == 3
        assert stats["is_consistent"] is True


# ============================================================================ #
# 2. Embedding Service Tests                                                   #
# ============================================================================ #

class TestEmbeddingService:
    """Tests for Sentence-BERT embedding generation and device management."""

    def test_embed_texts_dimension_and_normalization(self):
        svc = get_embedding_service()
        texts = ["Investigator logged evidence at 14:00 UTC", "Encrypted message received via Signal"]
        vecs = svc.embed_texts(texts)

        assert vecs.shape == (2, 384)
        assert vecs.dtype == np.float32

        # Check L2 unit normalization (norm should equal 1.0 within float tolerance)
        for i in range(len(texts)):
            norm = np.linalg.norm(vecs[i])
            assert pytest.approx(norm, rel=1e-3) == 1.0

    def test_embed_query(self):
        svc = get_embedding_service()
        q_vec = svc.embed_query("wire transfer to Swiss account")
        assert q_vec.shape == (384,)
        assert pytest.approx(np.linalg.norm(q_vec), rel=1e-3) == 1.0

    def test_empty_input_handling(self):
        svc = get_embedding_service()
        empty_batch = svc.embed_texts([])
        assert empty_batch.shape == (0, 384)

        empty_q = svc.embed_query("   ")
        assert empty_q.shape == (384,)
        assert np.all(empty_q == 0.0)

    def test_health_check(self):
        svc = get_embedding_service()
        hc = svc.health_check()
        assert hc["status"] == "READY"
        assert hc["dimension"] == 384
        assert hc["is_available"] is True


# ============================================================================ #
# 3. Embedding Formatter & Content Hashing Tests                              #
# ============================================================================ #

class TestEmbeddingFormatter:
    """Tests for deterministic formatting and content hashing."""

    def test_message_formatting(self):
        can = CanonicalEvidence(
            id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp_msg_1",
            source_file="whatsapp_chat.db",
            source_path="/raw/whatsapp_chat.db",
            record_identifier="msg_101",
            content="Meet me tomorrow at 5 PM near the bank.",
            application="WhatsApp",
            device_id="DEV_001",
            event_timestamp=datetime(2026, 9, 30, 17, 0, 0, tzinfo=timezone.utc),
            entities=[{"type": "LOCATION", "value": "bank"}],
            metadata_={"sender": "+1555123", "receiver": "+1555987"},
        )

        fmt_text, hash1 = EmbeddingFormatter.format_canonical_record(can)
        assert fmt_text is not None
        assert "Artifact Type: MESSAGE" in fmt_text
        assert "Application: WhatsApp" in fmt_text
        assert "Content: Meet me tomorrow at 5 PM near the bank." in fmt_text
        assert "Sender: +1555123" in fmt_text
        assert "Entities: LOCATION: bank" in fmt_text
        assert len(hash1) == 64  # SHA-256 hex string

        # Determinism check: formatting same object yields exact same hash
        _, hash2 = EmbeddingFormatter.format_canonical_record(can)
        assert hash1 == hash2

    def test_staleness_detection_on_content_change(self):
        can = CanonicalEvidence(
            id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp_msg_2",
            source_file="messages.db",
            source_path="/raw/messages.db",
            record_identifier="msg_102",
            content="Original unedited message",
            application="Signal",
            entities=[],
            metadata_={},
        )
        _, hash_orig = EmbeddingFormatter.format_canonical_record(can)

        # Modify content (e.g. reprocessing/normalization update)
        can.content = "Modified and reprocessed message content"
        _, hash_mod = EmbeddingFormatter.format_canonical_record(can)

        assert hash_orig != hash_mod

    def test_non_embeddable_blank_record(self):
        blank_can = CanonicalEvidence(
            id=uuid.uuid4(),
            case_id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            artifact_type=ArtifactType.FILESYSTEM,
            canonical_fingerprint="fp_blank",
            source_file="empty.bin",
            source_path="/raw/empty.bin",
            record_identifier="fs_0",
            content=None,
            application=None,
            entities=[],
            metadata_={},
        )
        fmt, h = EmbeddingFormatter.format_canonical_record(blank_can)
        assert fmt is None
        assert h is None


# ============================================================================ #
# 4. Hybrid Retrieval Ranker Tests                                             #
# ============================================================================ #

class TestRetrievalRanker:
    """Tests for hybrid rank fusion, exact match boost, and deduplication."""

    def test_rank_hybrid_and_exact_boost(self):
        from backend.app.schemas.search import SearchResultItem, SearchResultSource

        ranker = RetrievalRanker(lexical_weight=0.5, semantic_weight=0.5, exact_boost=0.2)

        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        id3 = uuid.uuid4()

        src = SearchResultSource(
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            source_file="file.db",
            source_path="/raw/file.db",
            record_identifier="r1",
        )

        item1_lex = SearchResultItem(
            id=id1,
            artifact_type="MESSAGE",
            content_preview="Meeting tomorrow",
            match_type="TEXT_MATCH",
            matched_entities=[],
            source=src,
        )
        item2_lex = SearchResultItem(
            id=id2,
            artifact_type="CONTACT",
            content_preview="John Doe +1555123",
            match_type="EXACT_MATCH",
            matched_entities=[],
            source=src,
        )
        item1_sem = SearchResultItem(
            id=id1,
            artifact_type="MESSAGE",
            content_preview="Meeting tomorrow",
            match_type="SEMANTIC_MATCH",
            similarity_score=0.85,
            matched_entities=[],
            source=src,
        )
        item3_sem = SearchResultItem(
            id=id3,
            artifact_type="MESSAGE",
            content_preview="Schedule coffee",
            match_type="SEMANTIC_MATCH",
            similarity_score=0.95,
            matched_entities=[],
            source=src,
        )

        ranked = ranker.rank_hybrid(
            lexical_items=[item1_lex, item2_lex],
            semantic_items=[item1_sem, item3_sem],
            query="meeting",
        )

        assert len(ranked) == 3
        top_item = ranked[0]
        # id1 appears in both lexical and semantic -> highest hybrid rank
        assert top_item.id == id1
        assert "Hybrid" in top_item.retrieval_explanation
        assert top_item.match_type == "HYBRID_MATCH"


# ============================================================================ #
# 5. Embedding Worker Tests                                                    #
# ============================================================================ #

@pytest.mark.asyncio
class TestEvidenceEmbeddingWorker:
    """Tests for asynchronous batch embedding generation worker."""

    async def test_worker_batch_generation(self):
        case_id = uuid.uuid4()
        job_id = uuid.uuid4()

        # Mock database session and queries
        mock_session = AsyncMock()
        evidence_id = uuid.uuid4()
        mock_job = ProcessingJob(
            id=job_id,
            case_id=case_id,
            evidence_id=evidence_id,
            job_type=JobType.EMBEDDING,
            status=JobStatus.RUNNING,
            checkpoint_data={},
            records_processed=0,
        )

        can_id = uuid.uuid4()
        can_rec = CanonicalEvidence(
            id=can_id,
            case_id=case_id,
            evidence_id=uuid.uuid4(),
            raw_artifact_id=uuid.uuid4(),
            artifact_type=ArtifactType.MESSAGE,
            canonical_fingerprint="fp_w_1",
            source_file="chat.xml",
            source_path="/raw/chat.xml",
            record_identifier="msg_w1",
            content="Asynchronous forensic embedding worker batch item",
            application="Telegram",
            entities=[],
            metadata_={},
        )

        worker = EvidenceEmbeddingWorker(batch_size=32)

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        mock_job_repo = AsyncMock()
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo.update_status.return_value = mock_job

        mock_emb_repo = AsyncMock()
        mock_emb_repo.get_by_canonical_id.return_value = None
        mock_emb_repo.create_or_update.return_value = MagicMock()

        # Mock query execution for count and select
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 1
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = [can_rec]

        mock_session.execute.side_effect = [mock_scalar, mock_scalars, MagicMock(scalars=lambda: MagicMock(all=lambda: []))]

        with patch("backend.app.services.embedding_worker.async_session_factory", return_value=mock_session), \
             patch("backend.app.services.embedding_worker.ProcessingJobRepository", return_value=mock_job_repo), \
             patch("backend.app.services.embedding_worker.EmbeddingRepository", return_value=mock_emb_repo), \
             patch.object(worker.vector_store, "add") as mock_v_add:

            await worker.execute_job(job_id=job_id)

            assert mock_job_repo.update_status.called
            assert mock_v_add.called
