import sys
import os
import time
from dotenv import load_dotenv
load_dotenv(override=True)

# Add root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "vectordb") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "vectordb"))

from vectordb.orchestrator import chat

def test_chat_speed():
    user_id = "8LHc6JLobCg5jNW13BrixmxnSPa2"
    message = "How can I save INR 5,000?"
    
    print(f"Testing chat latency for query: '{message}'")
    start_time = time.time()
    
    try:
        response = chat(message, context=[], user_id=user_id)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"Duration: {duration:.2f} seconds")
        print("-" * 20)
        print(f"Status: {response.get('status')}")
        print(f"Answer: {response.get('answer')}")
        print("-" * 20)
        
        if duration > 10:
            print("WARNING: Latency is still high (> 10s)")
        else:
            print("SUCCESS: Latency is within acceptable limits for hackathon.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat_speed()
