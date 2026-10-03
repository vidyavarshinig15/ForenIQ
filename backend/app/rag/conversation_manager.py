from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import uuid

from backend.app.schemas.rag import EvidenceCitation, RAGConversationHistory, RAGConversationMessage

logger = logging.getLogger(__name__)


class CaseScopedConversationManager:
    """
    Manages in-memory case-isolated multi-turn conversational investigation sessions.
    Strictly guarantees that session history cannot leak across case boundaries.
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        # Key: (case_id, conversation_id) -> RAGConversationHistory
        self._conversations: Dict[str, RAGConversationHistory] = {}

    def _get_key(self, case_id: str, conversation_id: str) -> str:
        return f"{str(case_id).strip()}::{str(conversation_id).strip()}"

    def get_or_create_conversation(self, case_id: str, conversation_id: Optional[str] = None) -> RAGConversationHistory:
        case_id_clean = str(case_id).strip()
        conv_id = conversation_id.strip() if conversation_id else str(uuid.uuid4())
        key = self._get_key(case_id_clean, conv_id)

        if key not in self._conversations:
            now_iso = datetime.now(timezone.utc).isoformat()
            self._conversations[key] = RAGConversationHistory(
                conversation_id=conv_id,
                case_id=case_id_clean,
                messages=[],
                created_at=now_iso,
                updated_at=now_iso,
            )
        return self._conversations[key]

    def add_turn(
        self,
        case_id: str,
        conversation_id: str,
        role: str,
        content: str,
        evidence_references: Optional[List[EvidenceCitation]] = None,
    ) -> RAGConversationMessage:
        conv = self.get_or_create_conversation(case_id, conversation_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        message = RAGConversationMessage(
            message_id=str(uuid.uuid4()),
            case_id=str(case_id).strip(),
            role=role,
            content=content,
            timestamp=now_iso,
            evidence_references=evidence_references or [],
        )

        conv.messages.append(message)
        conv.updated_at = now_iso

        # Enforce bounded history size
        if len(conv.messages) > self.max_turns * 2:
            conv.messages = conv.messages[-self.max_turns * 2 :]

        return message

    def get_history(self, case_id: str, conversation_id: str) -> List[RAGConversationMessage]:
        key = self._get_key(case_id, conversation_id)
        if key in self._conversations:
            return list(self._conversations[key].messages)
        return []

    def format_history_for_prompt(self, case_id: str, conversation_id: str) -> str:
        messages = self.get_history(case_id, conversation_id)
        if not messages:
            return ""

        formatted_lines = []
        for msg in messages[-6:]:  # use last 3 dialogue turns
            role_label = "Investigator" if msg.role == "user" else "Assistant"
            formatted_lines.append(f"{role_label}: {msg.content}")

        return "\n".join(formatted_lines)

    def clear_conversation(self, case_id: str, conversation_id: str) -> bool:
        key = self._get_key(case_id, conversation_id)
        if key in self._conversations:
            del self._conversations[key]
            return True
        return False


# Global singleton instance
conversation_manager = CaseScopedConversationManager()
