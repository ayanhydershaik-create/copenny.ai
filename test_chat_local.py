import requests
import json

def test_chat():
    url = "http://localhost:8080/chat"
    payload = {
        "session_id": "test_session",
        "message": "Where did I spend the most this month?",
        "context": [],
        "user_id": "8LHc6JLobCg5jNW13BrixmxnSPa2"
    }
    
    # We need a valid cookie because of Depends(get_current_user)
    # But for a local test, let's see if we get a 401 (meaning server is up)
    # or a connection error.
    try:
        print(f"Testing {url}...")
        # Note: This will likely return 401 because no cookie is provided
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    test_chat()
