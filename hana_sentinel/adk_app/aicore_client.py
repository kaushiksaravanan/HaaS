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
    """Client for SAP AI Core (GenAIHub) LLM services."""

    def __init__(self):
        """Initialize AI Core client with credentials from environment."""
        self.base_url = os.getenv("AICORE_BASE_URL", "")
        self.auth_url = os.getenv("AICORE_AUTH_URL", "")
        self.client_id = os.getenv("AICORE_CLIENT_ID", "")
        self.client_secret = os.getenv("AICORE_CLIENT_SECRET", "")
        self.resource_group = os.getenv("AICORE_RESOURCE_GROUP", "default")
        self.deployment_id = os.getenv("LLM_DEPLOYMENT_ID", "")
        self.model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")

        self._access_token = None
        self._token_expiry = None

        if not all([self.base_url, self.auth_url, self.client_id, self.client_secret]):
            logger.warning("AI Core credentials not fully configured")

    def is_configured(self) -> bool:
        """Check if AI Core is properly configured."""
        return bool(
            self.base_url
            and self.auth_url
            and self.client_id
            and self.client_secret
        )

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

    def chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to AI Core.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional model parameters

        Returns:
            dict with 'content' and 'usage' information
        """
        if not self.is_configured():
            raise Exception("AI Core not configured")

        token = self._get_access_token()

        # Prepare request
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "AI-Resource-Group": self.resource_group,
        }

        # Build chat completion request
        payload = {
            "model": self.model_name,
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
            logger.info(f"Headers: {headers}")
            logger.info(f"Payload: {payload}")
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
        max_tokens: int = 2048
    ) -> str:
        """
        Simple text generation (convenience method).

        Args:
            prompt: User prompt
            system_prompt: Optional system instruction
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

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
            max_tokens=max_tokens
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
