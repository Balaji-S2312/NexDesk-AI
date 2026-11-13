import logging
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class GroqClientError(Exception):
    """Base exception for Groq client errors."""
    pass

class GroqAuthenticationError(GroqClientError):
    """Raised when API key is missing or invalid."""
    pass

class GroqRateLimitError(GroqClientError):
    """Raised when rate limits are exceeded."""
    pass

class GroqAPIError(GroqClientError):
    """Raised on 5xx or unhandled API errors."""
    pass

class GroqClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL or "openai/gpt-oss-120b"
        self.base_url = "https://api.groq.com/openai/v1"
        self.timeout = 30.0

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 1024,
    ) -> str:
        if not self.is_configured():
            logger.warning("Groq API key not configured.")
            raise GroqAuthenticationError("GROQ_API_KEY is not set in the environment or .env configuration.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Safe logging without exposing sensitive data
        sanitized_key = f"{self.api_key[:6]}...{self.api_key[-4:]}" if len(self.api_key) > 10 else "***"
        logger.info(f"Dispatching Groq chat completion request [model={self.model}, key={sanitized_key}, messages_count={len(messages)}]")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
            except httpx.TimeoutException as e:
                logger.error(f"Groq API call timed out after {self.timeout}s")
                raise GroqClientError("The AI service request timed out. Please try again.") from e
            except httpx.RequestError as e:
                logger.error(f"Network error communicating with Groq API: {str(e)}")
                raise GroqClientError(f"Network error contacting AI service: {str(e)}") from e

        if response.status_code == 200:
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
                return content
            except (KeyError, IndexError) as e:
                logger.error(f"Malformed response payload from Groq: {data}")
                raise GroqAPIError("Received malformed response structure from Groq.") from e
        elif response.status_code == 401:
            logger.error("Groq API 401 Unauthorized - invalid API key.")
            raise GroqAuthenticationError("Invalid Groq API Key.")
        elif response.status_code == 429:
            logger.warning("Groq API 429 Too Many Requests / Rate Limited.")
            raise GroqRateLimitError("AI rate limit reached. Please wait a moment and try again.")
        else:
            logger.error(f"Groq API error HTTP {response.status_code}: {response.text}")
            raise GroqAPIError(f"AI Service Error ({response.status_code}): {response.text}")

# Global client singleton
groq_client = GroqClient()
