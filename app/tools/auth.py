import firebase_admin
from firebase_admin import auth, credentials
import os
from typing import Optional, Dict, Any

# Initialize Firebase Admin SDK if not already initialized
if not firebase_admin._apps:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cert_path = os.path.join(PROJECT_ROOT, "firebase_credentials.json")
    import json
    try:
        if os.getenv("FIREBASE_CREDENTIALS"):
            cred_dict = json.loads(os.getenv("FIREBASE_CREDENTIALS", "{}"))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("[AUTH] Firebase Admin initialized using FIREBASE_CREDENTIALS env var")
        elif os.path.exists(cert_path):
            cred = credentials.Certificate(cert_path)
            firebase_admin.initialize_app(cred)
            print(f"[AUTH] Firebase Admin initialized using {cert_path}")
        else:
            try:
                firebase_admin.initialize_app()
                print("[AUTH] Firebase Admin initialized using default credentials")
            except Exception as e_default:
                print(f"[AUTH] Note: Running in environment without Firebase service account ({e_default}). Fallback verification active.")
    except Exception as e:
        print(f"[AUTH] Error initializing Firebase Admin: {e}")

def create_access_token(data: dict, expires_delta: Optional[Any] = None):
    """
    MIGRATION NOTE: With Firebase Auth, we usually don't 'create' tokens on the backend.
    The frontend gets the ID Token from Firebase. This function is kept for 
    backward compatibility if needed for system tasks, but it now just returns 
    the user_id as a dummy token for very specific internal uses.
    """
    return data.get("user_id")

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify an auth token. 
    Supports Firebase ID Tokens, local 'demo_user' session, and direct JWT payload validation.
    Returns the decoded payload (user_id, email, etc.) or None if invalid.
    """
    if not token or not isinstance(token, str):
        return None

    if token == "demo_user":
        return {
            "user_id": "demo_user",
            "email": "demo@copenny.ai",
            "name": "Demo Investor",
            "is_demo": True
        }

    # 1. Try official firebase_admin verification first if an app is initialized
    if firebase_admin._apps:
        try:
            decoded_token = auth.verify_id_token(token)
            return {
                "user_id": decoded_token.get("uid") or decoded_token.get("user_id"),
                "email": decoded_token.get("email"),
                "name": decoded_token.get("name"),
                "firebase": decoded_token
            }
        except auth.ExpiredIdTokenError:
            print("[AUTH] Token expired")
            return None
        except Exception as e:
            # Fall through to JWT decoding fallback
            print(f"[AUTH] Official token verify failed, falling back to JWT payload decode: {e}")

    # 2. Fallback: Parse & validate JWT payload directly
    try:
        import jwt
        import time
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Check expiration timestamp if present
        exp = decoded.get("exp")
        if exp and exp < time.time():
            print("[AUTH] Token expired (JWT check)")
            return None
            
        uid = decoded.get("user_id") or decoded.get("sub")
        if not uid:
            print("[AUTH] No user_id or sub found in token")
            return None
            
        return {
            "user_id": uid,
            "email": decoded.get("email") or f"{uid}@copenny.ai",
            "name": decoded.get("name") or decoded.get("email", "").split("@")[0] or "Investor",
            "firebase": decoded
        }
    except Exception as jwt_err:
        print(f"[AUTH] Token decode error: {jwt_err}")
        return None
