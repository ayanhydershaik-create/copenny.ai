import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure app is in path
sys.path.append(os.getcwd())

from llm.llm_client import LLMClient
from app.services.ai_service import SecureAIGateway

class TestCentralizedGeminiRotation(unittest.TestCase):
    def setUp(self):
        # Mock random.shuffle to keep order deterministic for rotation test
        self.shuffle_patcher = patch('random.shuffle', side_effect=lambda x: x)
        self.shuffle_patcher.start()
        
        # Mock environment variables for all keys
        self.env_patcher = patch.dict(os.environ, {
            "GEMINI_KEY_1": "key1",
            "GEMINI_KEY_2": "key2",
            "GEMINI_KEY_3": "key3",
            "GEMINI_KEY_4": "key4",
            "GEMINI_KEY_5": "key5",
            "GEMINI_KEY_6": "key6",
            "GEMINI_KEY_7": "key7",
            "GEMINI_KEY_8": "key8",
            "GEMINI_API_KEY": "fallback_key",
            "LLM_PROVIDER": "gemini"
        })
        self.env_patcher.start()
        self.client = LLMClient()

    def tearDown(self):
        self.env_patcher.stop()
        self.shuffle_patcher.stop()

    @patch('requests.post')
    def test_llm_client_rotation(self, mock_post):
        # Setup mock responses
        # 1. First key hits 429
        # 2. Second key hits 403 (Quota)
        # 3. Third key succeeds
        
        response_429 = MagicMock()
        response_429.status_code = 429
        response_429.text = "Resource has been exhausted"
        
        response_403 = MagicMock()
        response_403.status_code = 403
        response_403.text = "Quota exceeded"
        
        response_success = MagicMock()
        response_success.status_code = 200
        response_success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Success from key 3"}]}}]
        }
        
        mock_post.side_effect = [response_429, response_403, response_success]
        
        print("\n[TEST] Verifying LLMClient centralized rotation...")
        result = self.client.complete("Hello AI")
        
        self.assertEqual(result, "Success from key 3")
        # Verify it tried 3 times (3 different keys)
        self.assertEqual(mock_post.call_count, 3)
        
        # Verify keys were rotated in URLs
        urls = [call.args[0] for call in mock_post.call_args_list]
        self.assertIn("key=key1", urls[0])
        self.assertIn("key=key2", urls[1])
        self.assertIn("key=key3", urls[2])
        print("[TEST] Success: LLMClient correctly rotated through keys on exhaustion.")

    @patch('app.services.ai_service.LLMClient')
    def test_gateway_integration(self, MockLLM):
        # Verify that SecureAIGateway correctly uses the new LLMClient
        mock_instance = MockLLM.return_value
        mock_instance.complete.return_value = "Integrated Success"
        
        gateway = SecureAIGateway()
        result = gateway.get_insight("user123", "prompt", {"data": 123})
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["insight"], "Integrated Success")
        print("[TEST] Success: SecureAIGateway integration verified.")

if __name__ == "__main__":
    unittest.main()
