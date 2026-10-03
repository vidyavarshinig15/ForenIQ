from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from backend.app.schemas.rag import EvidenceContextItem


class BaseLLMProvider(ABC):
    """
    Abstract base interface for all LLM providers in the forensic RAG pipeline.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical provider identifier (e.g. 'local', 'openai_compatible')."""
        pass

    @abstractmethod
    async def generate_answer(
        self,
        query: str,
        evidence_items: List[EvidenceContextItem],
        evidence_context_text: str,
        system_prompt: str,
        conversation_history_text: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Executes evidence-grounded generation against the supplied context.
        Must return the raw generated text adhering to the required forensic sections.
        """
        pass
