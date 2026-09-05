import os
import time
import hashlib
import json
from typing import Dict, Any
from llm.featherless_client import get_featherless_client

class SecureAIGateway:
    def __init__(self):
        # Persistent Featherless AI client with Qwen/Qwen2.5-7B-Instruct
        self.llm_client = get_featherless_client()
        
        # Caching: { (user_id, prompt_hash): (response, timestamp) }
        self.cache = {}
        self.CACHE_TTL = 300  # 5 minutes
        
        # Rate Limiting: { user_id: [timestamps] }
        self.request_log = {}
        self.RATE_LIMIT_PER_HOUR = 100

    def _get_prompt_hash(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode()).hexdigest()

    def _is_rate_limited(self, user_id: str) -> bool:
        now = time.time()
        one_hour_ago = now - 3600
        
        if user_id not in self.request_log:
            self.request_log[user_id] = []
            
        # Clean up old requests
        self.request_log[user_id] = [t for t in self.request_log[user_id] if t > one_hour_ago]
        
        if len(self.request_log[user_id]) >= self.RATE_LIMIT_PER_HOUR:
            return True
        
        self.request_log[user_id].append(now)
        return False

    async def aget_insight(self, user_id: str, prompt: str, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI Gateway logic with Featherless.ai, caching, and rate limiting (Natively ASYNC).
        """
        prompt_hash = self._get_prompt_hash(prompt)
        cache_key = (user_id, prompt_hash)
        
        # 1. Check Cache
        if cache_key in self.cache:
            response, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.CACHE_TTL:
                print(f"[AI GATEWAY] Returning cached result for user: {user_id}")
                return response

        # 2. Check Rate Limit
        if self._is_rate_limited(user_id):
            print(f"[AI GATEWAY] Rate hit for user: {user_id}. Returning analytics only.")
            return {
                **analytics_data,
                "insight": "AI insight usage limit reached. Showing data-driven analytics.",
                "status": "rate_limited"
            }

        # 3. Call Featherless AI
        try:
            print(f"[AI GATEWAY] Requesting Featherless AI for user: {user_id}")
            response_text = await self.llm_client.acomplete(prompt)
            
            final_response = {
                **analytics_data,
                "insight": response_text.strip(),
                "status": "success"
            }
            
            # Update Cache
            self.cache[cache_key] = (final_response, time.time())
            return final_response
            
        except Exception as e:
            err_str = str(e).lower()
            print(f"[AI GATEWAY] Featherless LLM call failed: {err_str}")
            
            user_msg = "Our AI Advisor is currently experiencing high demand. Please try again in a few moments."
            if "quota" in err_str or "429" in err_str:
                user_msg = "AI capacity limit reached. We'll be back online in a minute! Thank you for your patience."

            return {
                **analytics_data,
                "insight": user_msg,
                "status": "overloaded"
            }


# Global singleton
ai_gateway = SecureAIGateway()
