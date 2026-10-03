import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from backend.app.core.config import settings
from backend.app.rag.prompts import build_evidence_block, build_user_query_block
from backend.app.rag.providers.base import BaseLLMProvider
from backend.app.schemas.rag import EvidenceContextItem

logger = logging.getLogger(__name__)


class ForensicPrivacyBoundaryException(Exception):
    """Raised when an attempt is made to transmit evidence externally without authorization."""
    pass


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    Provider supporting OpenAI-compatible LLM endpoints (e.g. Ollama, vLLM, LocalAI, LM Studio, OpenAI).
    Enforces air-gap boundaries unless RAG_ALLOW_EXTERNAL_APIS is explicitly enabled.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.RAG_OPENAI_BASE_URL or "http://localhost:11434/v1").rstrip("/")
        self.api_key = api_key or settings.RAG_OPENAI_API_KEY or "none"
        model = model_name or settings.RAG_LLM_MODEL or "llama3.2:3b"
        super().__init__(model_name=model)

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    def _validate_privacy_boundary(self) -> None:
        """
        Ensures evidence is not leaked to unauthorized cloud providers.
        """
        parsed = urlparse(self.base_url)
        hostname = (parsed.hostname or "").lower()
        is_local = hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or hostname.endswith(".local")

        if not is_local and not settings.RAG_ALLOW_EXTERNAL_APIS:
            raise ForensicPrivacyBoundaryException(
                f"Data Privacy Boundary Violation: Cannot transmit forensic evidence to external endpoint "
                f"'{self.base_url}' because RAG_ALLOW_EXTERNAL_APIS is disabled."
            )

    async def generate_answer(
        self,
        query: str,
        evidence_items: List[EvidenceContextItem],
        evidence_context_text: str,
        system_prompt: str,
        conversation_history_text: str = "",
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        self._validate_privacy_boundary()

        evidence_block = build_evidence_block(evidence_context_text)
        user_block = build_user_query_block(query, conversation_history_text)
        combined_user_content = f"{evidence_block}\n\n{user_block}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_user_content},
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": settings.RAG_TEMPERATURE,
            "max_tokens": settings.RAG_MAX_OUTPUT_TOKENS,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return str(content)
        except Exception as e:
            logger.error(f"OpenAI-compatible LLM provider failure: {e}")
            raise
