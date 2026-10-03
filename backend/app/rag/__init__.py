"""
Phase 12 — Retrieval-Augmented Generation (RAG) & Evidence-Grounded Investigator Assistant
"""

from backend.app.rag.citation_validator import CitationValidationService
from backend.app.rag.context_builder import EvidenceContextBuilder
from backend.app.rag.conversation_manager import CaseScopedConversationManager, conversation_manager
from backend.app.rag.prompts import SYSTEM_PROMPT_FORENSIC_RAG, RAG_PROMPT_VERSION, build_evidence_block, build_user_query_block
from backend.app.rag.providers.base import BaseLLMProvider
from backend.app.rag.providers.factory import get_llm_provider
from backend.app.rag.providers.local_provider import DeterministicForensicRAGProvider
from backend.app.rag.providers.openai_compatible_provider import OpenAICompatibleProvider
from backend.app.rag.rag_service import ForensicRAGService

__all__ = [
    "CitationValidationService",
    "EvidenceContextBuilder",
    "CaseScopedConversationManager",
    "conversation_manager",
    "SYSTEM_PROMPT_FORENSIC_RAG",
    "RAG_PROMPT_VERSION",
    "build_evidence_block",
    "build_user_query_block",
    "BaseLLMProvider",
    "DeterministicForensicRAGProvider",
    "OpenAICompatibleProvider",
    "get_llm_provider",
    "ForensicRAGService",
]
