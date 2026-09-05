
import os, sys
sys.path.insert(0, os.path.abspath("."))

from database.firestore_service import get_firestore_service
from app.tools.auth import verify_token

print("=== FIRESTORE DIAGNOSTICS ===")

db = get_firestore_service()
print(f"Firestore connected: {db.is_connected()}")

if not db.is_connected():
    print("ERROR: Firestore not connected. Checking credentials...")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
    print(f"Credentials path: {os.path.abspath(cred_path)}")
    print(f"File exists: {os.path.exists(cred_path)}")
    
    import firebase_admin
    print(f"Apps already initialized: {firebase_admin._apps}")

try:
    print("\nTesting get_user_subscription for 'demo_user'...")
    sub = db.get_user_subscription("demo_user")
    print(f"Subscription: {sub}")
except Exception as e:
    print(f"ERROR calling get_user_subscription: {e}")

print("\nTesting verify_token with 'demo_user' string...")
payload = verify_token("demo_user")
print(f"Payload: {payload}")

print("\n=== DIAGNOSTICS COMPLETE ===")
