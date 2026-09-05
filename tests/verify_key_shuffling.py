import os
import sys
import unittest
from unittest.mock import patch

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from llm.llm_client import LLMClient

class TestLLMClientShuffling(unittest.TestCase):
    def test_gemini_key_shuffling(self):
        # Set up a fixed set of keys
        mock_env = {
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
        }
        
        with patch.dict(os.environ, mock_env):
            # Capture the order of keys across multiple instances
            orders = []
            for _ in range(50):
                client = LLMClient()
                orders.append(tuple(client.gemini_keys))
            
            # Verify that we have more than one unique order
            unique_orders = set(orders)
            print(f"\nUnique orders observed: {len(unique_orders)} out of 50 trials.")
            
            self.assertGreater(len(unique_orders), 1, "Keys were not shuffled!")
            
            # Also verify all keys are present in each instance
            for order in orders:
                self.assertEqual(len(order), 9)
                self.assertTrue(all(k in order for k in ["key1", "key2", "key3", "key4", "key5", "key6", "key7", "key8", "fallback_key"]))

if __name__ == "__main__":
    unittest.main()
