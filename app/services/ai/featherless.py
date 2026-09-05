"""
app/services/ai/featherless.py
Base Featherless.ai service used by all six agents.
"""
from llm.featherless_client import get_featherless_client, FeatherlessClient
from typing import Optional, AsyncIterator


def get_client() -> FeatherlessClient:
    return get_featherless_client()


async def chat(prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> str:
    client = get_client()
    return await client.acomplete(prompt, system=system, max_tokens=max_tokens)


async def stream(prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> AsyncIterator[str]:
    client = get_client()
    async for chunk in client.astream(prompt, system=system, max_tokens=max_tokens):
        yield chunk
