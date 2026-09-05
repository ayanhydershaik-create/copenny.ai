"""
app/routers/subscriptions.py
Subscription management API endpoints backed by PostgreSQL hackwave_db.
AI-powered unused subscription detection.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from database.postgres_service import get_postgres_service
from app.tools.auth import verify_token
from fastapi import Cookie

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


def get_user_id(copenny_auth: Optional[str] = Cookie(None)) -> str:
    if not copenny_auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(copenny_auth)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["user_id"]


class SubscriptionCreate(BaseModel):
    name: str
    amount: float
    billing_cycle: str = "monthly"
    category: str = "Subscription"
    next_billing_date: Optional[str] = None
    is_active: bool = True
    notes: str = ""


class SubscriptionUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None
    billing_cycle: Optional[str] = None
    category: Optional[str] = None
    next_billing_date: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


@router.get("")
def list_subscriptions(
    user_id: str = Depends(get_user_id),
    active_only: bool = Query(False),
):
    """List all subscriptions from PostgreSQL with monthly cost summary."""
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    subs = pg.get_subscriptions(user_id, active_only=active_only)

    total_monthly = 0.0
    for s in subs:
        amount = float(s.get("amount") or 0)
        cycle = s.get("billing_cycle", "monthly")
        if cycle == "monthly":
            s["monthly_equivalent"] = amount
        elif cycle == "annual" or cycle == "yearly":
            s["monthly_equivalent"] = round(amount / 12, 2)
        elif cycle == "quarterly":
            s["monthly_equivalent"] = round(amount / 3, 2)
        else:
            s["monthly_equivalent"] = amount
        if s.get("is_active"):
            total_monthly += s["monthly_equivalent"]

    return {
        "subscriptions": subs,
        "count": len(subs),
        "total_monthly_cost": round(total_monthly, 2),
        "total_annual_cost": round(total_monthly * 12, 2),
    }


@router.post("", status_code=201)
def create_subscription(body: SubscriptionCreate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    if not pg.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        sub = pg.create_subscription(user_id, body.model_dump())
        return sub
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{sub_id}")
def update_subscription(sub_id: str, body: SubscriptionUpdate, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    updated = pg.update_subscription(sub_id, user_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return updated


@router.delete("/{sub_id}", status_code=204)
def delete_subscription(sub_id: str, user_id: str = Depends(get_user_id)):
    pg = get_postgres_service()
    pg.delete_subscription(sub_id, user_id)
    return None


@router.get("/detect-unused")
async def detect_unused(user_id: str = Depends(get_user_id)):
    """
    AI-powered unused subscription detection.
    Returns analysis for user review — never auto-cancels.
    """
    pg = get_postgres_service()
    subs = pg.get_subscriptions(user_id, active_only=True)
    transactions = pg.get_transactions(user_id, limit=200)

    from app.services.ai.agents.subscriptions import identify_unused
    result = await identify_unused(subs, transactions)
    return result


@router.post("/{sub_id}/cancel-workflow")
def get_cancellation_workflow(sub_id: str, user_id: str = Depends(get_user_id)):
    """
    Get cancellation instructions for a subscription.
    IMPORTANT: This marks the subscription as inactive in CoPenny.
    It does NOT cancel the actual external subscription — user must do that.
    """
    pg = get_postgres_service()
    sub = next(
        (s for s in pg.get_subscriptions(user_id) if s.get("id") == sub_id),
        None
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {
        "subscription": sub,
        "disclaimer": (
            "CoPenny cannot cancel external subscriptions automatically. "
            "Follow the steps below to cancel your subscription directly."
        ),
        "steps": [
            f"1. Log in to your {sub.get('name')} account",
            "2. Go to Settings → Billing or Subscription",
            "3. Click 'Cancel Subscription' or 'Cancel Plan'",
            "4. Follow any confirmation prompts",
            f"5. Return here and click 'Mark as Cancelled' to update your CoPenny record",
        ],
        "mark_inactive_action": f"PUT /api/subscriptions/{sub_id} with is_active=false",
    }
