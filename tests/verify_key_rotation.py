import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from llm.llm_client import LLMClient

class TestLLMClientShuffling(unittest.TestCase):
    @patch('random.shuffle', side_effect=lambda x: x) # Keep order deterministic for rotation test
    @patch('requests.post')
    def test_gemini_key_rotation(self, mock_post, mock_shuffle):
        # Set up environment variables for testing with all 6 keys + fallback
        with patch.dict(os.environ, {
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
        }):
            client = LLMClient()
            self.assertEqual(len(client.gemini_keys), 9)
            # Note: client.gemini_keys is shuffled in __init__
            keys_found = sorted(client.gemini_keys)
            self.assertEqual(keys_found, sorted(["key1", "key2", "key3", "key4", "key5", "key6", "key7", "key8", "fallback_key"]))

            # Mock responses: 
            # 1st call: 429 Resource Exhausted
            # 2nd call: 200 Success
            mock_resp_429 = MagicMock()
            mock_resp_429.status_code = 429
            mock_resp_429.text = "Quota exceeded"

            mock_resp_200 = MagicMock()
            mock_resp_200.status_code = 200
            mock_resp_200.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "Success from key 2"}]}}]
            }

            mock_post.side_effect = [mock_resp_429, mock_resp_200]

            response = client.complete("test prompt")
            
            self.assertEqual(response, "Success from key 2")
            self.assertEqual(mock_post.call_count, 2)
            
            # Verify URLs used the correct keys
            args1, kwargs1 = mock_post.call_args_list[0]
            self.assertIn("key=key1", args1[0])
            
            args2, kwargs2 = mock_post.call_args_list[1]
            self.assertIn("key=key2", args2[0])
            
            print("\nVerification successful: Gemini key rotated from key1 to key2 after 429 error.")

if __name__ == "__main__":
    unittest.main()
