import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.user import User
from backend.app.rag.conversation_manager import conversation_manager
from backend.app.rag.rag_service import ForensicRAGService
from backend.app.schemas.rag import (
    RAGConversationHistory,
    RAGQueryRequest,
    RAGQueryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{case_id}/rag/query",
    response_model=RAGQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute evidence-grounded natural language investigation inquiry",
)
async def execute_rag_investigation_query(
    case_id: UUID = Path(..., description="ID of the case under investigation"),
    request: RAGQueryRequest = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_forwarded_for: Optional[str] = Header(None),
) -> RAGQueryResponse:
    """
    Executes a strict evidence-grounded natural language query:
    1. Parses query using Phase 11 NLP Intent & Entity extraction.
    2. Performs case-scoped Phase 9/10 hybrid search.
    3. Builds bounded, deduplicated context blocks.
    4. Generates structured response via configured LLM provider.
    5. Validates evidence citations and guarantees zero cross-case leakage.
    6. Logs audit trail with reproducibility metadata.
    """
    rag_service = ForensicRAGService(db)
    return await rag_service.execute_rag_query(
        case_id=case_id,
        current_user=current_user,
        request=request,
        client_ip=x_forwarded_for,
    )


@router.get(
    "/{case_id}/rag/conversations/{conversation_id}",
    response_model=RAGConversationHistory,
    status_code=status.HTTP_200_OK,
    summary="Get case-scoped conversation history",
)
async def get_rag_conversation_history(
    case_id: UUID = Path(..., description="Case ID"),
    conversation_id: str = Path(..., description="Conversation session ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RAGConversationHistory:
    """
    Retrieves the multi-turn investigation history for the specific case and session.
    """
    rag_service = ForensicRAGService(db)
    await rag_service.search_service._verify_case_access(case_id, current_user)

    conv = conversation_manager.get_or_create_conversation(str(case_id), conversation_id)
    return conv


@router.delete(
    "/{case_id}/rag/conversations/{conversation_id}",
    status_code=status.HTTP_200_OK,
    summary="Clear case-scoped conversation session",
)
async def clear_rag_conversation(
    case_id: UUID = Path(..., description="Case ID"),
    conversation_id: str = Path(..., description="Conversation session ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deletes the conversation context for the specified case and session.
    """
    rag_service = ForensicRAGService(db)
    await rag_service.search_service._verify_case_access(case_id, current_user)

    success = conversation_manager.clear_conversation(str(case_id), conversation_id)
    return {"message": "Conversation history cleared successfully", "cleared": success}
