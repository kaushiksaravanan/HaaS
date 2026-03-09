"""
LangChain-compatible wrapper for SAP AI Core (GenAIHub).
Provides ChatGenAIHub class that can be used with browser-use and other LangChain tools.
"""

import os
import logging
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import ConfigDict

from .aicore_client import get_aicore_client

logger = logging.getLogger(__name__)


class ChatGenAIHub(BaseChatModel):
    """LangChain-compatible chat model wrapper for SAP AI Core (GenAIHub).

    This allows browser-use and other LangChain tools to use GenAIHub models
    instead of Google Vertex AI or OpenAI directly.

    Usage:
        llm = ChatGenAIHub()
        response = llm.invoke("Hello!")
    """

    # Allow extra fields for browser-use compatibility (it monkey-patches ainvoke, etc.)
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    model_name: str = "gpt-4o"
    model: str = "gpt-4o"  # Alias for browser-use compatibility
    temperature: float = 0.7
    max_tokens: int = 4096
    provider: str = "openai"  # browser-use compatibility - GenAIHub uses OpenAI-compatible API

    def __init__(self, **kwargs):
        """Initialize ChatGenAIHub with optional model parameters."""
        super().__init__(**kwargs)
        # Get model name from env if not provided
        if "model_name" not in kwargs:
            self.model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")
        # Keep model in sync with model_name
        self.model = self.model_name

    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "genaihub"

    @property
    def _identifying_params(self) -> dict:
        """Return parameters that identify this model."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        """Convert LangChain messages to GenAIHub format."""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
            else:
                # Default to user message
                converted.append({"role": "user", "content": str(msg.content)})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs
    ) -> ChatResult:
        """Generate a response using GenAIHub.

        Args:
            messages: List of LangChain messages
            stop: Optional stop sequences
            run_manager: Optional callback manager
            **kwargs: Additional model parameters

        Returns:
            ChatResult with generated response
        """
        client = get_aicore_client()

        if not client.is_configured():
            raise ValueError(
                "GenAIHub (AI Core) not configured. "
                "Set AICORE_BASE_URL, AICORE_AUTH_URL, AICORE_CLIENT_ID, AICORE_CLIENT_SECRET in .env"
            )

        # Convert messages
        genaihub_messages = self._convert_messages(messages)

        # Merge kwargs with defaults
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        try:
            # Call GenAIHub
            response = client.chat_completion(
                messages=genaihub_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.get("content", "")

            # Create ChatGeneration
            generation = ChatGeneration(
                message=AIMessage(content=content),
                generation_info={
                    "model": response.get("model", self.model_name),
                    "usage": response.get("usage", {}),
                    "finish_reason": response.get("finish_reason", ""),
                }
            )

            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"GenAIHub generation failed: {e}")
            raise

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs
    ) -> ChatResult:
        """Async generate - currently delegates to sync version."""
        # TODO: Implement true async when aicore_client supports it
        return self._generate(messages, stop, run_manager, **kwargs)


def get_chat_model() -> ChatGenAIHub:
    """Get a configured ChatGenAIHub instance.

    Returns:
        ChatGenAIHub instance ready to use

    Raises:
        ValueError if GenAIHub is not configured
    """
    client = get_aicore_client()
    if not client.is_configured():
        raise ValueError(
            "GenAIHub not configured. Set AICORE_* environment variables."
        )
    return ChatGenAIHub()


def test_chat_model() -> dict:
    """Test the ChatGenAIHub model.

    Returns:
        dict with test results
    """
    try:
        llm = get_chat_model()
        response = llm.invoke("Say 'GenAIHub LangChain wrapper working!' in one sentence.")

        return {
            "status": "success",
            "model": llm.model_name,
            "response": response.content,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }
