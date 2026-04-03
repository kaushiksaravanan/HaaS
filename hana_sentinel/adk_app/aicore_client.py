"""
SAP AI Core Client for GenAIHub Integration
============================================

Provides client for SAP AI Core (GenAIHub) to use gpt-4o model
instead of Google's Vertex AI/Gemini models.
"""

import os
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AICoreiClient:
    """Client for SAP AI Core (GenAIHub) LLM services.
    Falls back to local Hyperspace AI proxy if AI Core is not configured.
    """

    def __init__(self):
        """Initialize AI Core client with credentials from environment."""
        self.base_url = os.getenv("AICORE_BASE_URL", "")
        self.auth_url = os.getenv("AICORE_AUTH_URL", "")
        self.client_id = os.getenv("AICORE_CLIENT_ID", "")
        self.client_secret = os.getenv("AICORE_CLIENT_SECRET", "")
        self.resource_group = os.getenv("AICORE_RESOURCE_GROUP", "default")
        self.deployment_id = os.getenv("LLM_DEPLOYMENT_ID", "")
        self.model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")

        # AI proxy (Hyperspace AI) — tried first
        self._proxy_url = os.getenv("GENAIHUB_PROXY_URL", "http://localhost:6655")
        self._proxy_key = os.getenv("GENAIHUB_PROXY_API_KEY", "d3d25b98-d27a-4d9c-8f95-5d39731e3a3a")

        self._access_token = None
        self._token_expiry = None

        # Determine which backends are available
        self._proxy_available = bool(self._proxy_url and self._proxy_key)
        self._aicore_available = all([self.base_url, self.auth_url, self.client_id, self.client_secret])

        if self._proxy_available and self._aicore_available:
            logger.info("Both AI proxy (%s) and AI Core (%s) configured — proxy-first with AI Core fallback", self._proxy_url, self.base_url)
        elif self._proxy_available:
            logger.info("AI proxy configured at %s (no AI Core fallback)", self._proxy_url)
        elif self._aicore_available:
            logger.info("AI Core configured at %s (no proxy)", self.base_url)
        else:
            logger.warning("No LLM backend configured")

    def is_configured(self) -> bool:
        """Check if any LLM backend is available (AI proxy or AI Core)."""
        return self._proxy_available or self._aicore_available

    def _get_access_token(self) -> str:
        """Get or refresh OAuth access token."""
        # Check if we have a valid token
        if self._access_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._access_token

        # Request new token
        logger.info("Requesting new AI Core access token")

        try:
            response = requests.post(
                f"{self.auth_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 min buffer
                logger.info(f"Access token obtained, expires in {expires_in}s")
                return self._access_token
            else:
                logger.error(f"Token request failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get access token: {response.status_code}")

        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            raise

    def _proxy_chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send chat completion to local Hyperspace AI proxy (OpenAI-compatible)."""
        endpoint = f"{self._proxy_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._proxy_key}",
            "Content-Type": "application/json",
        }
        use_model = model or self.model_name
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            logger.info("Sending chat completion to AI proxy: %s (model=%s)", endpoint, use_model)
            response = requests.post(endpoint, json=payload, headers=headers, timeout=60)

            if response.status_code == 200:
                result = response.json()
                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                return {
                    "content": message.get("content", ""),
                    "usage": result.get("usage", {}),
                    "model": result.get("model", self.model_name),
                    "finish_reason": choice.get("finish_reason", ""),
                }
            else:
                logger.error("Local proxy request failed: %s - %s", response.status_code, response.text[:300])
                raise Exception(f"Local proxy request failed: {response.status_code}")
        except Exception as e:
            logger.error("Error in proxy chat completion: %s", e)
            raise

    def chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to AI Core or local proxy fallback.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            model: Optional model override (e.g. 'anthropic--claude-4.6-sonnet')
            **kwargs: Additional model parameters

        Returns:
            dict with 'content' and 'usage' information
        """
        if not self.is_configured():
            raise Exception("No LLM backend configured")

        # Strategy: try AI proxy first, fall back to AI Core on failure/timeout
        proxy_error = None
        if self._proxy_available:
            try:
                return self._proxy_chat_completion(messages, temperature, max_tokens, model=model, **kwargs)
            except Exception as e:
                proxy_error = e
                if self._aicore_available:
                    logger.warning("AI proxy failed (%s), falling back to AI Core", e)
                else:
                    raise  # No fallback available

        if not self._aicore_available:
            raise Exception("No LLM backend available")

        token = self._get_access_token()

        # Prepare request
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "AI-Resource-Group": self.resource_group,
        }

        # Build chat completion request
        use_model = model or self.model_name
        payload = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        # Add deployment ID if specified
        if self.deployment_id:
            headers["AI-Deployment-ID"] = self.deployment_id

        # SAP AI Core supports different endpoint formats:
        # Option 1: /v2/inference/deployments/{id}/chat/completions
        # Option 2: /v2/inference/deployments/{id}/v1/chat/completions (OpenAI proxy)
        # Option 3: /v2/lm/chat/completions (models API)
        if self.deployment_id:
            # Try OpenAI proxy format first
            endpoint = f"{self.base_url}/inference/deployments/{self.deployment_id}/v1/chat/completions"
        else:
            endpoint = f"{self.base_url}/lm/chat/completions"

        try:
            logger.info(f"Sending chat completion to {endpoint}")
            logger.debug(f"Headers: {{k: (v[:20] + '...') if k == 'Authorization' else v for k, v in headers.items()}}")
            logger.debug(f"Payload model={payload.get('model')}, messages={len(payload.get('messages', []))}")
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()

                # Extract response in OpenAI format
                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")

                return {
                    "content": content,
                    "usage": result.get("usage", {}),
                    "model": result.get("model", self.model_name),
                    "finish_reason": choice.get("finish_reason", "")
                }
            else:
                logger.error(f"Chat completion failed: {response.status_code} - {response.text}")
                raise Exception(f"AI Core request failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error in chat completion: {e}")
            raise

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        """
        Simple text generation (convenience method).

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model: Optional model override (e.g. 'anthropic--claude-4.6-sonnet')

        Returns:
            Generated text string
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        result = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
        )

        return result.get("content", "")


# Global instance
_aicore_client = None


def get_aicore_client() -> AICoreiClient:
    """Get or create global AI Core client instance."""
    global _aicore_client
    if _aicore_client is None:
        _aicore_client = AICoreiClient()
    return _aicore_client


def test_aicore_connection() -> Dict[str, Any]:
    """
    Test AI Core connection and model.

    Returns:
        dict with test results
    """
    try:
        client = get_aicore_client()

        if not client.is_configured():
            return {
                "status": "error",
                "error": "AI Core not configured - missing credentials"
            }

        # Test simple completion
        response = client.generate_text(
            prompt="Say 'Hello from SAP AI Core!' in one sentence.",
            temperature=0.0,
            max_tokens=50
        )

        return {
            "status": "success",
            "model": client.model_name,
            "response": response,
            "configured": True
        }

    except Exception as e:
        logger.error(f"AI Core connection test failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "configured": False
        }
