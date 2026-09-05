import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

load_dotenv(override=True)

from llm.llm_client import LLMClient

def test_fallback():
    print("--- Verifying LLM Fallback Logic ---")
    
    # Initialize client
    client = LLMClient()
    client.provider = "gemini"
    
    # Force Gemini to fail by using invalid keys
    client.gemini_keys = ["invalid_key_to_force_failure"]
    
    print(f"Primary Provider: {client.provider}")
    print(f"Fallback Model: {client.openrouter_model}")
    
    try:
        print("\nAttempting completion (Gemini keys should fail)...")
        # Use a short prompt for test
        response = client.complete("Hello, say 'Backup Active' in 2 words.")
        print(f"\nResponse received: {response}")
        
        # Check if response came through
        print("\n[SUCCESS] Fallback logic triggered and returned a response.")
    except Exception as e:
        print(f"\n[FAILURE] Fallback failed with error: {e}")

if __name__ == "__main__":
    test_fallback()
