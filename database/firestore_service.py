"""
Firebase Firestore Service — Drop-in replacement for MongoDBService.
MIGRATION: MongoDB → Firestore (firebase-admin Python SDK)

Collections mapping:
  MongoDB              →  Firestore
  ─────────────────────────────────────────────────────────────
  users                →  users           (doc ID = email)
  user_profiles        →  user_profiles   (doc ID = user_id)
  user_metadata        →  user_metadata   (doc ID = user_id)
  user_subscriptions   →  user_subscriptions (doc ID = user_id)
  cashflow_alerts      →  cashflow_alerts/{user_id}/alerts  (subcollection)
  user_models          →  user_models     (doc ID = user_id)

All public methods preserve the exact same signatures as MongoDBService
so that ZERO changes are required in routes, routers, or tools.
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()


def _init_firestore():
    """Initialise Firebase Admin SDK once and return a Firestore client."""
    import json
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
        abs_path = os.path.abspath(cred_path)

        if not firebase_admin._apps:
            if os.getenv("FIREBASE_CREDENTIALS"):
                cred_dict = json.loads(os.getenv("FIREBASE_CREDENTIALS", "{}"))
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                print("[SUCCESS] Connected to Firebase Firestore via Env Var")
            elif os.path.exists(abs_path):
                cred = credentials.Certificate(abs_path)
                firebase_admin.initialize_app(cred)
                print("[SUCCESS] Connected to Firebase Firestore")
            else:
                print(
                    f"[ERROR] Firebase credentials file not found at: {abs_path}\n"
                    "        Create a Firebase project, download service account JSON,\n"
                    "        and set FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS in your .env."
                )
                return None

        return firestore.client()
    except Exception as e:
        print(f"[ERROR] Firestore init failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Subscription tier constants (identical to MongoDBService)
# ---------------------------------------------------------------------------
SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "max_transactions": 50,
        "max_ai_queries_per_day": 10,
        "alerts_enabled": False,
        "sms_alerts": False,
        "data_retention_months": 3,
        "priority_support": False,
    },
    "pro": {
        "name": "Pro",
        "price": 500,
        "max_transactions": 500,
        "max_ai_queries_per_day": 50,
        "alerts_enabled": True,
        "sms_alerts": False,
        "data_retention_months": 12,
        "priority_support": False,
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 900,
        "max_transactions": -1,
        "max_ai_queries_per_day": -1,
        "alerts_enabled": True,
        "sms_alerts": True,
        "data_retention_months": -1,
        "priority_support": True,
    },
}


class FirestoreService:
    """
    Drop-in replacement for MongoDBService using Firebase Firestore.
    Every public method has an identical signature to MongoDBService.
    """

    def __init__(self):
        # MIGRATION: replaced pymongo with firebase_admin.firestore
        self.db = _init_firestore()
        # Re-expose tiers as a class attribute (some code reads it directly)
        self.SUBSCRIPTION_TIERS = SUBSCRIPTION_TIERS

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """Return True when Firestore is available."""
        return self.db is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _col(self, name: str):
        """Shorthand for self.db.collection(name)."""
        return self.db.collection(name)

    def _doc(self, collection: str, doc_id: str):
        """Shorthand for a specific document reference."""
        return self.db.collection(collection).document(doc_id)

    def _to_dict(self, snapshot) -> Optional[Dict[str, Any]]:
        """Convert a Firestore DocumentSnapshot to a plain dict (or None)."""
        if snapshot and snapshot.exists:
            return snapshot.to_dict()
        return None

    # ------------------------------------------------------------------
    # User Authentication
    # MIGRATION: MongoDB find/insert_one → Firestore get/set
    # ------------------------------------------------------------------

    def sync_firebase_user(self, uid: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Sync a Firebase user with Firestore.
        If user doesn't exist, create profile and subscription.
        Returns the user info.
        """
        if not self.is_connected():
            return {"success": False, "error": "Firestore not connected"}

        email = email.lower().strip()
        try:
            # We use Firebase UID as our primary user_id now
            user_id = uid 
            
            # Check if user profile exists
            profile_snap = self._doc("user_profiles", user_id).get()
            if not profile_snap.exists:
                # Create user doc (legacy 'users' collection for meta)
                self._doc("users", email).set({
                    "email": email,
                    "user_id": user_id,
                    "name": name or email.split("@")[0],
                    "auth_type": "firebase"
                })
                # Create profile
                self.create_user_profile(user_id, {
                    "name": name or email.split("@")[0], 
                    "email": email,
                    "created_at": datetime.now().isoformat()
                })
                # Create initial free subscription
                self.update_user_subscription(user_id, "free", confirmed=False)
                print(f"[AUTH] Created new Firestore profile for Firebase user: {user_id}")
            
            return {"success": True, "user_id": user_id, "name": name or email.split("@")[0]}
        except Exception as e:
            print(f"[AUTH] Sync error: {e}")
            return {"success": False, "error": str(e)}

    # LEGACY AUTH METHODS (Kept as stubs for now to prevent import errors)
    def register_user(self, email: str, password: str, name: str) -> Dict[str, Any]:
        return {"success": False, "error": "Legacy registration disabled. Use Firebase Auth."}

    def verify_user(self, email: str, password: str) -> Dict[str, Any]:
        return {"success": False, "error": "Legacy login disabled. Use Firebase Auth."}

    # ------------------------------------------------------------------
    # User Profiles
    # MIGRATION: MongoDB user_profiles collection → Firestore user_profiles/{user_id}
    # ------------------------------------------------------------------

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected(): return None
        return self._to_dict(self._doc("user_profiles", user_id).get())

    def create_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            profile_data["user_id"] = user_id
            # MIGRATION: MongoDB upsert → Firestore set(merge=True)
            self._doc("user_profiles", user_id).set(profile_data, merge=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            # Use set(merge=True) instead of update() so this works even if the
            # document doesn't exist yet (e.g. demo mode, unsynced profiles).
            updates["user_id"] = user_id
            self._doc("user_profiles", user_id).set(updates, merge=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_user_profile(self, user_id: str) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            self._doc("user_profiles", user_id).delete()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_all_users(self) -> List[str]:
        if not self.is_connected(): return []
        return [doc.id for doc in self._col("user_profiles").stream()]

    # ------------------------------------------------------------------
    # CSV Metadata
    # MIGRATION: MongoDB user_metadata collection → Firestore user_metadata/{user_id}
    # ------------------------------------------------------------------

    def save_user_csv_metadata(self, user_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            self._doc("user_metadata", user_id).set(metadata, merge=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_csv_metadata(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_connected(): return None
        return self._to_dict(self._doc("user_metadata", user_id).get())

    # ------------------------------------------------------------------
    # User Models
    # ------------------------------------------------------------------

    def save_model_info(self, user_id: str, model_info: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            self._doc("user_models", user_id).set(model_info, merge=True)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Cashflow Alerts
    # MIGRATION: MongoDB cashflow_alerts collection → Firestore subcollection
    #   cashflow_alerts/{user_id}/alerts/{auto_id}
    #   (subcollection is Firestore best practice for per-user lists)
    # ------------------------------------------------------------------

    def save_cashflow_alert(self, user_id: str, alert: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            alert["user_id"] = user_id
            alert["created_at"] = datetime.now().isoformat()
            # MIGRATION: MongoDB insert_one → Firestore subcollection add()
            self.db.collection("cashflow_alerts").document(user_id).collection("alerts").add(alert)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_alerts(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_connected(): return []
        try:
            # MIGRATION: MongoDB find().sort().limit() → Firestore order_by().limit()
            from firebase_admin import firestore
            query = (
                self.db.collection("cashflow_alerts")
                .document(user_id)
                .collection("alerts")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            return [doc.to_dict() for doc in query.stream()]
        except Exception as e:
            print(f"[Firestore] Error fetching alerts: {e}")
            return []

    def clear_user_alerts(self, user_id: str) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        try:
            # MIGRATION: MongoDB delete_many → Firestore batch delete of subcollection docs
            alerts_ref = self.db.collection("cashflow_alerts").document(user_id).collection("alerts")
            batch = self.db.batch()
            deleted = 0
            for doc in alerts_ref.stream():
                batch.delete(doc.reference)
                deleted += 1
            batch.commit()
            return {"success": True, "deleted_count": deleted}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Subscriptions
    # MIGRATION: MongoDB user_subscriptions → Firestore user_subscriptions/{user_id}
    # ------------------------------------------------------------------

    def update_user_subscription(self, user_id: str, tier: str, months: int = 1, confirmed: bool = True) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False, "error": "Firestore not connected"}
        if tier not in SUBSCRIPTION_TIERS:
            return {"success": False, "error": f"Invalid tier: {tier}"}

        try:
            expiry = None
            if tier != "free":
                expiry = (datetime.now() + timedelta(days=30 * months)).isoformat()

            # MIGRATION: MongoDB update_one(upsert) → Firestore set(merge=True)
            self._doc("user_subscriptions", user_id).set({
                "user_id": user_id,
                "tier": tier,
                "expiry": expiry,
                "updated_at": datetime.now().isoformat(),
                "plan_confirmed": confirmed,
                "ai_queries_today": 0,
                "transactions_this_month": 0,
            }, merge=True)
            return {"success": True, "tier": tier, "expiry": expiry}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_subscription(self, user_id: str) -> Dict[str, Any]:
        if not self.is_connected():
            return {"tier": "free", "features": SUBSCRIPTION_TIERS["free"]}

        try:
            snap = self._doc("user_subscriptions", user_id).get()
            if not snap.exists:
                return {"tier": "free", "features": SUBSCRIPTION_TIERS["free"]}

            data = snap.to_dict()
            tier = data.get("tier", "free")

            # Check expiry
            expiry = data.get("expiry")
            if expiry and tier != "free":
                if datetime.fromisoformat(expiry) < datetime.now():
                    tier = "free"

            return {
                "tier": tier,
                "features": SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["free"]),
                "expiry": data.get("expiry"),
                "plan_confirmed": data.get("plan_confirmed", False) if tier != "free" else data.get("plan_confirmed", True),
                "ai_queries_today": data.get("ai_queries_today", 0),
                "transactions_this_month": data.get("transactions_this_month", 0),
            }
        except Exception as e:
            return {"tier": "free", "features": SUBSCRIPTION_TIERS["free"], "error": str(e)}

    def check_feature_access(self, user_id: str, feature: str) -> Dict[str, Any]:
        sub = self.get_user_subscription(user_id)
        tier = sub.get("tier", "free")
        features = sub.get("features", SUBSCRIPTION_TIERS["free"])

        if feature == "ai_query":
            limit = features.get("max_ai_queries_per_day", 10)
            used = sub.get("ai_queries_today", 0)
            if limit == -1:
                return {"allowed": True, "remaining": -1}
            return {"allowed": used < limit, "remaining": max(0, limit - used), "limit": limit}

        elif feature == "transactions":
            limit = features.get("max_transactions", 50)
            used = sub.get("transactions_this_month", 0)
            if limit == -1:
                return {"allowed": True, "remaining": -1}
            return {"allowed": used < limit, "remaining": max(0, limit - used), "limit": limit}

        elif feature == "alerts":
            return {"allowed": features.get("alerts_enabled", False)}

        elif feature == "sms_alerts":
            return {"allowed": features.get("sms_alerts", False)}

        return {"allowed": True}

    def increment_usage(self, user_id: str, usage_type: str) -> Dict[str, Any]:
        if not self.is_connected(): return {"success": False}
        try:
            from google.cloud.firestore_v1 import Increment
            ref = self._doc("user_subscriptions", user_id)

            if usage_type == "ai_query":
                # MIGRATION: MongoDB $inc → Firestore Increment sentinel
                ref.update({"ai_queries_today": Increment(1)})
            elif usage_type == "transaction":
                ref.update({"transactions_this_month": Increment(1)})
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Singleton factory — same interface as get_mongodb_service()
# ---------------------------------------------------------------------------
_service: Optional[FirestoreService] = None


def get_firestore_service() -> FirestoreService:
    """
    Get or create a singleton instance of the FirestoreService.
    """
    global _service
    if _service is None:
        _service = FirestoreService()
    return _service

# Alias for backward compatibility (Deprecated)
def get_mongodb_service() -> FirestoreService:
    return get_firestore_service()
