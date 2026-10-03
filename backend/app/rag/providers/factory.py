import logging
from typing import Optional

from backend.app.core.config import settings
from backend.app.rag.providers.base import BaseLLMProvider
from backend.app.rag.providers.local_provider import DeterministicForensicRAGProvider
from backend.app.rag.providers.openai_compatible_provider import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> BaseLLMProvider:
    """
    Factory function to retrieve the configured LLM provider instance.
    Defaults to 100% offline DeterministicForensicRAGProvider for zero external dependencies.
    """
    selected_provider = (provider_name or settings.RAG_LLM_PROVIDER or "local").lower().strip()
    selected_model = model_name or settings.RAG_LLM_MODEL or "deterministic-forensic-rag-v1"

    if selected_provider in ("local", "deterministic", "offline"):
        return DeterministicForensicRAGProvider(model_name=selected_model)
    elif selected_provider in ("openai_compatible", "ollama", "vllm", "openai"):
        return OpenAICompatibleProvider(model_name=selected_model)
    else:
        logger.warning(
            f"Unknown LLM provider '{selected_provider}', falling back to local deterministic provider."
        )
        return DeterministicForensicRAGProvider(model_name=selected_model)
