"""
app/routers/anomalies.py
Real-time Anomaly Detection Router using PostgreSQL transaction records.

Features:
- Detect unusual transactions (>2 standard deviations above category average)
- Assign confidence score (0-99%)
- AI-backed contextual explanations
- Safe action workflows (Review, Flag Transaction, Contact Bank Guidance)
- Strictly no fake card-locking claims
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Cookie
from pydantic import BaseModel

from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from app.services.ai.agents.anomaly import classify_transaction

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class ActionWorkflowReq(BaseModel):
    transaction_id: str
    action_type: str  # "review" | "flag_suspicious" | "contact_bank_guide"
    notes: Optional[str] = None


@router.get("")
def get_anomalies(user_id: str = Depends(get_user_id), lookback_days: int = 90):
    """
    Retrieve detected spending anomalies from real PostgreSQL transactions.
    """
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")

    anomalies = pg.get_anomalies(user_id, lookback_days=lookback_days)
    return {
        "anomalies": anomalies,
        "count": len(anomalies),
        "status": "warning" if len(anomalies) > 0 else "clean",
    }


@router.post("/action")
def execute_anomaly_action(body: ActionWorkflowReq, user_id: str = Depends(get_user_id)):
    """
    Safe workflow for handling detected anomalies.
    Does NOT falsely pretend to lock debit/credit cards or freeze bank accounts.
    """
    pg = get_postgres_service()
    tx = pg.get_transaction(body.transaction_id, user_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if body.action_type == "review":
        pg.update_transaction(body.transaction_id, user_id, {
            "notes": f"Reviewed by user on {tx.get('date')}: Confirmed legitimate."
        })
        return {
            "success": True,
            "status": "reviewed",
            "message": "Transaction marked as reviewed and verified by user.",
        }

    elif body.action_type == "flag_suspicious":
        pg.update_transaction(body.transaction_id, user_id, {
            "notes": f"FLAGGED AS SUSPICIOUS: {body.notes or 'Unrecognized charge'}"
        })
        return {
            "success": True,
            "status": "flagged",
            "message": "Transaction flagged for your records. Export this transaction details for your bank dispute.",
        }

    elif body.action_type == "contact_bank_guide":
        return {
            "success": True,
            "status": "guidance_provided",
            "transaction_details": {
                "id": tx["id"],
                "merchant": tx.get("merchant"),
                "amount": tx.get("amount"),
                "date": str(tx.get("date")),
            },
            "steps": [
                "1. Call your bank's customer service number on the back of your card.",
                "2. Reference the exact transaction date, amount, and merchant name.",
                "3. Request a temporary block on the affected card if you suspect unauthorized access.",
                "4. Ask for a dispute form / chargeback initiation.",
            ],
            "disclaimer": "CoPenny AI does not connect directly to banking settlement rails and cannot freeze cards on your behalf.",
        }

    raise HTTPException(status_code=400, detail=f"Unsupported action type: {body.action_type}")
