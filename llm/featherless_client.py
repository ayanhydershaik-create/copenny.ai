"""
llm/featherless_client.py
Featherless.ai OpenAI-compatible API client.
Replaces the old Gemini + OpenRouter LLMClient.

- Single FEATHERLESS_API_KEY (no key rotation)
- Model: Qwen/Qwen2.5-7B-Instruct
- Supports: sync complete(), async acomplete(), async stream_complete()
- Bias shield preserved
"""
import os
import httpx
import asyncio
from typing import Optional, AsyncIterator
from dotenv import load_dotenv

load_dotenv(override=True)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
FEATHERLESS_MODEL = "Qwen/Qwen2.5-7B-Instruct"


class FeatherlessClient:
    """
    Lightweight async-first client for the Featherless.ai OpenAI-compatible API.
    """

    def __init__(self, timeout: float = 60.0):
        self.api_key = os.getenv("FEATHERLESS_API_KEY", "")
        self.model = os.getenv("FEATHERLESS_MODEL", FEATHERLESS_MODEL)
        self.timeout = timeout
        self.base_url = FEATHERLESS_BASE_URL

        if not self.api_key:
            print("[FeatherlessClient] WARNING: FEATHERLESS_API_KEY not set.")
        else:
            print(f"[FeatherlessClient] Initialized. Model: {self.model}")

    # ──────────────────────────────────────────────────────────────
    # Bias shield (preserved from original)
    # ──────────────────────────────────────────────────────────────

    def audit_bias(self, text: str) -> str:
        bias_indicators = [
            "typical for your age", "because you are a woman", "given your gender",
            "people from your country", "at your income bracket", "stereotypical"
        ]
        detected = [bi for bi in bias_indicators if bi.lower() in text.lower()]
        if detected:
            print(f"[BIAS SHIELD] Potential bias detected: {detected}")
            return text + "\n\n[Fairness Note: This response was audited for bias.]"
        return text

    def _build_messages(self, prompt: str, system: Optional[str]) -> list:
        messages = []
        if system:
            messages.append({"role": "system", "content": system.strip()})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────────────────────
    # Synchronous completion
    # ──────────────────────────────────────────────────────────────

    def complete(self, prompt: str, system: Optional[str] = None,
                 max_tokens: int = 2048, temperature: float = 0.7) -> str:
        """Synchronous completion via Featherless.ai."""
        import requests

        body = {
            "model": self.model,
            "messages": self._build_messages(prompt, system),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            js = resp.json()
            text = js["choices"][0]["message"]["content"]
            return self.audit_bias(text)
        except Exception as e:
            print(f"[FeatherlessClient] complete() error: {e}")
            raise

    # ──────────────────────────────────────────────────────────────
    # Async completion
    # ──────────────────────────────────────────────────────────────

    async def acomplete(self, prompt: str, system: Optional[str] = None,
                        max_tokens: int = 2048, temperature: float = 0.7) -> str:
        """Async completion via Featherless.ai."""
        body = {
            "model": self.model,
            "messages": self._build_messages(prompt, system),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            js = resp.json()
            text = js["choices"][0]["message"]["content"]
            return self.audit_bias(text)

    # ──────────────────────────────────────────────────────────────
    # Async streaming completion
    # ──────────────────────────────────────────────────────────────

    async def astream(
        self, prompt: str, system: Optional[str] = None,
        max_tokens: int = 2048, temperature: float = 0.7
    ) -> AsyncIterator[str]:
        """
        Async token-by-token streaming via Featherless.ai SSE.
        Yields text chunks as they arrive.
        """
        body = {
            "model": self.model,
            "messages": self._build_messages(prompt, system),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        import json
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue


# ──────────────────────────────────────────────────────────────
# Backward-compatible alias (replaces old LLMClient usage)
# ──────────────────────────────────────────────────────────────

# Singleton
_client: Optional[FeatherlessClient] = None


def get_featherless_client() -> FeatherlessClient:
    global _client
    if _client is None:
        _client = FeatherlessClient()
    return _client


# Alias for old code that imports LLMClient
class LLMClient(FeatherlessClient):
    """
    Drop-in alias for old LLMClient usage.
    All Gemini-specific methods removed.
    """
    pass
