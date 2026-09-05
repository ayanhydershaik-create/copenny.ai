"""
llm/llm_client.py
Now a thin re-export of FeatherlessClient for backward compatibility.
All Gemini / OpenRouter / 8-key rotation logic has been removed.
"""
from llm.featherless_client import FeatherlessClient as LLMClient, get_featherless_client

__all__ = ["LLMClient", "get_featherless_client"]
